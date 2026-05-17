# tests/api/test_vaults_api.py

def test_list_vaults_success(client, auth_headers_1, test_vault_1_obj):
    """
    Testet GET /api/vaults
    Sollte den Vault zurückgeben, der durch die Fixture 'test_vault_1_obj' erstellt wurde.
    """
    response = client.get('/api/vaults/', headers=auth_headers_1)

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
    response = client.get('/api/vaults/', headers=auth_headers_1)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'Vault For User 1'  # Der Vault von User 2 darf nicht auftauchen


def test_create_vault_success(client, auth_headers_1):
    """Testet POST /api/vaults."""
    payload = {'name': 'My New Awesome Vault'}
    response = client.post('/api/vaults/', headers=auth_headers_1, json=payload)

    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'My New Awesome Vault'
    assert 'id' in data


def test_create_vault_duplicate_name_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass ein Vault mit dem gleichen Namen nicht erstellt werden kann."""
    payload = {'name': 'Vault For User 1'}
    response = client.post('/api/vaults/', headers=auth_headers_1, json=payload)

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
    response = client.get('/api/vaults/', headers=auth_headers_1)

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
    assert response.status_code == 400  # Bad Request
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


def test_export_vault_endpoint_success(client, auth_headers_1, test_vault_1_obj):
    """Happy Path: Erfolgreicher Export über die API. Überprüft File-Headers und Content."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/export', headers=auth_headers_1)

    assert response.status_code == 200
    assert response.mimetype == 'application/json'

    content_disposition = response.headers.get('Content-Disposition')
    assert content_disposition is not None
    assert 'attachment;' in content_disposition
    assert 'filename=' in content_disposition
    assert '.nexidion' in content_disposition

    data = response.get_json()
    assert data["nexidion_export_version"] == 1
    assert data["vault"]["name"] == test_vault_1_obj.name


def test_export_vault_endpoint_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Fehlerfall: Anderer User (nicht Owner) versucht den Vault zu exportieren."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/export', headers=auth_headers_2)
    assert response.status_code == 403
    assert "Only the vault owner" in response.get_json()['error']


def test_export_vault_endpoint_not_found(client, auth_headers_1):
    """Fehlerfall: Versuch, einen nicht existierenden Vault zu exportieren."""
    response = client.get('/api/vaults/9999/export', headers=auth_headers_1)
    assert response.status_code == 404
    assert "not found" in response.get_json()['error']


# === TESTS für GET /api/vaults/<id> (Vault Details) ===

def test_get_vault_details_success(client, auth_headers_1, test_vault_1_obj):
    """Happy Path: Erfolgreicher Abruf der Details eines Vaults."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == test_vault_1_obj.id
    assert data['name'] == test_vault_1_obj.name
    assert 'created_at' in data


def test_get_vault_details_not_found(client, auth_headers_1):
    """Fehlerfall: Versuch, die Details eines nicht existierenden Vaults abzurufen."""
    response = client.get('/api/vaults/9999', headers=auth_headers_1)
    assert response.status_code == 404
    assert "not found" in response.get_json()['error'].lower()


def test_get_vault_details_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Fehlerfall: User 2 versucht, die Details des Vaults von User 1 abzurufen."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}', headers=auth_headers_2)
    assert response.status_code == 403
    assert "permission" in response.get_json()['error'].lower()


# === TESTS für Vault Access Management (GET, POST, DELETE) ===

def test_get_vault_access_owner_success(client, auth_headers_1, test_vault_1_obj):
    """[GET /api/vaults/<id>/access] Owner kann die Zugriffsliste einer Vault einsehen."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, dict)


def test_get_vault_access_admin_success(client, admin_headers, test_vault_1_obj):
    """[GET /api/vaults/<id>/access] Admin kann die Zugriffsliste einer Vault einsehen (Override)."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/access', headers=admin_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, dict)


def test_get_vault_access_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """[GET /api/vaults/<id>/access] Fremder User darf die Liste nicht einsehen."""
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_2)
    assert response.status_code == 403
    assert "Only the vault owner or an admin" in response.get_json()['error']


def test_get_vault_access_guest_denied(client, auth_headers_1, test_vault_1_obj, test_user_1_obj, db_session):
    """[GET /api/vaults/<id>/access] Guest User (Demo) wird geblockt, selbst wenn er Owner ist."""
    test_user_1_obj.is_guest = True
    db_session.session.commit()

    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_1)

    # Revert for other tests
    test_user_1_obj.is_guest = False
    db_session.session.commit()

    assert response.status_code == 403
    assert "Guest users cannot manage vault access." in response.get_json()['error']


def test_grant_vault_access_owner_success(client, auth_headers_1, test_vault_1_obj, test_user_2_obj):
    """[POST /api/vaults/<id>/access] Owner kann Rechte auf seine Vault gewähren."""
    payload = {"user_id": test_user_2_obj.id, "role": "editor"}
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_1, json=payload)
    assert response.status_code == 200
    assert "Access granted." in response.get_json()['message']


def test_grant_vault_access_missing_user_id(client, auth_headers_1, test_vault_1_obj):
    """[POST /api/vaults/<id>/access] Fehler 400, wenn user_id im Body fehlt."""
    payload = {"role": "editor"}
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_1, json=payload)
    assert response.status_code == 400
    assert "user_id is required" in response.get_json()['error']


def test_grant_vault_access_invalid_role(client, auth_headers_1, test_vault_1_obj, test_user_2_obj):
    """[POST /api/vaults/<id>/access] Fehler 400 bei ungültiger Rolle."""
    payload = {"user_id": test_user_2_obj.id, "role": 99}
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/access', headers=auth_headers_1, json=payload)
    assert response.status_code == 400
    assert "Invalid role" in response.get_json()['error']


def test_revoke_vault_access_owner_success(client, auth_headers_1, test_vault_1_obj, test_user_2_obj):
    """[DELETE /api/vaults/<id>/access/<user_id>] Owner kann Rechte für seine Vault entziehen."""
    # Setup: Zuerst Rechte vergeben
    client.post(
        f'/api/vaults/{test_vault_1_obj.id}/access',
        headers=auth_headers_1,
        json={"user_id": test_user_2_obj.id, "role": "editor"}
    )

    # Test: Entziehen
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}/access/{test_user_2_obj.id}',
                             headers=auth_headers_1)
    assert response.status_code == 200
    assert "Access revoked." in response.get_json()['message']

