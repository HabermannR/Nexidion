# tests/services/test_node_service.py
import pytest
from backend.services import node_service, vault_service
from backend.models import Node, Version, Vault


def test_get_content_for_nodes_success(db_session, test_user_1_obj):
    """
    Testet den Erfolgsfall für get_content_for_nodes.
    """
    # ARRANGE: Erstelle einen Vault und Nodes über die Services
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Test-Vault", user_id)
    vault_id = vault.id

    node1_dict = node_service.create_node("Titel Eins", "Inhalt von Node 1.", None, vault_id, user_id)
    node2_dict = node_service.create_node("Titel Zwei", "Inhalt von Node 2.", None, vault_id, user_id)
    node_service.create_node("Unerwünschter Node", "...", None, vault_id, user_id)

    node_ids_to_fetch = [node1_dict.id, node2_dict.id]

    # ACT: Rufe die zu testende Service-Funktion auf.
    result = node_service.get_content_for_nodes(
        node_ids=node_ids_to_fetch, vault_id=vault_id, user_id=user_id
    )

    # ASSERT: Überprüfe das Ergebnis.
    assert result["titles"] == ["Titel Eins", "Titel Zwei"]
    assert "Inhalt von Node 1." in result["content"]
    assert "Inhalt von Node 2." in result["content"]


def test_get_content_for_nodes_raises_value_error_on_empty_list(test_user_1_obj):
    """
    Testet, ob der Service einen ValueError bei einer leeren node_ids-Liste auslöst.
    """
    # ARRANGE: Wir brauchen einen Vault, um die Berechtigungsprüfung zu bestehen
    vault = vault_service.create_vault("Dummy Vault", test_user_1_obj.id)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="mindestens eine Node-ID angegeben werden"):
        node_service.get_content_for_nodes(
            node_ids=[], vault_id=vault.id, user_id=test_user_1_obj.id
        )


def test_get_content_for_nodes_raises_permission_error(test_user_1_obj, test_user_2_obj):
    """
    Testet, ob eine PermissionError ausgelöst wird, wenn ein User
    auf Nodes in einem fremden Vault zugreift.
    """
    # ARRANGE: Vault und Node gehören zu user1
    vault1 = vault_service.create_vault("Vault von User 1", test_user_1_obj.id)
    node1_dict = node_service.create_node("Geheimer Node", "Top Secret", None, vault1.id, test_user_1_obj.id)
    node1_id = node1_dict.id  # Extrahiere die ID.

    # ACT & ASSERT: user2 versucht, auf den Node von user1 zuzugreifen.
    with pytest.raises(PermissionError):
        node_service.get_content_for_nodes(
            node_ids=[node1_id], vault_id=vault1.id, user_id=test_user_2_obj.id  # Falscher Benutzer!
        )


def test_get_nodes_by_ids_success(test_user_1_obj):
    """
    Testet, ob get_nodes_by_ids die korrekten Nodes als Dictionaries zurückgibt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Test-Vault", user_id)
    vault_id = vault.id

    node1_dict = node_service.create_node("Node 1", "Content 1", None, vault_id, user_id)
    node2_dict = node_service.create_node("Node 2", "Content 2", None, vault_id, user_id)
    node_service.create_node("Node 3", "Content 3", None, vault_id, user_id)

    node_ids_to_fetch = [node1_dict.id, node2_dict.id]

    # ACT
    result_nodes = node_service.get_nodes_by_ids(node_ids_to_fetch, vault_id, user_id)

    # ASSERT
    assert len(result_nodes) == 2
    result_titles = sorted([node['title'] for node in result_nodes])
    assert result_titles == ["Node 1", "Node 2"]


def test_get_content_for_nodes_preserves_order(test_user_1_obj):
    """
    Testet, ob get_content_for_nodes die Reihenfolge der übergebenen IDs beibehält.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Order-Test Vault", user_id)
    vault_id = vault.id

    node_b_dict = node_service.create_node("Node B", "Content B", None, vault_id, user_id)
    node_a_dict = node_service.create_node("Node A", "Content A", None, vault_id, user_id)
    ids_in_specific_order = [node_b_dict.id, node_a_dict.id]

    # ACT
    result = node_service.get_content_for_nodes(ids_in_specific_order, vault_id, user_id)

    # ASSERT
    assert result['titles'] == ["Node B", "Node A"]


def test_get_nodes_by_ids_for_user(db_session, test_user_1_obj):
    """
    Testet, ob die Funktion die korrekten Node-Objekte mit den
    korrekten aktuellen Versionen zurückgibt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Node-Test Vault", user_id)
    vault_id = vault.id

    node1_dict = node_service.create_node("Node 1", "Content V1", None, vault_id, user_id)
    node2_dict = node_service.create_node("Node 2", "Content V2", None, vault_id, user_id)
    node1_id = node1_dict.id
    node2_id = node2_dict.id

    # Update node1 to create a second version
    node_service.update_node(node1_id, vault_id, user_id, content="Content V1.1")

    # ACT: Holen der *Node-Objekte*
    nodes_result = node_service.get_nodes_by_ids_for_user([node1_id, node2_id], vault_id, user_id)

    # ASSERT
    assert len(nodes_result) == 2
    result_map = {node.id: node for node in nodes_result}

    assert node1_id in result_map
    node1_from_result = result_map[node1_id]
    assert isinstance(node1_from_result, Node)
    assert node1_from_result.title == "Node 1"
    assert node1_from_result.current_version == 2
    assert node1_from_result.current_version_object.content == "Content V1.1"

    assert node2_id in result_map
    node2_from_result = result_map[node2_id]
    assert isinstance(node2_from_result, Node)
    assert node2_from_result.title == "Node 2"
    assert node2_from_result.current_version == 1
    assert node2_from_result.current_version_object.content == "Content V2"


def test_get_nodes_by_ids_for_user_permission_denied(test_user_1_obj, test_user_2_obj):
    """
    Testet, dass User 2 keine Nodes aus dem Vault von User 1 abrufen kann.
    """
    # ARRANGE
    vault1 = vault_service.create_vault("Vault von User 1", test_user_1_obj.id)
    node1_dict = node_service.create_node("Node 1", "...", None, vault1.id, test_user_1_obj.id)
    node1_id = node1_dict.id

    # ACT & ASSERT
    with pytest.raises(PermissionError):
        node_service.get_nodes_by_ids_for_user(
            node_ids=[node1_id], vault_id=vault1.id, user_id=test_user_2_obj.id
        )


def test_delete_node_reparents_children_to_grandparent(db_session, test_user_1_obj):
    """
    Testet, dass beim Löschen eines Nodes dessen Kinder an den "Großeltern-Node"
    angehängt werden (neues parent_id).
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Adoption Test Vault", user_id)
    vault_id = vault.id

    grandparent_node_dict = node_service.create_node("Grandparent", "...", None, vault_id, user_id)
    grandparent_id = grandparent_node_dict.id

    parent_node_to_delete_dict = node_service.create_node("Parent (to be deleted)", "...", grandparent_id, vault_id,
                                                          user_id)
    parent_id_to_delete = parent_node_to_delete_dict.id

    child_node_dict = node_service.create_node("Child", "...", parent_id_to_delete, vault_id, user_id)
    child_id = child_node_dict.id

    # Stelle den Zustand vor dem Löschen sicher
    child_node_before_delete = db_session.session.get(Node, child_id)
    assert child_node_before_delete.parent_id == parent_id_to_delete

    # ACT
    node_service.delete_node(parent_id_to_delete, vault_id, user_id)

    # ASSERT
    # 1. Der Parent-Node ist gelöscht
    deleted_node = db_session.session.get(Node, parent_id_to_delete)
    assert deleted_node is None

    # 2. Der Child-Node existiert noch
    reparented_child = db_session.session.get(Node, child_id)
    assert reparented_child is not None

    # 3. Der Child-Node hat jetzt den Grandparent als neuen Parent
    assert reparented_child.parent_id == grandparent_id


def test_get_full_node_tree_recursively(client, auth_headers_1, test_vault_1_obj, test_user_1_obj):
    """
    Testet, ob der Endpunkt GET /nodes/ die gesamte Baumstruktur korrekt,
    sortiert und ohne Inhalte der Kind-Elemente zurückgibt.
    """
    # ARRANGE
    # 1. Stelle explizit sicher, dass wir einen Root-Node haben, um einen IndexError zu vermeiden
    root_node_obj = node_service.create_node("Summary", "Root", None, test_vault_1_obj.id, test_user_1_obj.id)
    root_node_id = root_node_obj.id

    # 2. Erstelle Kind-Elemente
    node_service.create_node("Zebra Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)
    node_a_obj = node_service.create_node("Apple Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)

    node_service.create_node("Sub-Note 2", "Content", node_a_obj.id, test_vault_1_obj.id, test_user_1_obj.id)
    node_service.create_node("Sub-Note 1", "Content", node_a_obj.id, test_vault_1_obj.id, test_user_1_obj.id)

    # ACT
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1)

    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) > 0, "Die Liste der Nodes sollte nicht leer sein."

    # Suche unseren definierten Root-Node in der Antwort
    root_node_data = next((n for n in data if n['id'] == root_node_id), None)
    assert root_node_data is not None, "Root node wurde im Baum nicht gefunden."
    assert root_node_data['title'] == 'Summary'

    level_1_children = root_node_data['children']
    assert len(level_1_children) == 2
    # Alphabetische Sortierung prüfen
    assert level_1_children[0]['title'] == 'Apple Folder'
    assert level_1_children[1]['title'] == 'Zebra Folder'

    apple_folder_data = level_1_children[0]
    level_2_children = apple_folder_data['children']
    assert len(level_2_children) == 2
    assert level_2_children[0]['title'] == 'Sub-Note 1'
    assert level_2_children[1]['title'] == 'Sub-Note 2'

    # Prüfen, ob der Content aus Performancegründen (defer) weggelassen wurde
    assert 'content' not in level_1_children[0]
    assert 'content' not in level_2_children[0]


def test_get_single_node_api_returns_correct_structure(client, auth_headers_1, test_vault_1_obj, test_user_1_obj):
    """
    Testet den API-Endpunkt GET /.../nodes/{node_id} und überprüft die JSON-Struktur.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_dict = node_service.create_node("API Test Node", "V1", None, vault_id, user_id)
    node_id = node_dict.id
    node_service.update_node(node_id, vault_id, user_id, content="V2")

    # ACT: Rufe den API-Endpunkt auf
    response = client.get(f'/api/vaults/{vault_id}/nodes/{node_id}', headers=auth_headers_1)

    # ASSERT
    assert response.status_code == 200
    assert response.content_type == 'application/json'
    data = response.get_json()
    assert isinstance(data, dict)
    assert data['id'] == node_id
    assert data['title'] == "API Test Node"
    assert data['content'] == "V2"
    assert 'versions' not in data
    assert data['has_versions'] is True
    assert data['version_count'] == 2


def test_get_node_versions_returns_correct_data(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_node_versions die korrekte Liste von Versionen
    für einen Node zurückgibt (als Stubs zur Performance-Optimierung).
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    node_dict = node_service.create_node("Versions-Test-Node", "Inhalt V1", None, vault_id, user_id)
    node_id = node_dict.id
    node_service.update_node(node_id, vault_id, user_id, content="Inhalt V2")
    node_service.update_node(node_id, vault_id, user_id, content="Inhalt V3")

    # ACT
    versions_list = node_service.get_node_versions(node_id, vault_id, user_id)

    # ASSERT
    assert versions_list is not None
    assert len(versions_list) == 3
    assert versions_list[0]['version'] == 3

    # Da wir nun hochoptimierte Stubs zurückgeben, darf 'content' nicht mehr vorhanden sein.
    assert versions_list[0].get('is_stub') is True
    assert 'content' not in versions_list[0]

    assert versions_list[0]['author_name'] == test_user_1_obj.display_name


def test_get_node_versions_for_nonexistent_node_returns_none(test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_node_versions None zurückgibt, wenn die Node-ID nicht existiert.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    non_existent_node_id = "abc-123-def-456"

    # ACT
    result = node_service.get_node_versions(non_existent_node_id, vault_id, user_id)

    # ASSERT
    assert result is None


def test_create_node_sets_default_icon(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob beim Erstellen eines Nodes ohne Angabe eines Icons
    das korrekte Standard-Icon gesetzt wird.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # ACT
    # Wir rufen create_node auf, OHNE ein Icon anzugeben.
    new_node_obj = node_service.create_node(
        title="Node mit Standard-Icon",
        content="",
        parent_id=None,
        vault_id=vault_id,
        author_id=user_id
    )

    # ASSERT
    assert hasattr(new_node_obj, 'icon'), "Das Node-Objekt sollte ein 'icon'-Attribut haben."
    assert new_node_obj.icon == "bxs-file-doc"  # Überprüfe gegen den Standardwert

    # Optional: Prüfe direkt in der Datenbank
    node_from_db = db_session.session.get(Node, new_node_obj.id)
    assert node_from_db.icon == "bxs-file-doc"


def test_update_node_icon_success(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet den Erfolgsfall: Das Icon eines Nodes wird korrekt geändert.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Erstelle einen Node. Er wird das Standard-Icon "bxs-file-doc" haben.
    node_obj = node_service.create_node("Node zum Icon-Test", "", None, vault_id, user_id)
    node_id = node_obj.id

    new_icon = "bxs-bulb"  # Ein anderes, gültiges Icon.

    # ACT
    # Rufe die zu testende Funktion auf.
    updated_node_obj = node_service.update_node_icon(node_id, vault_id, user_id, new_icon)

    # ASSERT
    # 1. Die Funktion gibt das aktualisierte Node-OBJEKT zurück.
    assert isinstance(updated_node_obj, Node)
    assert updated_node_obj.id == node_id
    assert updated_node_obj.icon == new_icon

    # 2. Überprüfe zur Sicherheit auch direkt in der Datenbank.
    node_from_db = db_session.session.get(Node, node_id)
    assert node_from_db.icon == new_icon


def test_update_node_icon_to_none(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob das Icon eines Nodes auf None (NULL in der DB) gesetzt werden kann.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Node zum Icon-Entfernen", "", None, vault_id, user_id)
    node_id = node_obj.id

    # Stelle sicher, dass anfangs ein Icon da ist.
    assert node_obj.icon is not None

    # ACT
    updated_node_obj = node_service.update_node_icon(node_id, vault_id, user_id, None)

    # ASSERT
    assert updated_node_obj.icon is None
    node_from_db = db_session.session.get(Node, node_id)
    assert node_from_db.icon is None


def test_update_node_icon_with_invalid_value_raises_error(test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass ein ValueError bei einem ungültigen Icon-String ausgelöst wird.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Node mit ungültigem Icon", "", None, vault_id, user_id)
    node_id = node_obj.id
    invalid_icon = "dies-ist-kein-gueltiges-icon"

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Invalid icon value"):
        node_service.update_node_icon(node_id, vault_id, user_id, invalid_icon)


def test_update_node_content_creates_new_version(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob eine reine Inhaltsänderung eine neue Version erstellt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Erstelle einen Node. Er hat jetzt Version 1.
    node_obj = node_service.create_node("Titel bleibt gleich", "Inhalt V1", None, vault_id, user_id)
    node_id = node_obj.id

    # Hole den initialen Node aus der DB, um den Zustand zu prüfen.
    initial_node = db_session.session.get(Node, node_id)
    assert initial_node.current_version == 1

    # ACT
    # Ändere NUR den Inhalt. Die Methode gibt jetzt ein Objekt zurück.
    updated_node_obj = node_service.update_node(
        node_id=node_id,
        vault_id=vault_id,
        user_id=user_id,
        content="Inhalt V2 (neu)"
    )

    # ASSERT
    # 1. Das zurückgegebene Objekt sollte die neue Version widerspiegeln.
    assert updated_node_obj.current_version == 2
    assert updated_node_obj.current_version_object.content == "Inhalt V2 (neu)"
    assert updated_node_obj.current_version_object.title == "Titel bleibt gleich"

    # 2. Überprüfe direkt in der Datenbank.
    node_from_db = db_session.session.get(Node, node_id)
    assert node_from_db.current_version == 2
    assert node_from_db.current_version_object.content == "Inhalt V2 (neu)"

    # 3. Es sollten jetzt zwei Versionen in der DB existieren.
    version_count = db_session.session.query(Version).filter_by(node_id=node_id).count()
    assert version_count == 2


def test_update_node_title_creates_new_version(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob eine reine Titeländerung eine neue Version erstellt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Alter Titel", "Inhalt bleibt gleich", None, vault_id, user_id)
    node_id = node_obj.id

    initial_node = db_session.session.get(Node, node_id)
    assert initial_node.current_version == 1

    # ACT
    # Ändere NUR den Titel.
    updated_node_obj = node_service.update_node(
        node_id=node_id,
        vault_id=vault_id,
        user_id=user_id,
        title="Neuer Titel"
    )

    # ASSERT
    assert updated_node_obj.current_version == 2
    assert updated_node_obj.current_version_object.title == "Neuer Titel"
    assert updated_node_obj.current_version_object.content == "Inhalt bleibt gleich"

    node_from_db = db_session.session.get(Node, node_id)
    assert node_from_db.current_version == 2
    assert node_from_db.current_version_object.title == "Neuer Titel"

    version_count = db_session.session.query(Version).filter_by(node_id=node_id).count()
    assert version_count == 2


def test_update_node_icon_does_not_create_new_version(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass eine reine Icon-Änderung KEINE neue Version erstellt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Node für Icon-Test", "Inhalt V1", None, vault_id, user_id)
    node_id = node_obj.id

    initial_node = db_session.session.get(Node, node_id)
    assert initial_node.current_version == 1

    # ACT
    # Rufe die separate Funktion zum Ändern des Icons auf.
    node_service.update_node_icon(
        node_id=node_id,
        vault_id=vault_id,
        user_id=user_id,
        icon="bxs-archive"  # Ein neues Icon
    )

    # ASSERT
    # 1. Überprüfe den Node in der Datenbank.
    node_from_db = db_session.session.get(Node, node_id)
    assert node_from_db.icon == "bxs-archive"  # Das Icon wurde geändert.

    # 2. ABER: Die Version ist immer noch 1.
    assert node_from_db.current_version == 1

    # 3. Es existiert nur EINE Version in der Datenbank. Das ist der entscheidende Test.
    version_count = db_session.session.query(Version).filter_by(node_id=node_id).count()
    assert version_count == 1


def test_cannot_delete_root_node(db_session, test_user_1_obj):
    """
    Testet, dass der Haupt-Node (Root Node mit parent_id=None) eines Vaults
    NICHT gelöscht werden kann.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Protected Root Vault", user_id)
    vault_id = vault.id

    # Erstelle einen Top-Level Node (parent_id = None)
    root_node_obj = node_service.create_node("Vault Summary", "Root Content", None, vault_id, user_id)

    # ACT & ASSERT
    # Wir erwarten, dass der Service das Löschen aktiv durch einen PermissionError unterbindet
    with pytest.raises(PermissionError, match="The root summary node cannot be deleted"):
        node_service.delete_node(root_node_obj.id, vault_id, user_id)


class TestInternalLinkingService:
    """Eine Klasse, um alle Service-Tests für interne Links zu gruppieren."""

    def test_search_for_autocomplete_service(self, db_session, test_user_1_obj):
        """Testet die Kernlogik der Autocomplete-Suche im Service."""
        # ARRANGE
        user_id = test_user_1_obj.id
        vault = vault_service.create_vault("Search-Test Vault", user_id)
        vault_id = vault.id

        node_service.create_node("Final Fantasy VII", "", None, vault_id, user_id)
        node_service.create_node("Final Fantasy X", "", None, vault_id, user_id)
        node_service.create_node("Chrono Trigger", "", None, vault_id, user_id)

        # ACT
        results = node_service.search_nodes_for_autocomplete("Final", vault_id, user_id)

        # ASSERT
        assert len(results) == 2
        titles = {item['title'] for item in results}
        assert "Final Fantasy VII" in titles
        assert "Final Fantasy X" in titles
        assert "id" in results[0]  # Stelle sicher, dass das Format stimmt

    def test_search_for_autocomplete_is_case_insensitive(self, db_session, test_user_1_obj):
        """Stellt sicher, dass die Service-Suche case-insensitive ist."""
        user_id = test_user_1_obj.id
        vault = vault_service.create_vault("Case-Test Vault", user_id)
        vault_id = vault.id

        node_service.create_node("Ein Test mit GROSSBUCHSTABEN", "", None, vault_id, user_id)

        results = node_service.search_nodes_for_autocomplete("grossbuchstaben", vault_id, user_id)

        assert len(results) == 1
        assert results[0]['title'] == "Ein Test mit GROSSBUCHSTABEN"

    def test_search_for_autocomplete_respects_vault_boundaries(self, db_session, test_user_1_obj, test_user_2_obj):
        """Stellt sicher, dass die Suche nur im angegebenen Vault sucht."""
        user1_id, user2_id = test_user_1_obj.id, test_user_2_obj.id
        vault1 = vault_service.create_vault("Vault 1", user1_id)
        vault2 = vault_service.create_vault("Vault 2", user2_id)

        # Beide User erstellen einen Node mit ähnlichem Titel in ihrem jeweiligen Vault
        node_service.create_node("Gemeinsamer Titel", "", None, vault1.id, user1_id)
        node_service.create_node("Gemeinsamer Titel", "", None, vault2.id, user2_id)

        # ACT: Suche als User 1 im Vault 1
        results = node_service.search_nodes_for_autocomplete("Gemeinsamer", vault1.id, user1_id)

        # ASSERT: Es sollte nur ein Ergebnis aus Vault 1 gefunden werden
        assert len(results) == 1

        # Überprüfe den Node, um sicherzugehen, dass es der richtige ist (optional, aber gut)
        node_id = results[0]['id']
        node_from_db = db_session.session.get(Node, node_id)
        assert node_from_db.vault_id == vault1.id

    def test_resolve_link_targets_service_mixed_scenarios(self, db_session, test_user_1_obj):
        """
        Ein umfassender Service-Test für `resolve_link_targets` mit allen Szenarien.
        """
        # ARRANGE
        user_id = test_user_1_obj.id
        vault = vault_service.create_vault("Resolve-Test Vault", user_id)
        vault_id = vault.id

        # 1. Eindeutiger starker Link
        strong_node = node_service.create_node("Starker Link", "", None, vault_id, user_id)
        # 2. Eindeutiger schwacher Link
        weak_node = node_service.create_node("Schwacher Link", "", None, vault_id, user_id)
        # 3. Mehrdeutiger schwacher Link
        node_service.create_node("Mehrdeutig", "", None, vault_id, user_id)
        node_service.create_node("Mehrdeutig", "", None, vault_id, user_id)
        # 4. Nicht existierende Ziele
        unresolved_uuid = "00000000-1111-2222-3333-444444444444"
        unresolved_title = "Diesen Titel gibt es nicht"

        targets = [
            strong_node.id,
            "Schwacher Link",
            "Mehrdeutig",
            unresolved_uuid,
            unresolved_title
        ]

        # ACT
        results = node_service.resolve_link_targets(targets, vault_id, user_id)

        # ASSERT
        assert isinstance(results, dict)

        # 1. Starker Link -> resolved
        assert results[strong_node.id]['status'] == 'resolved'
        assert results[strong_node.id]['node']['id'] == strong_node.id

        # 2. Schwacher Link -> resolved
        assert results["Schwacher Link"]['status'] == 'resolved'
        assert results["Schwacher Link"]['node']['id'] == weak_node.id

        # 3. Mehrdeutiger Link -> ambiguous
        assert results["Mehrdeutig"]['status'] == 'ambiguous'
        assert results["Mehrdeutig"]['matchCount'] == 2

        # 4. Nicht gefundene Links -> unresolved
        assert results[unresolved_uuid]['status'] == 'unresolved'
        assert results[unresolved_title]['status'] == 'unresolved'

    def test_resolve_link_targets_permission_error(self, db_session, test_user_1_obj, test_user_2_obj):
        """Testet, dass die Funktion eine PermissionError auslöst, wenn der falsche User anfragt."""
        user1_id, user2_id = test_user_1_obj.id, test_user_2_obj.id
        vault1 = vault_service.create_vault("Permission Test Vault", user1_id)

        node = node_service.create_node("Geheimer Node", "", None, vault1.id, user1_id)

        with pytest.raises(PermissionError):
            node_service.resolve_link_targets([node.id], vault1.id, user2_id)

    def test_resolve_link_targets_handles_case_insensitivity(self, db_session, test_user_1_obj):
        """Stellt sicher, dass die Titelauflösung case-insensitive ist."""
        user_id = test_user_1_obj.id
        vault = vault_service.create_vault("Case-Insensitive-Resolve Vault", user_id)
        vault_id = vault.id

        node = node_service.create_node("Ein Titel mit Case", "", None, vault_id, user_id)

        # ACT: Suche mit kleingeschriebenem Titel
        results = node_service.resolve_link_targets(["ein titel mit case"], vault_id, user_id)

        # ASSERT
        assert results["ein titel mit case"]['status'] == 'resolved'
        assert results["ein titel mit case"]['node']['id'] == node.id


# ========================================================================
# Tests für AI Summary, Version Loading & Fulltext Search (Service)
# ========================================================================

def test_update_node_ai_summary_success(db_session, test_user_1_obj, test_vault_1_obj):
    """Testet das erfolgreiche Aktualisieren der AI-Summary im Service."""
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("AI Node", "Content", None, vault_id, user_id)

    updated_node = node_service.update_node_ai_summary(node_obj.id, vault_id, user_id,
                                                       "Dies ist eine KI Zusammenfassung.")

    assert updated_node.ai_summary == "Dies ist eine KI Zusammenfassung."
    # Direkt in der DB prüfen
    db_node = db_session.session.get(Node, node_obj.id)
    assert db_node.ai_summary == "Dies ist eine KI Zusammenfassung."


def test_get_version_by_id_success(db_session, test_user_1_obj, test_vault_1_obj):
    """Testet das Abrufen einer spezifischen Version via Service."""
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    node_obj = node_service.create_node("Titel", "Inhalt V1", None, vault_id, user_id)
    node_service.update_node(node_obj.id, vault_id, user_id, content="Inhalt V2")

    # Hole alle Versionen (als Stubs), um die echte Versions-ID zu bekommen
    versions = node_service.get_node_versions(node_obj.id, vault_id, user_id)
    v2_id = versions[0]['id']  # Angenommen, die neueste Version steht oben

    # Hole das volle Versions-Objekt
    full_version = node_service.get_version_by_id(v2_id, node_obj.id, vault_id, user_id)

    assert full_version is not None
    assert full_version['content'] == "Inhalt V2"
    assert full_version.get('is_stub') is not True  # Sollte das vollständige Objekt sein


def test_search_nodes_fulltext_matches_all_fields(db_session, test_user_1_obj, test_vault_1_obj):
    """Testet, ob die Volltextsuche Titel, Content und AI-Summary durchsucht."""
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Node 1: Treffer im Titel
    node_service.create_node("EinzigartigerTitel", "Nichts", None, vault_id, user_id)
    # Node 2: Treffer im Content
    node_service.create_node("Normal", "Hier steht das Wort EinzigartigerContent", None, vault_id, user_id)
    # Node 3: Treffer in der AI Summary
    node3 = node_service.create_node("Normal 2", "Nichts", None, vault_id, user_id)
    node_service.update_node_ai_summary(node3.id, vault_id, user_id, "Enthält EinzigartigeSummary")

    # ACT & ASSERT
    res_title = node_service.search_nodes_fulltext("EinzigartigerTitel", vault_id, user_id, 10)
    assert len(res_title) == 1

    res_content = node_service.search_nodes_fulltext("EinzigartigerContent", vault_id, user_id, 10)
    assert len(res_content) == 1

    res_summary = node_service.search_nodes_fulltext("EinzigartigeSummary", vault_id, user_id, 10)
    assert len(res_summary) == 1


def test_search_nodes_fulltext_respects_limit(db_session, test_user_1_obj, test_vault_1_obj):
    """Prüft, ob das Limit bei der Volltextsuche greift."""
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    for i in range(5):
        node_service.create_node(f"LimitTest {i}", "Content", None, vault_id, user_id)

    results = node_service.search_nodes_fulltext("LimitTest", vault_id, user_id, limit=3)
    assert len(results) == 3


# ========================================================================
# Tests für historische Versionen in get_node_by_id (Service)
# ========================================================================

def test_get_node_by_id_patches_historical_version_correctly(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass bei Anforderung einer alten Version das Node-Dictionary
    mit den Daten der alten Version überschrieben wird (inkl. AI Summary Reset).
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # 1. Erstelle V1
    node_obj = node_service.create_node("Titel V1", "Inhalt V1", None, vault_id, user_id)
    node_id = node_obj.id

    # 2. Erstelle V2 (Update)
    node_service.update_node(node_id, vault_id, user_id, title="Titel V2", content="Inhalt V2")

    # 3. Füge V2 eine KI-Zusammenfassung hinzu
    node_service.update_node_ai_summary(node_id, vault_id, user_id, "Moderne KI Zusammenfassung")

    # ACT: Frage explizit nach Version 1
    result = node_service.get_node_by_id(node_id, vault_id, user_id, target_version=1)

    # ASSERT
    assert result is not None
    # Das Dictionary sollte auf V1 gepatcht sein
    assert result['title'] == "Titel V1"
    assert result['content'] == "Inhalt V1"
    assert result['version'] == 1

    # WICHTIG: Die KI-Zusammenfassung muss für historische Versionen genullt werden!
    assert result['ai_summary'] is None
    assert result['summary_is_current'] is False


def test_get_node_by_id_with_current_version_skips_patching(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass die Patching-Logik übersprungen wird, wenn die angefragte
    Version der aktuellen Version entspricht (node.current_version != target_version ist False).
    """
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Titel V1", "Inhalt V1", None, vault_id, user_id)
    node_service.update_node_ai_summary(node_obj.id, vault_id, user_id, "Summary V1")

    # ACT: Frage nach V1 (welches die aktuelle Version ist)
    result = node_service.get_node_by_id(node_obj.id, vault_id, user_id, target_version=1)

    # ASSERT
    assert result['title'] == "Titel V1"
    assert result['version'] == 1
    # Da es die aktuelle Version ist, darf die AI-Summary nicht genullt werden
    assert result['ai_summary'] == "Summary V1"


def test_get_node_by_id_raises_value_error_if_version_not_found(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass ein ValueError geworfen wird, wenn eine spezifische Version
    angefragt wird, die nicht in der Datenbank existiert.
    """
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node_obj = node_service.create_node("Einziger Titel", "Inhalt", None, vault_id, user_id)

    # ACT & ASSERT: Frage nach Version 99, die nicht existiert
    with pytest.raises(ValueError, match="Version not found"):
        node_service.get_node_by_id(node_obj.id, vault_id, user_id, target_version=99)