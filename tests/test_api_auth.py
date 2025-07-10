# tests/test_api_auth.py
import json

def test_login_success(client, test_user_1_obj): # db_session durch test_user_1_obj ersetzen
    """
    Testet einen erfolgreichen Login.
    Die Fixture 'test_user_1_obj' stellt sicher, dass der Benutzer existiert.
    """
    response = client.post('/api/login',
                           data=json.dumps({
                               'username': 'user1',          # Angepasst an die Fixture
                               'password': 'password123'     # Angepasst an die Fixture
                           }),
                           content_type='application/json')

    assert response.status_code == 200 # Sollte jetzt funktionieren

def test_login_failure(client, db_session):
    """Testet einen Login mit falschem Passwort."""
    response = client.post('/api/login',
                           data=json.dumps({
                               'username': 'testuser',
                               'password': 'wrongpassword'
                           }),
                           content_type='application/json')

    # Erwarte einen 401 Unauthorized Fehler
    assert response.status_code == 401
    data = response.get_json()
    assert data['msg'] == 'Bad username or password'

def test_get_vaults_protected(client, test_user_1_obj): # db_session durch test_user_1_obj ersetzen
    """
    Testet einen geschützten Endpunkt.
    """
    # Schritt 1: Einloggen
    login_res = client.post('/api/login',
                            data=json.dumps({'username': 'user1', 'password': 'password123'}),
                            content_type='application/json')
    assert login_res.status_code == 200
    access_token = login_res.get_json()['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}

    # Schritt 2: Geschützte Anfrage
    vaults_res = client.get('/api/vaults', headers=headers)
    assert vaults_res.status_code == 200 # Der eigentliche Test

def test_get_vaults_unauthorized(client, db_session):
    """Testet den Zugriff auf einen geschützten Endpunkt ohne Token."""
    response = client.get('/api/vaults')
    
    # Erwarte einen 401 Fehler, weil der JWT fehlt
    assert response.status_code == 401