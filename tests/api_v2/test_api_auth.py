# tests/api_v2/test_api_auth.py


def test_v2_login_success(client, test_user_1_obj):
    """Testet einen erfolgreichen Login über den neuen V2 Endpunkt."""
    response = client.post('/api/auth/login',
                           json={'username': 'user1', 'password': 'password123'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'user' in data
    assert data['user']['username'] == 'user1'

def test_v2_login_failure_bad_password(client, test_user_1_obj):
    """Testet einen Login mit falschem Passwort über den V2 Endpunkt."""
    response = client.post('/api/auth/login',
                           json={'username': 'user1', 'password': 'wrongpassword'})
    assert response.status_code == 401
    data = response.get_json()
    # KORRIGIERT: Erwartet die exakte Fehlermeldung aus der API
    assert data['error'] == 'Invalid credentials'

def test_v2_login_failure_missing_fields(client):
    """Testet einen Request mit fehlenden Daten."""
    response = client.post('/api/auth/login',
                           json={'username': 'user1'}) # Passwort fehlt
    assert response.status_code == 400
    data = response.get_json()
    assert data['error'] == 'Username and password are required'

def test_get_me_success(client, auth_headers_1, test_user_1_obj):
    """Testet den erfolgreichen Abruf des eigenen Profils."""
    response = client.get('/api/auth/me', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert 'user' in data
    assert data['user']['id'] == test_user_1_obj.id
    assert 'password_hash' not in data['user']

def test_get_me_no_token(client):
    """Test: Versuchter Abruf ohne Token -> 401 Unauthorized."""
    response = client.get('/api/auth/me')
    assert response.status_code == 401
    # KORRIGIERT: Flask-JWT-Extended verwendet den 'msg'-Schlüssel
    data = response.get_json()
    assert 'msg' in data
    assert 'Missing Authorization Header' in data['msg']

def test_get_me_bad_token(client):
    """Test: Versuchter Abruf mit ungültigem Token -> 422 Unprocessable Entity."""
    headers = {'Authorization': 'Bearer not-a-real-token'}
    response = client.get('/api/auth/me', headers=headers)
    assert response.status_code == 422
    # KORRIGIERT: Flask-JWT-Extended verwendet den 'msg'-Schlüssel
    data = response.get_json()
    assert 'msg' in data
    assert 'Not enough segments' in data['msg']

def test_change_password_success(client, auth_headers_1, test_user_1_obj):
    """Test: Erfolgreiches Ändern des Passworts mit Verifizierung."""
    payload = {
        "old_password": "password123",
        "new_password": "a_new_secure_password"
    }
    response = client.post('/api/auth/change-password', headers=auth_headers_1, json=payload)
    assert response.status_code == 200
    assert "Password updated successfully" in response.get_json()['msg']

    # Verifizierung: Login mit neuem Passwort muss funktionieren
    login_response = client.post('/api/auth/login', json={
        'username': 'user1',
        'password': 'a_new_secure_password'
    })
    assert login_response.status_code == 200
    assert 'access_token' in login_response.get_json()

    # Gegen-Test: Login mit altem Passwort muss fehlschlagen
    failed_login_response = client.post('/api/auth/login', json={
        'username': 'user1',
        'password': 'password123'
    })
    assert failed_login_response.status_code == 401

def test_change_password_wrong_old_password(client, auth_headers_1, test_user_1_obj):
    """Test: Passwortänderung schlägt fehl, weil das alte Passwort falsch ist."""
    payload = {
        "old_password": "wrong_old_password",
        "new_password": "a_new_secure_password"
    }
    response = client.post('/api/auth/change-password', headers=auth_headers_1, json=payload)
    assert response.status_code == 401
    # KORRIGIERT: Die API sendet hier einen 'error'-Schlüssel
    assert "Invalid old password" in response.get_json()['error']
