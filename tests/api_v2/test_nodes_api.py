# tests/api/v2/test_nodes_api.py
import pytest
from backend.services import node_service


# --- Helper-Funktion für diese Testdatei ---
def create_test_node(client, headers, vault_id, title, content="...", parent_id=None):
    """
    Erstellt einen Node über die API und gibt das resultierende JSON-Objekt zurück.
    Wirft einen Fehler, wenn die Erstellung fehlschlägt, um Tests sauber zu halten.
    """
    node_data = {'title': title, 'content': content}
    if parent_id:
        node_data['parent_id'] = parent_id

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=headers,
                           json=node_data)
    # Stellt sicher, dass das Setup für den Test erfolgreich war
    assert response.status_code == 201, f"Helper 'create_test_node' failed: {response.text}"
    return response.get_json()


# ========================================================================
# CRUD-Operationen
# ========================================================================

def test_create_node_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Erstellen eines neuen Nodes."""
    vault_id = test_vault_1_obj.id
    node_data = {'title': 'My First API Node', 'content': 'This is the content.'}

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'My First API Node'
    assert 'id' in data


def test_update_node_put(client, auth_headers_1, test_vault_1_obj):
    """Testet das Aktualisieren (PUT) eines Nodes."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node to be updated', 'Original Content')

    update_data = {'title': 'Completely New Title', 'content': 'This is the new, updated content.'}
    update_res = client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}',
                            headers=auth_headers_1,
                            json=update_data)
    assert update_res.status_code == 200
    data = update_res.get_json()
    assert data['title'] == 'Completely New Title'
    assert data['content'] == 'This is the new, updated content.'


def test_delete_node_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Löschen eines Nodes."""
    vault_id = test_vault_1_obj.id
    node_to_delete = create_test_node(client, auth_headers_1, vault_id, 'Node to be deleted')

    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}',
                               headers=auth_headers_1)
    assert delete_res.status_code == 200

    get_res = client.get(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}', headers=auth_headers_1)
    assert get_res.status_code == 404


def test_delete_node_reparents_child_via_api(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass beim Löschen eines Nodes dessen Kind an den Großeltern-Node
    angehängt wird (Adoptions-Logik).
    """
    # ARRANGE: Erstelle eine Hierarchie: Grandparent -> Parent -> Child
    vault_id = test_vault_1_obj.id
    grandparent = create_test_node(client, auth_headers_1, vault_id, 'Grandparent')
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent', parent_id=grandparent['id'])
    child = create_test_node(client, auth_headers_1, vault_id, 'Child', parent_id=parent['id'])

    # ACT: Lösche den Parent-Node über die API
    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{parent["id"]}',
                               headers=auth_headers_1)
    assert delete_res.status_code == 200

    # ASSERT: Überprüfe den neuen Zustand des Kindes über die API
    get_child_res = client.get(f'/api/vaults/{vault_id}/nodes/{child["id"]}', headers=auth_headers_1)
    assert get_child_res.status_code == 200
    child_data = get_child_res.get_json()

    # Das Kind sollte jetzt den Großeltern-Node als Parent haben
    assert child_data['parent_id'] == grandparent['id']


# ========================================================================
# GET-Variationen und Caching
# ========================================================================

def test_get_nodes_as_list(client, auth_headers_1, test_vault_1_obj):
    """Testet den ?format=list Query-Parameter."""
    vault_id = test_vault_1_obj.id
    create_test_node(client, auth_headers_1, vault_id, "Node A")

    response = client.get(f'/api/vaults/{vault_id}/nodes/?format=list', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1  # Mindestens der Root-Node + der neu erstellte
    assert 'content' in data[0]


def test_find_node_by_title_query_param(client, auth_headers_1, test_vault_1_obj):
    """Testet den ?title=... Query-Parameter für die Node-Suche."""
    vault_id = test_vault_1_obj.id
    create_test_node(client, auth_headers_1, vault_id, "My Special Findable Node")

    response = client.get(f'/api/vaults/{vault_id}/nodes/?title=Special Findable', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['title'] == "My Special Findable Node"


def test_get_node_versions_api_with_caching(client, auth_headers_1, test_vault_1_obj):
    """Testet den GET /.../nodes/{id}/versions Endpunkt, inklusive ETag-Caching."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node for Version Test', 'Content V1')
    client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}', headers=auth_headers_1, json={'content': 'Content V2'})

    # Erste Anfrage (ohne Cache)
    response1 = client.get(f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions', headers=auth_headers_1)
    assert response1.status_code == 200
    versions = response1.get_json()
    assert len(versions) == 2
    assert versions[0]['version'] == 2
    assert 'ETag' in response1.headers
    etag = response1.headers['ETag']

    # Zweite Anfrage (mit Cache)
    cached_headers = {**auth_headers_1, 'If-None-Match': etag}
    response2 = client.get(f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions', headers=cached_headers)
    assert response2.status_code == 304


# ========================================================================
# Spezifische PATCH-Routen (Move, Icon)
# ========================================================================

def test_move_node_patch(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Verschieben eines Nodes via PATCH .../move."""
    vault_id = test_vault_1_obj.id
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent Node')
    child = create_test_node(client, auth_headers_1, vault_id, 'Child Node')

    move_data = {'parent_id': parent['id']}
    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{child['id']}/move",
                            headers=auth_headers_1,
                            json=move_data)
    assert move_res.status_code == 200

    get_res = client.get(f"/api/vaults/{vault_id}/nodes/{child['id']}", headers=auth_headers_1)
    assert get_res.get_json()['parent_id'] == parent['id']


def test_set_node_icon_patch(client, auth_headers_1, test_vault_1_obj):
    """
    Testet das erfolgreiche Setzen und Entfernen eines GÜLTIGEN Icons.
    """
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node with Icon')

    # Setze ein gültiges Icon aus der Liste
    valid_icon = 'bxs-folder'
    icon_data = {'icon': valid_icon}
    icon_res = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                            headers=auth_headers_1,
                            json=icon_data)
    assert icon_res.status_code == 200
    assert icon_res.get_json()['icon'] == valid_icon

    # Entferne das Icon, indem `null` gesendet wird
    icon_data_null = {'icon': None}
    icon_res_null = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                                 headers=auth_headers_1,
                                 json=icon_data_null)
    assert icon_res_null.status_code == 200
    assert icon_res_null.get_json()['icon'] is None


@pytest.mark.parametrize("invalid_icon", [
    "not-a-valid-icon-string",  # Komplett ungültig
    "bx bxs-folder",               # Fast richtig, aber "bx " zu viel
    "",                         # Ein leerer String ist ebenfalls ungültig
    "bxs-folder ",           # Ungültig wegen Leerzeichen am Ende
])
def test_set_node_icon_with_invalid_string_fails(client, auth_headers_1, test_vault_1_obj, invalid_icon):
    """
    Testet, dass PATCH .../icon einen 400-Fehler zurückgibt, wenn ein ungültiger String gesendet wird.
    """
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Test Node')

    payload = {'icon': invalid_icon}
    response = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                            headers=auth_headers_1,
                            json=payload)

    assert response.status_code == 400
    error_json = response.get_json()
    assert "Invalid icon value" in error_json['error']


def test_set_node_icon_on_nonexistent_node(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass PATCH .../icon einen 404-Fehler zurückgibt, wenn der Node nicht existiert.
    """
    vault_id = test_vault_1_obj.id
    non_existent_node_id = "00000000-0000-0000-0000-000000000000"

    payload = {'icon': '❓'}
    response = client.patch(f"/api/vaults/{vault_id}/nodes/{non_existent_node_id}/icon",
                            headers=auth_headers_1,
                            json=payload)

    assert response.status_code == 400 # Der Service wirft einen ValueError, die API gibt 400 zurück
    assert "Node not found" in response.get_json()['error']


def test_set_node_icon_on_other_users_node(client, auth_headers_1, auth_headers_2, test_vault_1_obj, test_vault_2_obj):
    """
    Sicherheitstest: Stellt sicher, dass User 2 das Icon eines Nodes von User 1 nicht ändern kann.
    """
    # User 1 erstellt einen Node in seinem Vault
    vault_id_1 = test_vault_1_obj.id
    node_user_1 = create_test_node(client, auth_headers_1, vault_id_1, "Node von User 1")

    # User 2 versucht, das Icon für diesen Node zu ändern
    payload = {'icon': '🏴‍☠️'}
    response = client.patch(f"/api/vaults/{vault_id_1}/nodes/{node_user_1['id']}/icon",
                            headers=auth_headers_2,  # Wichtig: Header von User 2
                            json=payload)

    assert response.status_code == 403


# ========================================================================
# Bulk-Operationen
# ========================================================================

def test_bulk_get_nodes_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Abrufen mehrerer Nodes über POST /bulk-get."""
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "Bulk 1", "Content 1")
    node2 = create_test_node(client, auth_headers_1, vault_id, "Bulk 2", "Content 2")
    create_test_node(client, auth_headers_1, vault_id, "Untouched Node")

    payload = {'node_ids': [node1['id'], node2['id']]}
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get', headers=auth_headers_1, json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2

    # KORREKTUR: Prüfe auf 'node_id' in den zurückgegebenen Versionen-Objekten
    returned_node_ids = {item['node_id'] for item in data}
    assert set(payload['node_ids']) == returned_node_ids


def test_post_nodes_content_success(client, auth_headers_1, test_vault_1_obj):
    """Testet den POST /content Endpunkt."""
    vault_id = test_vault_1_obj.id
    node_a = create_test_node(client, auth_headers_1, vault_id, "Content A", content="Alpha.")
    node_b = create_test_node(client, auth_headers_1, vault_id, "Content B", content="Beta.")

    payload = {'node_ids': [node_a['id'], node_b['id']]}
    response = client.post(f'/api/vaults/{vault_id}/nodes/content', headers=auth_headers_1, json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data['titles'] == ["Content A", "Content B"]
    assert "Alpha." in data['content']
    assert "Beta." in data['content']


# ========================================================================
# Fehler- und Sicherheits-Tests
# ========================================================================

def test_create_node_unauthorized(client, test_vault_1_obj):
    """Testet, dass ein nicht eingeloggter Benutzer keinen Node erstellen kann."""
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/', json={'title': 'sneaky'})
    assert response.status_code == 401


def test_get_nodes_from_other_users_vault_fails(client, auth_headers_1, test_vault_2_obj):
    """Sicherheitstest: User 1 kann die Nodes von User 2 nicht sehen."""
    response = client.get(f"/api/vaults/{test_vault_2_obj.id}/nodes/", headers=auth_headers_1)
    assert response.status_code == 403


def test_update_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann einen Node von User 1 nicht aktualisieren."""
    node_user_1 = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Private Node')
    response = client.put(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node_user_1['id']}",
                          headers=auth_headers_2, json={'title': 'takeover'})
    assert response.status_code == 403


def test_move_node_into_its_own_child_fails(client, auth_headers_1, test_vault_1_obj):
    """Verhindert, dass ein Node in einen seiner eigenen Nachkommen verschoben wird."""
    vault_id = test_vault_1_obj.id
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent')
    child = create_test_node(client, auth_headers_1, vault_id, 'Child', parent_id=parent['id'])

    move_data = {'parent_id': child['id']}
    # KORREKTUR: Korrekter Endpunkt /move
    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{parent['id']}/move",
                            headers=auth_headers_1, json=move_data)
    assert move_res.status_code == 400
    assert 'Cannot move a node into one of its own children' in move_res.get_json()['error']


def test_create_node_with_parent_from_other_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj,
                                                        test_vault_2_obj):
    """Testet, dass das Erstellen eines Nodes mit einem Parent aus einem fremden Vault fehlschlägt."""
    parent_in_vault_2 = create_test_node(client, auth_headers_2, test_vault_2_obj.id, 'Parent in Vault 2')
    node_data = {'title': 'Invalid Child', 'parent_id': parent_in_vault_2['id']}

    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1, json=node_data)
    assert response.status_code == 403  # Oder 400, aber 403 ist semantisch passender hier.
    assert "Cannot assign a parent from a different vault" in response.get_json()['error']


@pytest.mark.parametrize("payload, expected_error", [
    ({}, "Request body must contain 'node_ids'."),
    ({"node_ids": "not-a-list"}, "'node_ids' must be a list."),
])
def test_post_nodes_content_with_invalid_payload(client, auth_headers_1, test_vault_1_obj, payload, expected_error):
    """Testet verschiedene ungültige Payloads für POST /content."""
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/content', headers=auth_headers_1, json=payload)
    assert response.status_code == 400
    assert expected_error in response.get_json()['error']


def test_bulk_get_nodes_with_non_existent_id_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass /bulk-get mit 404 fehlschlägt, wenn eine der Node-IDs nicht existiert."""
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "An Existing Node")
    # KORREKTUR: Ein gültiger String, der keinem Node entspricht, um Service-Fehler zu testen
    non_existent_uuid = '00000000-0000-0000-0000-000000000000'
    payload = {'node_ids': [node1['id'], non_existent_uuid]}

    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get', headers=auth_headers_1, json=payload)
    assert response.status_code == 404
    assert "not found" in response.get_json()['error']


def test_api_update_node_icon_success(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet den "Happy Path" für den PATCH /.../icon Endpunkt.
    """
    # ARRANGE
    # Erstelle einen Node über den Service, um ein Objekt zum Ändern zu haben.
    node_dict = node_service.create_node("API Icon Test", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict['id']

    payload = {'icon': 'bxs-brain'}  # Ein gültiges, neues Icon

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == node_id
    assert response_data['icon'] == 'bxs-brain'

    # Zusätzliche Überprüfung: Hole den Node erneut und prüfe, ob die Änderung persistent ist.
    get_response = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}', headers=auth_headers_1)
    assert get_response.get_json()['icon'] == 'bxs-brain'


def test_api_update_node_icon_to_null(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob das Icon via API auf `null` gesetzt werden kann.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Icon auf Null", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict['id']

    payload = {'icon': None}  # JSON `null` wird zu Python `None`

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 200
    assert response.get_json()['icon'] is None


def test_api_update_node_icon_with_invalid_icon_returns_400(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass die API einen 400 Bad Request bei einem ungültigen Icon zurückgibt.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Ungültiges Icon", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict['id']

    payload = {'icon': 'ungueltiger-string-123'}

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 400  # Weil ein ValueError im Service zu 400 wird
    assert "Invalid icon value" in response.get_json()['error']


def test_api_update_node_icon_with_missing_key_returns_400(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass die API einen 400 Bad Request zurückgibt, wenn der 'icon'-Schlüssel fehlt.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Fehlender Key", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict['id']

    payload = {'falscher_key': 'bxs-brain'}  # Der 'icon'-Key fehlt

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 400
    assert "Request body must contain 'icon'" in response.get_json()['error']