# tests/test_database_nodes.py

import pytest
from backend import database
from backend.models import db, Node, Version


# Diese Tests verwenden die Fixtures, die die ORM-Objekte zurückgeben
# (z.B. test_user_1_obj, test_vault_1_obj, test_user_2_obj, test_vault_2_obj)

# --- Tests für die Erstellung (CREATE) ---

def test_create_node_success(test_user_1_obj, test_vault_1_obj, db_session):
    """Testet die direkte, erfolgreiche Erstellung eines Nodes über die DB-Funktion."""
    # Arrange
    title = "My DB Test Node"
    content = "Some content."
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Act
    new_node = database.create_node(
        title=title,
        content=content,
        parent_id=None,
        vault_id=vault_id,
        author_id=user_id
    )

    # Assert
    assert new_node is not None
    assert new_node.title == title
    assert new_node.vault_id == vault_id

    # Überprüfen, ob die Version korrekt erstellt wurde
    retrieved_node = db_session.session.get(Node, new_node.id)
    assert retrieved_node is not None
    assert retrieved_node.current_version == 1
    assert len(retrieved_node.versions) == 1
    assert retrieved_node.versions[0].content == content
    assert retrieved_node.versions[0].author_id == user_id


def test_create_node_fails_for_invalid_vault(test_user_1_obj):
    """Testet, dass das Erstellen fehlschlägt, wenn die vault_id ungültig ist."""
    with pytest.raises(ValueError, match="Vault with ID 999 not found."):
        database.create_node(
            title="Wont be created",
            content="",
            parent_id=None,
            vault_id=999,
            author_id=test_user_1_obj.id
        )


# --- Tests für das Lesen und Berechtigungen (READ) ---

def test_get_all_nodes_as_tree_permission_denied(test_user_1_obj, test_vault_2_obj):
    """
    Sicherheitstest: Stellt sicher, dass _verify_vault_access in get_all_nodes_as_tree
    den Zugriff verweigert, wenn der User nicht der Besitzer ist.
    """
    # Arrange
    user1_id = test_user_1_obj.id
    vault_of_user2_id = test_vault_2_obj.id

    # Act & Assert
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        database.get_all_nodes_as_tree(vault_id=vault_of_user2_id, user_id=user1_id)


def test_get_node_by_id_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_2_obj):
    """
    Sicherheitstest: Verhindert das Abrufen eines einzelnen Nodes aus einem fremden Vault.
    """
    # Arrange: Benutzer 2 erstellt einen Node in seinem Vault
    node_in_vault2 = database.create_node(
        title="Secret Node", content="secret", parent_id=None,
        vault_id=test_vault_2_obj.id, author_id=test_user_2_obj.id
    )

    # Act & Assert: Benutzer 1 versucht, darauf zuzugreifen
    with pytest.raises(PermissionError):
        database.get_node_by_id(
            node_id=node_in_vault2.id,
            vault_id=test_vault_2_obj.id,
            user_id=test_user_1_obj.id
        )


# --- Tests für die Aktualisierung (UPDATE) ---

def test_update_node_creates_new_version(test_user_1_obj, test_vault_1_obj):
    """Testet, dass update_node eine neue Version erstellt und die current_version hochzählt."""
    # Arrange
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node = database.create_node("V1 Node", "Content V1", None, vault_id, user_id)
    assert node.current_version == 1

    # Act
    updated_node = database.update_node(
        node_id=node.id,
        vault_id=vault_id,
        user_id=user_id,
        content="Content V2"
    )

    # Assert
    assert updated_node.current_version == 2

    # Direkt aus der DB holen zur Verifizierung
    db.session.refresh(updated_node)
    assert len(updated_node.versions) == 2

    v1 = Version.query.filter_by(node_id=node.id, version=1).one()
    v2 = Version.query.filter_by(node_id=node.id, version=2).one()

    assert v1.content == "Content V1"
    assert v2.content == "Content V2"
    assert v2.author_id == user_id


# --- Tests für das Löschen (DELETE) ---

def test_delete_node_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_1_obj, db_session):
    """Sicherheitstest: Verhindert das Löschen eines Nodes durch einen unautorisierten Benutzer."""
    # Arrange: Benutzer 1 erstellt einen Node
    node_to_delete = database.create_node(
        "Node by User 1", "", None, test_vault_1_obj.id, test_user_1_obj.id
    )

    # Act & Assert: Benutzer 2 versucht, ihn zu löschen
    with pytest.raises(PermissionError):
        database.delete_node(
            node_id=node_to_delete.id,
            vault_id=test_vault_1_obj.id,
            user_id=test_user_2_obj.id  # Falscher Benutzer!
        )

    # Überprüfen, dass der Node noch da ist
    assert db_session.session.get(Node, node_to_delete.id) is not None


# --- Tests für das Verschieben (MOVE) ---

def test_move_node_fails_on_cyclic_dependency(test_user_1_obj, test_vault_1_obj):
    """Testet die interne Logik (_is_descendant), die das Verschieben in ein eigenes Kind verhindert."""
    # Arrange
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    grandparent = database.create_node("Grandparent", "", None, vault_id, user_id)
    parent = database.create_node("Parent", "", grandparent.id, vault_id, user_id)

    # Act & Assert: Versuche, den Großvater unter den Vater zu schieben
    with pytest.raises(ValueError, match="Cannot move a node into one of its own children."):
        database.move_node(
            node_id=grandparent.id,
            new_parent_id=parent.id,
            vault_id=vault_id,
            user_id=user_id
        )

def test_node_to_dict_sorts_children_alphabetically(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob die `to_dict`-Methode mit `include_children=True`
    die Kind-Nodes korrekt alphabetisch nach Titel sortiert.
    """
    # 1. ARRANGE: Erstelle einen Parent und mehrere Children in NICHT-alphabetischer Reihenfolge.
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    parent = database.create_node(
        title="Parent Node", content="", parent_id=None,
        vault_id=vault_id, author_id=user_id
    )

    # Erstelle die Kinder absichtlich "unsortiert"
    database.create_node(
        title="Charlie Child", content="", parent_id=parent.id,
        vault_id=vault_id, author_id=user_id
    )
    database.create_node(
        title="Alice Child", content="", parent_id=parent.id,
        vault_id=vault_id, author_id=user_id
    )
    database.create_node(
        title="Bob Child", content="", parent_id=parent.id,
        vault_id=vault_id, author_id=user_id
    )

    # Holen den Parent frisch aus der DB, um sicherzustellen, dass die Relationships geladen sind
    parent_from_db = db_session.session.get(Node, parent.id)


    # 2. ACT: Rufe die zu testende Methode auf.
    result_dict = parent_from_db.to_dict(include_children=True)


    # 3. ASSERT: Überprüfe, ob die zurückgegebene Liste sortiert ist.
    assert 'children' in result_dict
    assert len(result_dict['children']) == 3

    # Extrahiere die Titel aus der Ergebnisliste
    child_titles = [child['title'] for child in result_dict['children']]

    # Definiere die erwartete, alphabetisch sortierte Reihenfolge
    expected_order = ["Alice Child", "Bob Child", "Charlie Child"]

    # Die entscheidende Prüfung: Ist die Reihenfolge korrekt?
    assert child_titles == expected_order

def test_get_all_nodes_as_list(test_user_1_obj, test_vault_1_obj):
    """Testet get_all_nodes_as_list."""
    database.create_node("Node A", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    nodes = database.get_all_nodes_as_list(test_vault_1_obj.id, test_user_1_obj.id)
    # Es gibt den Root-Node "Summary" und "Node A"
    assert len(nodes) == 2
    assert isinstance(nodes[0], dict)

def test_get_node_by_title_not_found(test_user_1_obj, test_vault_1_obj):
    """Testet, was passiert, wenn kein Node mit dem Titel gefunden wird."""
    result = database.get_node_by_title("Non Existent Node", test_vault_1_obj.id, test_user_1_obj.id)
    assert result is None

def test_update_node_with_no_changes(test_user_1_obj, test_vault_1_obj):
    """Testet den Fall, bei dem update_node keine Änderungen vornimmt."""
    node = database.create_node("Original Title", "Original Content", None, test_vault_1_obj.id, test_user_1_obj.id)
    # Rufe update ohne neue Daten auf
    updated_node = database.update_node(
        node.id, test_vault_1_obj.id, test_user_1_obj.id,
        title="Original Title", content="Original Content"
    )
    # Es sollte keine neue Version erstellt werden
    assert updated_node.current_version == 1

def test_create_node_with_invalid_parent(test_user_1_obj, test_vault_1_obj):
    """Testet die Erstellung eines Nodes mit einer ungültigen parent_id."""
    with pytest.raises(ValueError, match="Parent node not found"):
        database.create_node("Child", "", "invalid-parent-id", test_vault_1_obj.id, test_user_1_obj.id)

# tests/test_database_nodes.py
# Stellen Sie sicher, dass 'database' und 'Node' importiert sind

def test_get_all_nodes_as_tree_success_and_structure(test_user_1_obj, test_vault_1_obj):
    """
    Testet den Erfolgsfall von get_all_nodes_as_tree und prüft,
    ob die Baumstruktur korrekt aufgebaut wird.
    """
    # 1. ARRANGE: Erstelle eine bekannte Hierarchie
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Der Vault hat bereits einen Root-Node "Summary". Wir fügen eine neue Hierarchie hinzu.
    parent_node = database.create_node(
        title="Parent A", content="", parent_id=None,
        vault_id=vault_id, author_id=user_id
    )
    child_node = database.create_node(
        title="Child A.1", content="", parent_id=parent_node.id,
        vault_id=vault_id, author_id=user_id
    )

    # 2. ACT: Rufe die zu testende Funktion auf
    tree = database.get_all_nodes_as_tree(vault_id=vault_id, user_id=user_id)

    # 3. ASSERT: Überprüfe die Struktur des Ergebnisses
    # Es sollte eine Liste mit 2 Root-Elementen sein: "Summary" und "Parent A"
    assert isinstance(tree, list)
    assert len(tree) == 2

    # Finde unseren Parent-Node im Ergebnis (die Liste ist nach Titel sortiert)
    assert tree[0]['title'] == 'Parent A'
    parent_dict = tree[0]

    # Überprüfe, ob das Kind korrekt verschachtelt ist
    assert 'children' in parent_dict
    assert len(parent_dict['children']) == 1
    assert parent_dict['children'][0]['title'] == 'Child A.1'

# tests/test_database_nodes.py
# Fügen Sie diesen Test zur Datei hinzu.

def test_get_nodes_by_ids_success(test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_nodes_by_ids die korrekten Nodes als Dictionaries zurückgibt.
    """
    # 1. ARRANGE: Erstelle mehrere Nodes, um sie später abzurufen.
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    node1 = database.create_node("Node 1", "Content 1", None, vault_id, user_id)
    node2 = database.create_node("Node 2", "Content 2", None, vault_id, user_id)
    # Dieser Node wird nicht abgefragt
    database.create_node("Node 3", "Content 3", None, vault_id, user_id)

    node_ids_to_fetch = [node1.id, node2.id]

    # 2. ACT: Rufe die zu testende Funktion auf.
    result_nodes = database.get_nodes_by_ids(node_ids_to_fetch, vault_id, user_id)

    # 3. ASSERT: Überprüfe das Ergebnis.
    assert isinstance(result_nodes, list)
    assert len(result_nodes) == 2

    # Überprüfe, ob die richtigen Nodes zurückgegeben wurden (Reihenfolge ist nicht garantiert).
    result_titles = sorted([node['title'] for node in result_nodes])
    assert result_titles == ["Node 1", "Node 2"]
    assert 'content' in result_nodes[0] # Sicherstellen, dass der Inhalt dabei ist

# tests/test_database_nodes.py
# Fügen Sie diese beiden Tests zur Datei hinzu.

def test_get_content_for_nodes_with_empty_list(test_user_1_obj, test_vault_1_obj):
    """
    Testet den Randfall, dass get_content_for_nodes mit einer leeren
    Liste von IDs aufgerufen wird.
    """
    # ACT: Rufe die Funktion mit einer leeren Liste auf.
    result = database.get_content_for_nodes([], test_vault_1_obj.id, test_user_1_obj.id)

    # ASSERT: Erwarte die leere Standardantwort.
    assert result == {"titles": [], "content": ""}


def test_get_content_for_nodes_formats_correctly_and_preserves_order(test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_content_for_nodes die Inhalte korrekt formatiert
    und die Reihenfolge der übergebenen IDs beibehält.
    """
    # 1. ARRANGE: Erstelle Nodes.
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    node_b = database.create_node("Node B", "Content B", None, vault_id, user_id)
    node_a = database.create_node("Node A", "Content A", None, vault_id, user_id)

    # Wichtig: Die Reihenfolge der IDs ist nicht alphabetisch.
    # Die Funktion muss diese Reihenfolge beibehalten.
    ids_in_specific_order = [node_b.id, node_a.id]

    # 2. ACT: Rufe die Funktion auf.
    result = database.get_content_for_nodes(ids_in_specific_order, vault_id, user_id)

    # 3. ASSERT: Überprüfe die Struktur und den Inhalt.
    # a) Überprüfe die Titel in der korrekten Reihenfolge.
    assert result['titles'] == ["Node B", "Node A"]

    # b) Überprüfe den formatierten String.
    expected_content = (
        "--- START OF DOCUMENT: Node B ---\n"
        "Content B\n"
        "--- END OF DOCUMENT: Node B ---\n\n"
        "--- START OF DOCUMENT: Node A ---\n"
        "Content A\n"
        "--- END OF DOCUMENT: Node A ---"
    )
    assert result['content'] == expected_content

# tests/test_database_nodes.py
# Stellen Sie sicher, dass 'database' und 'Version' importiert sind.

def test_get_versions_for_node_ids_with_empty_list(test_user_1_obj, test_vault_1_obj):
    """
    Testet den Randfall, dass get_versions_for_node_ids mit einer leeren
    Liste von IDs aufgerufen wird.
    """
    # ACT & ASSERT: Der Aufruf muss eine leere Liste zurückgeben.
    versions = database.get_versions_for_node_ids([], test_vault_1_obj.id, test_user_1_obj.id)
    assert versions == []


def test_get_versions_for_node_ids_success(test_user_1_obj, test_vault_1_obj):
    """
    Testet den erfolgreichen Abruf von Versionsobjekten für gegebene Node-IDs.
    """
    # 1. ARRANGE: Erstelle einige Nodes.
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node1 = database.create_node("Node V1", "Content V1", None, vault_id, user_id)
    node2 = database.create_node("Node V2", "Content V2", None, vault_id, user_id)

    # 2. ACT: Rufe die Funktion mit den IDs der neuen Nodes auf.
    versions = database.get_versions_for_node_ids([node1.id, node2.id], vault_id, user_id)

    # 3. ASSERT: Überprüfe, ob die korrekten Version-Objekte zurückgegeben wurden.
    assert len(versions) == 2
    assert all(isinstance(v, Version) for v in versions)

    # Überprüfe den Inhalt zur Sicherheit (Reihenfolge nicht garantiert)
    contents = sorted([v.content for v in versions])
    assert contents == ["Content V1", "Content V2"]

def test_get_node_by_id_returns_full_version_history(test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_node_by_id die komplette und korrekt sortierte
    Versionshistorie eines Nodes zurückgibt.
    """
    # 1. ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # a) Erstelle den Node mit seiner ersten Version (V1)
    node = database.create_node(
        "History Test Node", "Content V1", None, vault_id, user_id
    )
    assert node.current_version == 1

    # b) Update den Node, um Version 2 zu erstellen.
    database.update_node(
        node.id, vault_id, user_id, content="Content V2"
    )

    # c) Update den Node erneut, um Version 3 zu erstellen.
    database.update_node(
        node.id, vault_id, user_id, content="Content V3"
    )

    # 2. ACT: Rufe den Node mit seiner vollständigen Historie ab.
    node_dict = database.get_node_by_id(node.id, vault_id, user_id)

    # 3. ASSERT
    # a) Überprüfe die Metadaten des Nodes.
    assert node_dict is not None
    assert node_dict['id'] == node.id
    assert node_dict['current_version'] == 3
    assert node_dict['content'] == "Content V3"  # Der Inhalt sollte der von der neuesten Version sein.

    # b) Überprüfe die Versionshistorie.
    assert 'versions' in node_dict
    versions_history = node_dict['versions']
    assert isinstance(versions_history, list)
    assert len(versions_history) == 3

    # c) Die entscheidende Prüfung: Ist die Historie korrekt und richtig sortiert?
    # get_node_by_id sollte absteigend nach Version sortieren (neueste zuerst).
    assert versions_history[0]['version'] == 3
    assert versions_history[0]['content'] == "Content V3"
    assert versions_history[0]['author'] == test_user_1_obj.display_name

    assert versions_history[1]['version'] == 2
    assert versions_history[1]['content'] == "Content V2"

    assert versions_history[2]['version'] == 1
    assert versions_history[2]['content'] == "Content V1"

# tests/test_database_nodes.py

def test_get_node_by_title_with_empty_title_returns_none(test_user_1_obj, test_vault_1_obj):
    """
    Testet den Randfall, dass get_node_by_title mit einem leeren oder None-Titel
    aufgerufen wird und None zurückgeben soll.
    """
    # 1. ARRANGE: Erstelle einen Node, damit die DB nicht leer ist.
    database.create_node("Some Node", "", None, test_vault_1_obj.id, test_user_1_obj.id)

    # 2. ACT & ASSERT
    # a) Test mit leerem String
    result_empty = database.get_node_by_title("", test_vault_1_obj.id, test_user_1_obj.id)
    assert result_empty is None

    # b) Test mit None
    result_none = database.get_node_by_title(None, test_vault_1_obj.id, test_user_1_obj.id)
    assert result_none is None


def test_get_node_by_title_finds_most_relevant_node(test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_node_by_title den relevantesten Node findet.
    "Relevantester" bedeutet hier: Eine exakte Übereinstimmung (case-insensitive)
    wird einer Teilübereinstimmung vorgezogen.
    """
    # 1. ARRANGE: Erstelle mehrere Nodes, die zur Suche passen könnten.
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Dieser Node enthält den Suchbegriff, ist aber keine exakte Übereinstimmung.
    database.create_node(
        "A Long Title With Apple", "Content A", None, vault_id, user_id
    )
    # Dieser Node ist die exakte (case-insensitive) Übereinstimmung.
    # Er wird später erstellt, um zu prüfen, ob die Reihenfolge der Erstellung egal ist.
    exact_match_node = database.create_node(
        "Apple", "Content B (Exact Match)", None, vault_id, user_id
    )
    # Dieser Node ist alphabetisch vor der exakten Übereinstimmung,
    # um zu prüfen, ob die Relevanz wichtiger ist als die alphabetische Sortierung.
    database.create_node(
        "An Apple A Day", "Content C", None, vault_id, user_id
    )

    # 2. ACT: Suche nach "apple" (kleingeschrieben).
    found_node_dict = database.get_node_by_title("apple", vault_id, user_id)

    # 3. ASSERT: Überprüfe, ob der exakte Treffer zurückgegeben wurde.
    assert found_node_dict is not None
    assert found_node_dict['id'] == exact_match_node.id
    assert found_node_dict['title'] == "Apple"
    assert found_node_dict['content'] == "Content B (Exact Match)"

# Ein konstanter, nicht existierender UUID für die Tests
NON_EXISTENT_NODE_ID = "00000000-0000-0000-0000-000000000000"

def test_update_non_existent_node_fails(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass der Versuch, einen nicht existierenden Node zu aktualisieren,
    einen ValueError auslöst.
    """
    with pytest.raises(ValueError, match="Node not found in the specified vault"):
        database.update_node(
            node_id=NON_EXISTENT_NODE_ID,
            vault_id=test_vault_1_obj.id,
            user_id=test_user_1_obj.id,
            content="some content"
        )

def test_rename_non_existent_node_fails(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass der Versuch, einen nicht existierenden Node umzubenennen,
    einen ValueError auslöst.
    """
    with pytest.raises(ValueError, match="Node not found in the specified vault"):
        database.rename_node(
            node_id=NON_EXISTENT_NODE_ID,
            new_title="New Title",
            vault_id=test_vault_1_obj.id,
            user_id=test_user_1_obj.id
        )

def test_delete_non_existent_node_fails(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass der Versuch, einen nicht existierenden Node zu löschen,
    einen ValueError auslöst.
    """
    with pytest.raises(ValueError, match="Node not found in the specified vault"):
        database.delete_node(
            node_id=NON_EXISTENT_NODE_ID,
            vault_id=test_vault_1_obj.id,
            user_id=test_user_1_obj.id
        )

def test_move_non_existent_node_fails(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass der Versuch, einen nicht existierenden Node zu verschieben,
    einen ValueError auslöst.
    """
    # Erstelle einen gültigen Parent als Ziel
    parent_node = database.create_node("Valid Parent", "", None, test_vault_1_obj.id, test_user_1_obj.id)

    with pytest.raises(ValueError, match="Node to move not found in the specified vault."):
        database.move_node(
            node_id=NON_EXISTENT_NODE_ID,
            new_parent_id=parent_node.id,
            vault_id=test_vault_1_obj.id,
            user_id=test_user_1_obj.id
        )

def test_move_node_to_non_existent_parent_fails(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass der Versuch, einen Node zu einem nicht existierenden
    Parent zu verschieben, einen ValueError auslöst.
    """
    # Erstelle einen gültigen Node, der bewegt werden soll
    node_to_move = database.create_node("Node to move", "", None, test_vault_1_obj.id, test_user_1_obj.id)

    with pytest.raises(ValueError, match="Target parent node not found in the specified vault."):
        database.move_node(
            node_id=node_to_move.id,
            new_parent_id=NON_EXISTENT_NODE_ID, # Ziel-Parent existiert nicht
            vault_id=test_vault_1_obj.id,
            user_id=test_user_1_obj.id
        )