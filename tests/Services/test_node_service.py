# tests/services/test_node_service.py

import pytest
from backend.services import node_service, vault_service
from backend.models import Node, Version


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

    # ### HINWEIS ###: db_session.session.refresh() ist nicht mehr nötig und würde
    # bei einem Dictionary einen Fehler werfen. Wir können es einfach entfernen.

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


def test_delete_top_level_node_makes_children_top_level(db_session, test_user_1_obj):
    """
    Testet den Randfall: Wenn ein Top-Level-Node gelöscht wird,
    werden seine Kinder ebenfalls zu Top-Level-Nodes (parent_id = None).
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Top-Level Delete Test", user_id)
    vault_id = vault.id

    top_level_node_to_delete_dict = node_service.create_node("Top-Level (to be deleted)", "...", None, vault_id,
                                                             user_id)
    top_level_id_to_delete = top_level_node_to_delete_dict.id

    child_node_dict = node_service.create_node("Child", "...", top_level_id_to_delete, vault_id, user_id)
    child_id = child_node_dict.id

    # Stelle den Zustand vor dem Löschen sicher
    child_node_before_delete = db_session.session.get(Node, child_id)
    assert child_node_before_delete.parent_id == top_level_id_to_delete

    # ACT
    node_service.delete_node(top_level_id_to_delete, vault_id, user_id)

    # ASSERT
    deleted_node = db_session.session.get(Node, top_level_id_to_delete)
    assert deleted_node is None

    new_top_level_child = db_session.session.get(Node, child_id)
    assert new_top_level_child is not None
    assert new_top_level_child.parent_id is None


def test_get_full_node_tree_recursively(client, auth_headers_1, test_vault_1_obj, test_user_1_obj):
    """
    Testet, ob der Endpunkt GET /nodes/ die gesamte Baumstruktur korrekt,
    sortiert und ohne Inhalte der Kind-Elemente zurückgibt.
    """
    # ARRANGE
    tree_res = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1)
    root_node_id = tree_res.json[0]['id']

    node_service.create_node("Zebra Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)
    node_a_dict = node_service.create_node("Apple Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)
    node_a_id = node_a_dict.id

    node_service.create_node("Sub-Note 2", "Content", node_a_id, test_vault_1_obj.id, test_user_1_obj.id)
    node_service.create_node("Sub-Note 1", "Content", node_a_id, test_vault_1_obj.id, test_user_1_obj.id)

    # ACT
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1)

    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    root_node_data = data[0]
    assert root_node_data['title'] == 'Summary'

    level_1_children = root_node_data['children']
    assert len(level_1_children) == 2
    assert level_1_children[0]['title'] == 'Apple Folder'
    assert level_1_children[1]['title'] == 'Zebra Folder'

    apple_folder_data = level_1_children[0]
    level_2_children = apple_folder_data['children']
    assert len(level_2_children) == 2
    assert level_2_children[0]['title'] == 'Sub-Note 1'
    assert level_2_children[1]['title'] == 'Sub-Note 2'

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
    für einen Node zurückgibt, sortiert nach neuester zuerst.
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
    assert versions_list[0]['content'] == "Inhalt V3"
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
    new_node_dict = node_service.create_node(
        title="Node mit Standard-Icon",
        content="",
        parent_id=None,
        vault_id=vault_id,
        author_id=user_id
    )

    # ASSERT
    assert hasattr(new_node_dict, 'icon'), "Das Node-Objekt sollte ein 'icon'-Attribut haben."
    assert new_node_dict.icon == "bxs-file-doc" # Überprüfe gegen den Standardwert

    # Optional: Prüfe direkt in der Datenbank
    node_from_db = db_session.session.get(Node, new_node_dict.id)
    assert node_from_db.icon == "bxs-file-doc"

def test_update_node_icon_success(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet den Erfolgsfall: Das Icon eines Nodes wird korrekt geändert.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Erstelle einen Node. Er wird das Standard-Icon "bxs-file-doc" haben.
    node_dict = node_service.create_node("Node zum Icon-Test", "", None, vault_id, user_id)
    node_id = node_dict.id

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
    node_dict = node_service.create_node("Node zum Icon-Entfernen", "", None, vault_id, user_id)
    node_id = node_dict.id

    # Stelle sicher, dass anfangs ein Icon da ist.
    assert node_dict.icon is not None

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
    node_dict = node_service.create_node("Node mit ungültigem Icon", "", None, vault_id, user_id)
    node_id = node_dict.id
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
    node_dict = node_service.create_node("Titel bleibt gleich", "Inhalt V1", None, vault_id, user_id)
    node_id = node_dict.id

    # Hole den initialen Node aus der DB, um den Zustand zu prüfen.
    initial_node = db_session.session.get(Node, node_id)
    assert initial_node.current_version == 1

    # ACT
    # Ändere NUR den Inhalt.
    updated_node_dict = node_service.update_node(
        node_id=node_id,
        vault_id=vault_id,
        user_id=user_id,
        content="Inhalt V2 (neu)"
    )

    # ASSERT
    # 1. Das zurückgegebene Dictionary sollte die neue Version widerspiegeln.
    assert updated_node_dict['current_version'] == 2
    assert updated_node_dict['content'] == "Inhalt V2 (neu)"
    assert updated_node_dict['title'] == "Titel bleibt gleich"  # Titel unverändert

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
    node_dict = node_service.create_node("Alter Titel", "Inhalt bleibt gleich", None, vault_id, user_id)
    node_id = node_dict.id

    initial_node = db_session.session.get(Node, node_id)
    assert initial_node.current_version == 1

    # ACT
    # Ändere NUR den Titel.
    updated_node_dict = node_service.update_node(
        node_id=node_id,
        vault_id=vault_id,
        user_id=user_id,
        title="Neuer Titel"
    )

    # ASSERT
    assert updated_node_dict['current_version'] == 2
    assert updated_node_dict['title'] == "Neuer Titel"
    assert updated_node_dict['content'] == "Inhalt bleibt gleich"

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
    node_dict = node_service.create_node("Node für Icon-Test", "Inhalt V1", None, vault_id, user_id)
    node_id = node_dict.id

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