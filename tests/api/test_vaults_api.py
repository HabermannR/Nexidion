
def test_list_vaults_success(client, auth_headers_1, test_vault_1_obj):
    """
    Testet GET /api/vaults
    Sollte den Vault zurückgeben, der durch die Fixture 'test_vault_1_obj' erstellt wurde.
    """
    # Arrange:
    # - `auth_headers_1` loggt User 1 ein.
    # - `test_vault_1_obj` erstellt einen Vault für User 1 in der DB.

    # Act:
    response = client.get('/api/vaults/', headers=auth_headers_1)

    # Assert:
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['name'] == 'Vault For User 1'
    assert data[0]['id'] == test_vault_1_obj.id


def test_list_vaults_is_isolated(client, auth_headers_1, test_vault_1_obj, test_vault_2_obj):
    """
    Testet, dass User 1 NUR seine eigenen Vaults sieht und nicht die von User 2.
    """
    # Arrange:
    # - User 1 ist eingeloggt.
    # - Vault 1 (gehört User 1) und Vault 2 (gehört User 2) existieren.

    # Act:
    response = client.get('/api/vaults/', headers=auth_headers_1)

    # Assert:
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'Vault For User 1'  # Der Vault von User 2 darf nicht auftauchen


def test_create_vault_success(client, auth_headers_1):
    """Testet POST /api/vaults."""
    # Arrange
    payload = {'name': 'My New Awesome Vault'}

    # Act
    response = client.post('/api/vaults/', headers=auth_headers_1, json=payload)

    # Assert
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'My New Awesome Vault'
    assert 'id' in data


def test_create_vault_duplicate_name_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass ein Vault mit dem gleichen Namen nicht erstellt werden kann."""
    # Arrange
    # `test_vault_1_obj` hat bereits einen Vault 'Vault For User 1' erstellt.
    payload = {'name': 'Vault For User 1'}

    # Act
    response = client.post('/api/vaults/', headers=auth_headers_1, json=payload)

    # Assert
    assert response.status_code == 409  # Conflict
    data = response.get_json()
    assert "already own a vault named" in data['error']


def test_get_vaults_unauthorized(client):
    """Testet den Zugriff auf den v2-Vault-Endpunkt ohne Token."""
    response = client.get('/api/vaults/')
    assert response.status_code == 401


def test_get_vaults_success(client, auth_headers_1, test_vault_1_obj):
    """
    Testet den erfolgreichen Abruf von Vaults für einen eingeloggten Benutzer.
    """
    # Arrange:
    # - `auth_headers_1` loggt User 1 ein.
    # - `test_vault_1_obj` erstellt einen Vault für User 1 in der DB.

    # Act:
    response = client.get('/api/vaults/', headers=auth_headers_1)

    # Assert:
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['name'] == 'Vault For User 1'
    assert data[0]['id'] == test_vault_1_obj.id


# === ZUSÄTZLICHE TESTS für PUT /api/vaults/<id> (Rename) ===

def test_rename_vault_success(client, auth_headers_1, test_vault_1_obj):
    """Happy Path: Erfolgreiches Umbenennen eines Vaults."""
    payload = {"name": "My Super Renamed Vault"}
    response = client.put(f'/api/vaults/{test_vault_1_obj.id}',
                          headers=auth_headers_1,
                          json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == "My Super Renamed Vault"
    assert data['id'] == test_vault_1_obj.id


def test_rename_vault_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Fehlerfall: User 2 versucht, den Vault von User 1 umzubenennen."""
    payload = {"name": "Hacked!"}
    response = client.put(f'/api/vaults/{test_vault_1_obj.id}',
                                     headers=auth_headers_2,  # Authentifiziert als User 2
                                     json=payload)
    assert response.status_code == 403  # Forbidden
    assert "permission" in response.get_json()['error']


def test_rename_vault_not_found(client, auth_headers_1):
    """Fehlerfall: Versuch, einen nicht existierenden Vault umzubenennen."""
    payload = {"name": "Does not matter"}
    response = client.put('/api/vaults/999',
                          headers=auth_headers_1,
                          json=payload)
    assert response.status_code == 404  # Not Found
    assert "not found" in response.get_json()['error']


def test_rename_vault_no_name_provided(client, auth_headers_1, test_vault_1_obj):
    """Fehlerfall: Kein Name im Request-Body."""
    response = client.put(f'/api/vaults/{test_vault_1_obj.id}',
                          headers=auth_headers_1,
                          json={})  # Leerer Payload
    assert response.status_code == 400  # Bad Request
    assert "New name is required" in response.get_json()['error']


def test_delete_vault_success(client, auth_headers_1, test_user_1_obj):
    """Happy Path: Erfolgreiches Löschen eines Vaults, wenn es nicht der letzte ist."""
    # Arrange: Erstelle zwei Vaults über den Service, damit es schnell geht.
    from backend.services import vault_service
    vault1 = vault_service.create_vault("Vault to be deleted", test_user_1_obj.id)
    vault_service.create_vault("Vault to keep", test_user_1_obj.id)

    # Act
    response = client.delete(f'/api/vaults/{vault1.id}', headers=auth_headers_1)

    # Assert
    assert response.status_code == 200
    assert "deleted" in response.get_json()['message']


def test_delete_last_vault_fails(client, auth_headers_1, test_vault_1_obj):
    """Fehlerfall: Versuch, den letzten verbleibenden Vault zu löschen."""
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}', headers=auth_headers_1)
    assert response.status_code == 400  # Bad Request (oder ein anderer Fehlercode, den du definierst)
    assert "delete your last remaining vault" in response.get_json()['error']


def test_delete_vault_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Fehlerfall: User 2 versucht, den Vault von User 1 zu löschen."""
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}',
                             headers=auth_headers_2)  # Authentifiziert als User 2
    assert response.status_code == 403  # Forbidden


def test_delete_vault_not_found(client, auth_headers_1):
    """Fehlerfall: Versuch, einen nicht existierenden Vault zu löschen."""
    response = client.delete('/api/vaults/999', headers=auth_headers_1)
    assert response.status_code == 404  # Not Found