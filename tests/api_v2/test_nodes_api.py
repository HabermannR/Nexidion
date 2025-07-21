import pytest


# --- Helper-Funktion für diese Testdatei ---
def create_test_node(client, headers, vault_id, title, content="...", parent_id=None):
    """
    Erstellt einen Node über die V2-API und gibt das resultierende JSON-Objekt zurück.
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


def test_create_node_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Erstellen eines neuen Nodes in V2."""
    vault_id = test_vault_1_obj.id
    node_data = {'title': 'My First V2 Node', 'content': 'This is the content.'}

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'My First V2 Node'
    assert 'id' in data


def test_create_node_unauthorized(client, test_vault_1_obj):
    """Testet, dass ein nicht eingeloggter Benutzer keinen Node erstellen kann."""
    vault_id = test_vault_1_obj.id
    node_data = {'title': 'sneaky node'}

    response = client.post(f'/api/vaults/{vault_id}/nodes/', json=node_data)

    assert response.status_code == 401


def test_update_node_put(client, auth_headers_1, test_vault_1_obj):
    """Testet das vollständige Ersetzen (PUT) eines Nodes in V2."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node to be updated')

    update_data = {'title': 'Completely New Title', 'content': 'This is the new, updated content.'}

    update_res = client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}',
                            headers=auth_headers_1,
                            json=update_data)

    assert update_res.status_code == 200
    data = update_res.get_json()
    assert data['title'] == 'Completely New Title'
    assert data['content'] == 'This is the new, updated content.'


def test_rename_node_patch(client, auth_headers_1, test_vault_1_obj):
    """Testet das partielle Umbenennen (PATCH) eines Nodes in V2."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Old Title', content="Original Content")

    rename_data = {'title': 'Shiny New Title'}

    rename_res = client.patch(f'/api/vaults/{vault_id}/nodes/{node["id"]}',
                              headers=auth_headers_1,
                              json=rename_data)

    assert rename_res.status_code == 200
    data = rename_res.get_json()
    assert data['title'] == 'Shiny New Title'
    assert data['content'] == "Original Content"  # Inhalt sollte unverändert sein


def test_delete_node(client, auth_headers_1, test_vault_1_obj):
    """Testet das Löschen eines Nodes in V2."""
    vault_id = test_vault_1_obj.id
    # Der Root-Node kann nicht gelöscht werden. Wir müssen einen Kind-Node erstellen.
    tree_res = client.get(f'/api/vaults/{vault_id}/nodes/', headers=auth_headers_1)
    root_node_id = tree_res.get_json()[0]['id']

    node_to_delete = create_test_node(client, auth_headers_1, vault_id, 'Node to be deleted', parent_id=root_node_id)

    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}',
                               headers=auth_headers_1)
    assert delete_res.status_code == 200

    # Überprüfen, ob der Node wirklich weg ist
    get_res = client.get(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}', headers=auth_headers_1)
    assert get_res.status_code == 404


def test_get_nodes_as_list(client, auth_headers_1, test_vault_1_obj):
    """Testet den ?format=list Query-Parameter."""
    vault_id = test_vault_1_obj.id
    create_test_node(client, auth_headers_1, vault_id, "Node A")

    response = client.get(f'/api/vaults/{vault_id}/nodes/?format=list', headers=auth_headers_1)

    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2  # Root-Node + Node A
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


def test_get_nodes_from_other_users_vault_fails(client, auth_headers_1, test_vault_2_obj):
    """Sicherheitstest: User 1 kann die Nodes von User 2 nicht sehen."""
    other_vault_id = test_vault_2_obj.id
    response = client.get(f"/api/vaults/{other_vault_id}/nodes/", headers=auth_headers_1)
    assert response.status_code == 403


def test_delete_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann keinen Node von User 1 löschen."""
    vault_id = test_vault_1_obj.id
    node_to_delete = create_test_node(client, auth_headers_1, vault_id, 'Node von User 1')

    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}',
                               headers=auth_headers_2)
    assert delete_res.status_code == 403


def test_move_node_patch(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Verschieben eines Nodes in V2 via PATCH."""
    vault_id = test_vault_1_obj.id
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent Node')
    child = create_test_node(client, auth_headers_1, vault_id, 'Child Node')

    move_data = {'parent_id': parent['id']}

    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{child['id']}",
                            headers=auth_headers_1,
                            json=move_data)

    assert move_res.status_code == 200
    get_res = client.get(f"/api/vaults/{vault_id}/nodes/{child['id']}", headers=auth_headers_1)
    assert get_res.status_code == 200
    assert get_res.get_json()['parent_id'] == parent['id']


def test_patch_node_with_invalid_body(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass PATCH mit einem leeren oder ungültigen Body fehlschlägt."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Some Node")

    response = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}",
                            headers=auth_headers_1,
                            json={'unsupported_key': 'some_value'})

    assert response.status_code == 400
    assert "must contain 'title' or 'parent_id'" in response.get_json()['error']


def test_move_node_into_itself_fails(client, auth_headers_1, test_vault_1_obj):
    """Verhindert, dass ein Node in sich selbst verschoben wird."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Cyclic Node')

    move_data = {'parent_id': node['id']}

    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}",
                            headers=auth_headers_1,
                            json=move_data)

    assert move_res.status_code == 400
    assert 'Cannot move a node into itself' in move_res.get_json()['error']


def test_move_node_into_its_own_child_fails(client, auth_headers_1, test_vault_1_obj):
    """Verhindert, dass ein Node in einen seiner eigenen Nachkommen verschoben wird."""
    vault_id = test_vault_1_obj.id
    grandparent = create_test_node(client, auth_headers_1, vault_id, 'GP')
    parent = create_test_node(client, auth_headers_1, vault_id, 'P', parent_id=grandparent['id'])

    move_data = {'parent_id': parent['id']}

    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{grandparent['id']}",
                            headers=auth_headers_1,
                            json=move_data)

    assert move_res.status_code == 400
    assert 'Cannot move a node into one of its own children' in move_res.get_json()['error']


def test_post_nodes_content(client, auth_headers_1, test_vault_1_obj):
    """Testet den POST /content Endpunkt."""
    vault_id = test_vault_1_obj.id
    node_a = create_test_node(client, auth_headers_1, vault_id, "Content A", content="Alpha.")
    node_b = create_test_node(client, auth_headers_1, vault_id, "Content B", content="Beta.")

    payload = {'node_ids': [node_a['id'], node_b['id']]}

    response = client.post(f'/api/vaults/{vault_id}/nodes/content',
                           headers=auth_headers_1,
                           json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data['titles'] == ["Content A", "Content B"]
    assert "Alpha." in data['content']
    assert "Beta." in data['content']


def test_create_node_with_empty_title_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass das Erstellen eines Nodes mit leerem Titel fehlschlägt."""
    vault_id = test_vault_1_obj.id
    node_data = {'title': '   ', 'content': 'This should not be created.'}

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 400
    assert "cannot be empty" in response.get_json()['error']


@pytest.mark.parametrize("payload, expected_error", [
    (
            {"wrong_key": "some_value"},
            "must contain 'node_ids'"
    ),
    (
            {"node_ids": "not-a-list"},
            "'node_ids' must be a list"
    ),
    (
            {},  # Leerer Body
            "must contain 'node_ids'"
    )
])
def test_post_nodes_content_with_invalid_payload(client, auth_headers_1, test_vault_1_obj, payload, expected_error):
    """
    Testet verschiedene ungültige Payloads für den POST /content Endpunkt.
    """
    vault_id = test_vault_1_obj.id

    response = client.post(f'/api/vaults/{vault_id}/nodes/content',
                           headers=auth_headers_1,
                           json=payload)

    assert response.status_code == 400
    assert expected_error in response.get_json()['error']


def test_update_node_not_found(client, auth_headers_1, test_vault_1_obj):
    """
    Testet PUT /nodes/<id> - Fehlerfall: Node nicht gefunden.
    Deckt den ValueError-except-Block in der update_node API ab.
    """
    # Arrange
    payload = {"content": "This will fail anyway."}

    # Act
    response = client.put(f'/api/vaults/{test_vault_1_obj.id}/nodes/non-existent-node-id',
                          headers=auth_headers_1, json=payload)

    # Assert
    assert response.status_code == 404
    assert "not found" in response.get_json()['error']

def test_bulk_get_nodes_success(client, auth_headers_1, test_vault_1_obj):
    """
    Testet das erfolgreiche Abrufen mehrerer Nodes auf einmal über den /bulk-get Endpunkt.
    """
    # Arrange: Erstelle mehrere Nodes, um sie später abzurufen
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "Bulk Get Node 1", "Content for node 1.")
    node2 = create_test_node(client, auth_headers_1, vault_id, "Bulk Get Node 2", "Content for node 2.")
    create_test_node(client, auth_headers_1, vault_id, "Untouched Node")

    node_ids_to_get = [node1['id'], node2['id']]
    payload = {'node_ids': node_ids_to_get}

    # Act
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2

    # --- FIX: Überprüfe 'node_id' statt 'id' ---
    returned_ids = {node['node_id'] for node in data}
    assert set(node_ids_to_get) == returned_ids

    # Überprüfe die Details eines der zurückgegebenen Nodes stichprobenartig
    node1_data = next((n for n in data if n['node_id'] == node1['id']), None)
    assert node1_data is not None
    # Die zurückgegebene Version hat keinen Titel, also prüfen wir den Inhalt
    assert node1_data['content'] == "Content for node 1."


def test_bulk_get_nodes_with_non_existent_id(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass die Anfrage mit 404 fehlschlägt, wenn eine der Node-IDs (als String)
    nicht existiert. Deckt den ValueError-except-Block ab.
    """
    # Arrange
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "An Existing Node")

    # --- FIX: Verwende einen gültigen, aber nicht existierenden UUID-String statt eines Integers ---
    non_existent_uuid = '00000000-0000-0000-0000-000000000000'
    payload = {'node_ids': [node1['id'], non_existent_uuid]}

    # Act
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    # Jetzt sollte die Validierung im Controller durchgehen und der Service den Fehler auslösen.
    assert response.status_code == 404
    error_data = response.get_json()
    assert "error" in error_data
    assert "not found" in error_data['error']

@pytest.mark.parametrize("payload, expected_error", [
    ({}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": "not-a-list"}, "A list of 'node_ids' is required in the request body."),
    ({"wrong_key": [1, 2, 3]}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": None}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": ["some-valid-uuid", 12345]}, "All items in 'node_ids' must be strings.")
])
def test_bulk_get_nodes_invalid_payload(client, auth_headers_1, test_vault_1_obj, payload, expected_error):
    """
    Testet verschiedene ungültige Payloads für den /bulk-get Endpunkt,
    einschließlich falscher Datentypen innerhalb der Liste.
    """
    # Arrange
    vault_id = test_vault_1_obj.id

    # Act
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    assert response.status_code == 400
    assert response.get_json()['error'] == expected_error

def test_bulk_get_nodes_permission_denied(client, auth_headers_1, auth_headers_2, test_vault_1_obj, test_vault_2_obj):
    """
    Testet, dass die Anfrage mit 403 fehlschlägt, wenn versucht wird, auf einen Node
    ohne Berechtigung zuzugreifen. Deckt den PermissionError-except-Block ab.
    """
    # Arrange: User 1 erstellt einen Node in seinem Vault, User 2 ebenfalls in seinem.
    vault_id_user_1 = test_vault_1_obj.id
    node_user_1 = create_test_node(client, auth_headers_1, vault_id_user_1, "Node from User 1")
    node_user_2 = create_test_node(client, auth_headers_2, test_vault_2_obj.id, "Node from User 2")

    # User 1 versucht, seinen eigenen Node und den von User 2 abzurufen.
    payload = {'node_ids': [node_user_1['id'], node_user_2['id']]}

    # Act
    response = client.post(f'/api/vaults/{vault_id_user_1}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    assert response.status_code == 403
    error_data = response.get_json()
    assert "error" in error_data
    # Die Service-Funktion sollte eine PermissionError auslösen
    assert "Permission denied" in error_data['error'] or "access" in error_data['error']


@pytest.mark.parametrize("payload, expected_error", [
    ({}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": "not-a-list"}, "A list of 'node_ids' is required in the request body."),
    ({"wrong_key": [1, 2, 3]}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": None}, "A list of 'node_ids' is required in the request body."),
    ({"node_ids": ["some-valid-uuid", 12345]}, "All items in 'node_ids' must be strings.")
])
def test_bulk_get_nodes_invalid_payload(client, auth_headers_1, test_vault_1_obj, payload, expected_error):
    """
    Testet verschiedene ungültige Payloads für den /bulk-get Endpunkt.
    """
    # Arrange
    vault_id = test_vault_1_obj.id

    # Act
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    assert response.status_code == 400
    assert response.get_json()['error'] == expected_error


def test_bulk_get_nodes_with_empty_list(client, auth_headers_1, test_vault_1_obj):
    """
    Testet das Verhalten des Endpunkts, wenn eine leere Liste von IDs übergeben wird.
    Es sollte eine leere Liste zurückgegeben werden.
    """
    # Arrange
    vault_id = test_vault_1_obj.id
    payload = {'node_ids': []}

    # Act
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get',
                           headers=auth_headers_1,
                           json=payload)

    # Assert
    assert response.status_code == 200
    assert response.get_json() == []

def test_get_nodes_with_empty_search_title_fails(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass die Node-Suche mit einem leeren ?title=... Query-Parameter
    einen 400 Bad Request Fehler zurückgibt.
    """
    vault_id = test_vault_1_obj.id
    # Der leere Query-Parameter sollte vom Service als ungültig angesehen werden.
    response = client.get(f'/api/vaults/{vault_id}/nodes/?title=', headers=auth_headers_1)

    assert response.status_code == 400
    assert "Search title cannot be empty" in response.get_json()['error'] # Annahme der Fehlermeldung

def test_create_node_with_parent_from_other_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj,
                                                        test_vault_2_obj):
    """Testet, dass das Erstellen eines Nodes mit einem Parent aus einem fremden Vault fehlschlägt."""
    vault_id_1 = test_vault_1_obj.id

    # User 2 erstellt einen Node in seinem Vault
    parent_in_vault_2 = create_test_node(client, auth_headers_2, test_vault_2_obj.id, 'Parent in Vault 2')

    # User 1 versucht, einen Node in seinem Vault zu erstellen, aber mit dem Parent von User 2
    node_data = {'title': 'Invalid Child', 'parent_id': parent_in_vault_2['id']}

    response = client.post(f'/api/vaults/{vault_id_1}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 403  # oder 400, je nach Service-Implementierung
    assert "Parent node not found in the specified vault" in response.get_json()['error']

def test_create_node_internal_server_error(client, auth_headers_1, test_vault_1_obj, monkeypatch):
    """Testet den 500-Fehlerfall beim Erstellen eines Nodes."""

    # Mocke die Service-Funktion, damit sie eine unerwartete Exception wirft
    def mock_create_node(*args, **kwargs):
        raise Exception("Simulated unexpected database error")

    monkeypatch.setattr("backend.services.node_service.create_node", mock_create_node)

    node_data = {'title': 'This will fail'}
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 500
    assert "internal server error" in response.get_json()['error']


def test_get_single_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann einen Node von User 1 nicht direkt abrufen."""
    # User 1 erstellt einen Node
    node_user_1 = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Private Node')

    # User 2 versucht, ihn abzurufen
    response = client.get(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node_user_1['id']}", headers=auth_headers_2)

    assert response.status_code == 403



def test_update_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann einen Node von User 1 nicht via PUT aktualisieren."""
    node_user_1 = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Private Node')
    update_data = {'title': 'Attempted Takeover', 'content': '...'}

    response = client.put(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node_user_1['id']}",
                          headers=auth_headers_2,
                          json=update_data)

    assert response.status_code == 403


def test_patch_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann einen Node von User 1 nicht via PATCH aktualisieren."""
    node_user_1 = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Private Node')
    patch_data = {'title': 'Attempted Takeover'}

    response = client.patch(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node_user_1['id']}",
                            headers=auth_headers_2,
                            json=patch_data)

    assert response.status_code == 403


# --- Tests für Fehlerfälle in `delete_node` ---

def test_delete_root_node_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass das Löschen des Root-Nodes fehlschlägt."""
    vault_id = test_vault_1_obj.id
    tree_res = client.get(f'/api/vaults/{vault_id}/nodes/', headers=auth_headers_1)
    root_node_id = tree_res.get_json()[0]['id']

    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{root_node_id}',
                               headers=auth_headers_1)

    assert delete_res.status_code == 400
    assert "Cannot delete the root node" in delete_res.get_json()['error']


# --- Tests für Fehlerfälle in `post_nodes_content` ---

def test_post_nodes_content_permission_denied(client, auth_headers_1, auth_headers_2, test_vault_1_obj, test_vault_2_obj):
    """Testet, dass das Abrufen von Inhalten fehlschlägt, wenn ein Node aus einem fremden Vault stammt."""
    node_user_2 = create_test_node(client, auth_headers_2, test_vault_2_obj.id, 'Node from User 2')
    payload = {'node_ids': [node_user_2['id']]}

    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/content',
                           headers=auth_headers_1,
                           json=payload)

    assert response.status_code == 403


# --- Tests für Fehlerfälle in `propose_node_update` ---

def test_propose_update_with_invalid_session_id(client, auth_headers_1, test_vault_1_obj):
    """Testet den 404-Fehlerfall bei `propose-update` mit einer ungültigen Session-ID."""
    node = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Target Node')
    payload = {
        "session_id": "non-existent-session-uuid",
        "model": "test-model"
    }
    response = client.post(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node['id']}/propose-update",
                           headers=auth_headers_1,
                           json=payload)
    assert response.status_code == 404


def test_propose_update_permission_denied(client, auth_headers_1, test_vault_1_obj, monkeypatch):
    """Testet den 403-Fehlerfall bei `propose-update` via Mocking."""
    def mock_propose(*args, **kwargs):
        raise PermissionError("User does not have access to this session")

    monkeypatch.setattr("backend.services.chat_service.propose_node_update_from_chat", mock_propose)

    node = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Target Node')
    payload = {"session_id": "any-id", "model": "test-model"}
    response = client.post(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node['id']}/propose-update",
                           headers=auth_headers_1,
                           json=payload)
    assert response.status_code == 403


def test_propose_update_internal_server_error(client, auth_headers_1, test_vault_1_obj, monkeypatch):
    """Testet den 500-Fehlerfall bei `propose-update` via Mocking."""
    def mock_propose(*args, **kwargs):
        raise Exception("Simulated LLM API failure")

    monkeypatch.setattr("backend.services.chat_service.propose_node_update_from_chat", mock_propose)

    node = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Target Node')
    payload = {"session_id": "any-id", "model": "test-model"}
    response = client.post(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node['id']}/propose-update",
                           headers=auth_headers_1,
                           json=payload)
    assert response.status_code == 500
    assert "internal error" in response.get_json()['error']


def test_get_node_versions_api(client, auth_headers_1, test_vault_1_obj):
    """
    Testet den GET /.../nodes/{id}/versions Endpunkt, inklusive ETag-Caching.
    """
    # ARRANGE
    vault_id = test_vault_1_obj.id

    # 1. Erstelle einen Node über die API
    node = create_test_node(client, auth_headers_1, vault_id,
                            'Node for Version Test', 'Content V1')
    node_id = node['id']

    # 2. Aktualisiere den Node mehrmals, um Versionen zu erzeugen
    client.put(f'/api/vaults/{vault_id}/nodes/{node_id}',
               headers=auth_headers_1, json={'content': 'Content V2'})
    client.put(f'/api/vaults/{vault_id}/nodes/{node_id}',
               headers=auth_headers_1, json={'content': 'Content V3'})

    # --- Test der ersten Anfrage (ohne Cache) ---
    # ACT
    response1 = client.get(f'/api/vaults/{vault_id}/nodes/{node_id}/versions',
                           headers=auth_headers_1)

    # ASSERT
    assert response1.status_code == 200
    versions = response1.get_json()

    assert isinstance(versions, list)
    assert len(versions) == 3

    # Überprüfe die Reihenfolge (neueste zuerst) und den Inhalt
    assert versions[0]['version'] == 3
    assert versions[0]['content'] == 'Content V3'
    assert versions[1]['version'] == 2
    assert versions[1]['content'] == 'Content V2'
    assert versions[2]['version'] == 1
    assert versions[2]['content'] == 'Content V1'

    # Überprüfe, ob der ETag-Header für das Caching gesetzt wurde
    assert 'ETag' in response1.headers
    etag = response1.headers['ETag']

    # --- Test der zweiten Anfrage (mit Cache) ---
    # ARRANGE 2
    cached_headers = auth_headers_1.copy()
    cached_headers['If-None-Match'] = etag

    # ACT 2
    response2 = client.get(f'/api/vaults/{vault_id}/nodes/{node_id}/versions',
                           headers=cached_headers)

    # ASSERT 2
    assert response2.status_code == 304
    assert not response2.data  # Der Body muss bei 304 leer sein


def test_get_node_versions_for_nonexistent_node_api_returns_404(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass der API-Endpunkt für Versionen 404 zurückgibt, wenn der Node nicht existiert."""
    vault_id = test_vault_1_obj.id
    non_existent_node_id = "this-node-does-not-exist"

    response = client.get(f'/api/vaults/{vault_id}/nodes/{non_existent_node_id}/versions',
                          headers=auth_headers_1)

    assert response.status_code == 404