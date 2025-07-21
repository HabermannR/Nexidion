# tests/services/test_node_service.py

import pytest
from backend.services import node_service, vault_service
from backend.models import Node

def test_get_content_for_nodes_success(db_session, test_user_1_obj):
    """
    Testet den Erfolgsfall für get_content_for_nodes.
    """
    # ARRANGE: Erstelle einen Vault und Nodes über die Services
    user_id = test_user_1_obj.id
    # Wir erstellen den Vault direkt, um eine vault_id zu haben
    vault = vault_service.create_vault("Test-Vault", user_id)
    vault_id = vault.id

    node1 = node_service.create_node("Titel Eins", "Inhalt von Node 1.", None, vault_id, user_id)
    node2 = node_service.create_node("Titel Zwei", "Inhalt von Node 2.", None, vault_id, user_id)
    # Dieser Node wird nicht abgefragt und sollte nicht im Ergebnis erscheinen.
    node_service.create_node("Unerwünschter Node", "...", None, vault_id, user_id)

    node_ids_to_fetch = [node1.id, node2.id]

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
    with pytest.raises(ValueError, match="mindestens eine Node-ID"):
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
    node1 = node_service.create_node("Geheimer Node", "Top Secret", None, vault1.id, test_user_1_obj.id)

    # ACT & ASSERT: user2 versucht, auf den Node von user1 zuzugreifen.
    with pytest.raises(PermissionError):
        node_service.get_content_for_nodes(
            node_ids=[node1.id], vault_id=vault1.id, user_id=test_user_2_obj.id  # Falscher Benutzer!
        )


def test_get_nodes_by_ids_success(test_user_1_obj):
    """
    Testet, ob get_nodes_by_ids die korrekten Nodes als Dictionaries zurückgibt.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Test-Vault", user_id)
    vault_id = vault.id

    node1 = node_service.create_node("Node 1", "Content 1", None, vault_id, user_id)
    node2 = node_service.create_node("Node 2", "Content 2", None, vault_id, user_id)
    node_service.create_node("Node 3", "Content 3", None, vault_id, user_id)

    node_ids_to_fetch = [node1.id, node2.id]

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

    node_b = node_service.create_node("Node B", "Content B", None, vault_id, user_id)
    node_a = node_service.create_node("Node A", "Content A", None, vault_id, user_id)
    ids_in_specific_order = [node_b.id, node_a.id]

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

    node1 = node_service.create_node("Node 1", "Content V1", None, vault_id, user_id)
    node2 = node_service.create_node("Node 2", "Content V2", None, vault_id, user_id)

    # Update node1 to create a second version
    node_service.update_node(node1.id, vault_id, user_id, content="Content V1.1")

    # Holen Sie sich das aktualisierte node1-Objekt aus der DB, um sicherzustellen, dass wir den
    # korrekten `current_version` Wert haben.
    db_session.session.refresh(node1)

    # ACT: Holen der *Node-Objekte*
    # --- ÄNDERUNG HIER ---
    nodes_result = node_service.get_nodes_by_ids_for_user([node1.id, node2.id], vault_id, user_id)

    # ASSERT
    assert len(nodes_result) == 2

    # Mappe die Ergebnisse für einfachere Überprüfung
    result_map = {node.id: node for node in nodes_result}

    # Überprüfe Node 1
    assert node1.id in result_map
    node1_from_result = result_map[node1.id]
    assert isinstance(node1_from_result, Node)
    assert node1_from_result.title == "Node 1"
    # Wichtig: Prüfen, ob die aktuelle Version korrekt ist (sollte 2 sein)
    assert node1_from_result.current_version == 2
    assert node1_from_result.current_version_object is not None
    assert node1_from_result.current_version_object.content == "Content V1.1"

    # Überprüfe Node 2
    assert node2.id in result_map
    node2_from_result = result_map[node2.id]
    assert isinstance(node2_from_result, Node)
    assert node2_from_result.title == "Node 2"
    # Wichtig: Prüfen, ob die aktuelle Version korrekt ist (sollte 1 sein)
    assert node2_from_result.current_version == 1
    assert node2_from_result.current_version_object is not None
    assert node2_from_result.current_version_object.content == "Content V2"


def test_get_nodes_by_ids_for_user_permission_denied(test_user_1_obj, test_user_2_obj):
    """
    Testet, dass User 2 keine Nodes aus dem Vault von User 1 abrufen kann.
    """
    # ARRANGE
    vault1 = vault_service.create_vault("Vault von User 1", test_user_1_obj.id)
    node1 = node_service.create_node("Node 1", "...", None, vault1.id, test_user_1_obj.id)

    # ACT & ASSERT
    with pytest.raises(PermissionError):
        node_service.get_nodes_by_ids_for_user(
            node_ids=[node1.id], vault_id=vault1.id, user_id=test_user_2_obj.id  # Falscher User
        )


def test_get_nodes_as_tree_handles_orphaned_nodes(test_user_1_obj, db_session):
    """
    Testet den Edge Case, bei dem ein Node einen `parent_id` hat,
    dieser Parent-Node aber nicht mehr in der Datenbank existiert (ein "Waise").
    Dieser Test deckt den `else`-Zweig in der Baum-Erstellungs-Schleife ab.
    """
    # ARRANGE
    user = test_user_1_obj
    vault = vault_service.create_vault("Orphan Test Vault", user.id)

    # Erstelle einen Parent und einen Child
    parent = node_service.create_node("Parent", "...", None, vault.id, user.id)
    child = node_service.create_node("Child", "...", parent.id, vault.id, user.id)

    # Lösche jetzt den Parent direkt aus der DB, um einen Waisen zu erzeugen
    db_session.session.delete(parent)
    db_session.session.commit()

    # ACT
    tree = node_service.get_nodes_as_tree(vault.id, user.id)

    # ASSERT
    # Der Baum sollte den Root-Node und den verwaisten Child-Node enthalten.
    # Der Child wird als Top-Level-Node behandelt, da sein Parent fehlt.
    assert len(tree) == 2
    titles = sorted([node['title'] for node in tree])
    assert titles == ["Child", "Summary"]


def test_get_nodes_as_tree_sorts_children_correctly(test_user_1_obj, db_session):
    """
    Testet, ob die Kind-Elemente in der Baumstruktur korrekt alphabetisch sortiert werden.
    Dieser Test deckt den `if 'children' in node:` Zweig in der rekursiven Sortierfunktion ab.
    """
    # ARRANGE
    user = test_user_1_obj
    vault = vault_service.create_vault("Sort Test Vault", user.id)

    # Erstelle den Root-Node (kommt von create_vault)
    root_node_db = node_service.get_nodes_as_list(vault.id, user.id)[0]

    # Erstelle Kinder in umgekehrter alphabetischer Reihenfolge
    node_service.create_node("Z-Node", "...", root_node_db['id'], vault.id, user.id)
    node_service.create_node("B-Node", "...", root_node_db['id'], vault.id, user.id)
    node_service.create_node("A-Node", "...", root_node_db['id'], vault.id, user.id)

    # ACT
    tree = node_service.get_nodes_as_tree(vault.id, user.id)

    # ASSERT
    # Es gibt nur einen Top-Level-Node (den Root "Summary")
    assert len(tree) == 1

    # Die Kinder dieses Nodes müssen sortiert sein
    root_node_with_children = tree[0]
    assert 'children' in root_node_with_children
    assert len(root_node_with_children['children']) == 3

    child_titles = [child['title'] for child in root_node_with_children['children']]
    assert child_titles == ["A-Node", "B-Node", "Z-Node"]


def test_get_full_node_tree_recursively(client, auth_headers_1, test_vault_1_obj, test_user_1_obj):
    """
    Testet, ob der Endpunkt GET /nodes/ die gesamte Baumstruktur korrekt,
    sortiert und ohne Inhalte der Kind-Elemente zurückgibt.
    Dieser Test deckt den `include_children=True`-Fall in Node.to_dict() ab.
    """
    # 1. ARRANGE: Erstelle eine verschachtelte Node-Struktur
    # Die Titel sind absichtlich nicht alphabetisch sortiert, um die Sortierung zu testen.

    # Holen Sie die ID des Root-Nodes, der bei der Vault-Erstellung angelegt wurde.
    tree_res = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1)
    root_node_id = tree_res.json[0]['id']

    # Ebene 1
    node_z = node_service.create_node("Zebra Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)
    node_a = node_service.create_node("Apple Folder", "", root_node_id, test_vault_1_obj.id, test_user_1_obj.id)

    # Ebene 2 (Kinder von "Apple Folder")
    node_service.create_node("Sub-Note 2", "Content", node_a.id, test_vault_1_obj.id, test_user_1_obj.id)
    node_service.create_node("Sub-Note 1", "Content", node_a.id, test_vault_1_obj.id, test_user_1_obj.id)

    # 2. ACT: Rufe den Endpunkt ab, der die gesamte Baumstruktur zurückgeben sollte.
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1)

    # 3. ASSERT
    assert response.status_code == 200
    data = response.get_json()

    # Es sollte nur ein Element auf der obersten Ebene geben: den Root-Node
    assert len(data) == 1
    root_node_data = data[0]
    assert root_node_data['title'] == 'Summary'
    assert 'children' in root_node_data

    # Überprüfe die Kinder der ersten Ebene
    level_1_children = root_node_data['children']
    assert len(level_1_children) == 2

    # Überprüfe die SORTIERUNG: "Apple Folder" muss vor "Zebra Folder" kommen
    assert level_1_children[0]['title'] == 'Apple Folder'
    assert level_1_children[1]['title'] == 'Zebra Folder'

    # Überprüfe die Kinder der zweiten Ebene (unter "Apple Folder")
    apple_folder_data = level_1_children[0]
    assert 'children' in apple_folder_data
    level_2_children = apple_folder_data['children']
    assert len(level_2_children) == 2
    assert level_2_children[0]['title'] == 'Sub-Note 1'  # Überprüfe auch hier die Sortierung
    assert level_2_children[1]['title'] == 'Sub-Note 2'

    # Überprüfe die Performance-Optimierung:
    # Die Kind-Elemente in der Baumansicht sollten KEINEN Inhalt haben.
    assert 'content' not in level_1_children[0]
    assert 'content' not in level_1_children[1]
    assert 'content' not in level_2_children[0]


def test_get_single_node_api_returns_correct_structure(client, auth_headers_1, test_vault_1_obj, test_user_1_obj):
    """
    Testet den API-Endpunkt GET /.../nodes/{node_id} und überprüft die JSON-Struktur.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id
    node = node_service.create_node("API Test Node", "V1", None, vault_id, user_id)
    node_service.update_node(node.id, vault_id, user_id, content="V2")

    # ACT: Rufe den API-Endpunkt auf
    response = client.get(f'/api/vaults/{vault_id}/nodes/{node.id}', headers=auth_headers_1)

    # ASSERT - Status und Content-Type
    assert response.status_code == 200
    assert response.content_type == 'application/json'

    # ASSERT - JSON-Struktur und Daten
    data = response.get_json()
    assert isinstance(data, dict)
    assert data['id'] == node.id
    assert data['title'] == "API Test Node"
    assert data['content'] == "V2"  # Prüft den Inhalt der aktuellen Version

    # === DER ENTSCHEIDENDE TEST, DER FEHLGESCHLAGEN WÄRE ===
    # Dieser Test hätte geprüft, ob der "versions"-Schlüssel existiert.
    # Da du ihn entfernt hast, würde dieser Test einen KeyError werfen.
    # assert 'versions' in data
    # assert isinstance(data['versions'], list)
    # assert len(data['versions']) == 2

    # === DER NEUE, KORREKTE TEST FÜR DIE AKTUELLE API ===
    assert 'versions' not in data  # Prüft, dass die Liste absichtlich entfernt wurde.
    assert data['has_versions'] is True
    assert data['version_count'] == 2


# In deiner Test-Datei, z.B. tests/test_node_service.py

def test_get_node_versions_returns_correct_data(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob get_node_versions die korrekte Liste von Versionen
    für einen Node zurückgibt, sortiert nach neuester zuerst.
    """
    # ARRANGE
    user_id = test_user_1_obj.id
    vault_id = test_vault_1_obj.id

    # Erstelle einen Node und füge mehrere Versionen hinzu
    node = node_service.create_node("Versions-Test-Node", "Inhalt V1", None, vault_id, user_id)
    # Wichtig: kurzes Warten, um sicherzustellen, dass die Zeitstempel sich unterscheiden
    import time
    time.sleep(0.01)
    node_service.update_node(node.id, vault_id, user_id, content="Inhalt V2")
    time.sleep(0.01)
    node_service.update_node(node.id, vault_id, user_id, content="Inhalt V3")

    # ACT
    versions_list = node_service.get_node_versions(node.id, vault_id, user_id)

    # ASSERT
    assert versions_list is not None
    assert isinstance(versions_list, list)
    assert len(versions_list) == 3

    # Überprüfe die neueste Version (sollte an erster Stelle stehen)
    latest_version = versions_list[0]
    assert latest_version['version'] == 3
    assert latest_version['content'] == "Inhalt V3"
    assert 'author_name' in latest_version
    assert latest_version['author_name'] == test_user_1_obj.display_name

    # Überprüfe die mittlere Version
    middle_version = versions_list[1]
    assert middle_version['version'] == 2
    assert middle_version['content'] == "Inhalt V2"

    # Überprüfe die älteste Version
    oldest_version = versions_list[2]
    assert oldest_version['version'] == 1
    assert oldest_version['content'] == "Inhalt V1"


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