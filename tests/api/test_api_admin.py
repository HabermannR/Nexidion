import pytest
import json
from backend.models import User


# --- Fixture für Admin-Authentifizierung ---
@pytest.fixture(scope="function")
def admin_auth_headers(client, test_admin_obj):
    """
    Loggt den Admin-Benutzer ein und gibt die Authentifizierungs-Header zurück.
    """
    login_res = client.post('/api/auth/login',
                            json={'username': 'admin_user', 'password': 'admin_password'})
    assert login_res.status_code == 200, "Login für admin_user fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}


# --- Tests für GET /api/admin/users ---

def test_list_users_as_admin_success(client, admin_auth_headers, test_user_1_obj, test_user_2_obj, test_admin_obj):
    """[GET /users] Admin kann die Benutzerliste erfolgreich abrufen."""
    response = client.get('/api/admin/users', headers=admin_auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 3  # admin, user1, user2
    usernames = {user['username'] for user in data}
    assert 'admin_user' in usernames
    assert 'user1' in usernames
    assert 'user2' in usernames


def test_list_users_as_regular_user_fails(client, auth_headers_1):
    """[GET /users] Normaler Benutzer darf nicht auf die Benutzerliste zugreifen (403)."""
    response = client.get('/api/admin/users', headers=auth_headers_1)
    assert response.status_code == 403
    assert "Admin privileges required" in response.get_json()['error']


def test_list_users_unauthenticated_fails(client):
    """[GET /users] Nicht authentifizierter Zugriff schlägt fehl (401)."""
    response = client.get('/api/admin/users')
    assert response.status_code == 401


# --- Tests für POST /api/admin/users ---

def test_create_user_as_admin_success(client, admin_auth_headers, db_session):
    """[POST /users] Admin kann erfolgreich einen neuen Benutzer erstellen."""
    payload = {
        "username": "new_user_by_admin",
        "password": "strongpassword123",
        "display_name": "New User"
    }
    response = client.post('/api/admin/users', headers=admin_auth_headers, json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data['username'] == "new_user_by_admin"
    assert data['is_admin'] is False

    # In DB verifizieren
    user = db_session.session.get(User, data['id'])
    assert user is not None
    assert user.check_password("strongpassword123")


def test_create_user_fails_duplicate_username(client, admin_auth_headers, test_user_1_obj):
    """[POST /users] Admin kann keinen Benutzer mit einem existierenden Namen erstellen (409)."""
    payload = {"username": "user1", "password": "anypassword"}
    response = client.post('/api/admin/users', headers=admin_auth_headers, json=payload)
    assert response.status_code == 409
    assert "'user1' already exists" in response.get_json()['error']


def test_create_user_fails_missing_data(client, admin_auth_headers):
    """[POST /users] Erstellung schlägt fehl, wenn Daten fehlen (400)."""
    payload = {"username": "some_user"}  # Passwort fehlt
    response = client.post('/api/admin/users', headers=admin_auth_headers, json=payload)
    assert response.status_code == 400
    assert "Username and password are required" in response.get_json()['error']


# --- Tests für DELETE /api/admin/users/<id> ---

def test_delete_user_as_admin_success(client, admin_auth_headers, db_session, test_user_1_obj):
    """[DELETE /users/<id>] Admin kann einen anderen Benutzer erfolgreich löschen."""
    user_id_to_delete = test_user_1_obj.id
    response = client.delete(f'/api/admin/users/{user_id_to_delete}', headers=admin_auth_headers)
    assert response.status_code == 200
    assert "deleted successfully" in response.get_json()['message']

    # In DB verifizieren
    user = db_session.session.get(User, user_id_to_delete)
    assert user is None


def test_delete_user_as_regular_user_fails(client, auth_headers_1, test_user_2_obj):
    """[DELETE /users/<id>] Normaler Benutzer darf keine anderen Benutzer löschen (403)."""
    response = client.delete(f'/api/admin/users/{test_user_2_obj.id}', headers=auth_headers_1)
    assert response.status_code == 403


def test_delete_nonexistent_user_fails(client, admin_auth_headers):
    """[DELETE /users/<id>] Löschen eines nicht existierenden Benutzers schlägt fehl (404)."""
    response = client.delete('/api/admin/users/9999', headers=admin_auth_headers)
    assert response.status_code == 404
    assert "not found" in response.get_json()['error']


def test_admin_cannot_delete_self(client, admin_auth_headers, test_admin_obj):
    """[DELETE /users/<id>] Admin kann sich nicht selbst löschen (403)."""
    response = client.delete(f'/api/admin/users/{test_admin_obj.id}', headers=admin_auth_headers)
    assert response.status_code == 403
    assert "You cannot delete your own account" in response.get_json()['error']


# --- Tests für PUT /api/admin/users/<id>/password ---

def test_set_password_as_admin_success(client, admin_auth_headers, test_user_1_obj):
    """[PUT /password] Admin kann das Passwort eines Benutzers erfolgreich ändern."""
    payload = {"new_password": "new_password_by_admin"}
    response = client.put(f'/api/admin/users/{test_user_1_obj.id}/password', headers=admin_auth_headers, json=payload)
    assert response.status_code == 200

    # Verifizieren, dass der Login mit dem neuen Passwort funktioniert
    login_response = client.post('/api/auth/login', json={
        "username": test_user_1_obj.username,
        "password": "new_password_by_admin"
    })
    assert login_response.status_code == 200


# --- Tests für PUT /api/admin/users/<id> ---

def test_update_user_details_as_admin_success(client, admin_auth_headers, test_user_1_obj):
    """[PUT /users/<id>] Admin kann Details eines Benutzers erfolgreich ändern."""
    payload = {"display_name": "Updated Name", "is_admin": True}
    response = client.put(f'/api/admin/users/{test_user_1_obj.id}', headers=admin_auth_headers, json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['display_name'] == "Updated Name"
    assert data['is_admin'] is True


def test_update_user_fails_remove_last_admin(client, admin_auth_headers, test_admin_obj):
    """[PUT /users/<id>] Admin kann sich nicht selbst die Admin-Rechte entziehen, wenn er der letzte ist (403)."""
    payload = {"is_admin": False}
    response = client.put(f'/api/admin/users/{test_admin_obj.id}', headers=admin_auth_headers, json=payload)
    assert response.status_code == 403
    assert "Cannot remove admin status from the last administrator" in response.get_json()['error']