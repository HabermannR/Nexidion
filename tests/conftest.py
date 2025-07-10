# tests/conftest.py
import pytest
import json

# Passe die Importe an deine Projektstruktur an
from backend.app import create_app
from backend.models import db, User
from backend.database import create_vault_with_root_node
from backend.config import Config

# --- 1. Konfiguration für die Testumgebung ---
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    JWT_SECRET_KEY = 'super-secret-key-for-tests-only'


# --- 2. Basis-Fixtures für App und Client (Scope: module) ---
@pytest.fixture(scope='module')
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


# --- 3. Datenbank-Setup-Fixture (Scope: function) ---
@pytest.fixture(scope='function')
def db_session(app):
    """
    Garantiert eine saubere Datenbank für jeden einzelnen Test.
    Gibt das `db`-Objekt selbst zurück.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db # Gibt das db-Objekt zurück
        db.session.remove()
        db.drop_all()


# --- 4. Fixtures, die ORM-Objekte für direkte DB-Tests zurückgeben ---

@pytest.fixture(scope='function')
def test_user_1_obj(db_session):
    """Erstellt den ersten Test-Benutzer in der DB und gibt das SQLAlchemy-User-Objekt zurück."""
    user = User(username='user1', display_name='User One', user_type='human')
    user.set_password('password123')
    # === KORREKTUR HIER ===
    db_session.session.add(user)
    db_session.session.commit()
    return user

@pytest.fixture(scope='function')
def test_user_2_obj(db_session):
    """Erstellt einen ZWEITEN Test-Benutzer und gibt das SQLAlchemy-User-Objekt zurück."""
    user = User(username='user2', display_name='User Two', user_type='human')
    user.set_password('password456')
    # === KORREKTUR HIER ===
    db_session.session.add(user)
    db_session.session.commit()
    return user

@pytest.fixture(scope='function')
def test_vault_1_obj(test_user_1_obj):
    """Erstellt einen Vault für Benutzer 1 und gibt das SQLAlchemy-Vault-Objekt zurück."""
    vault = create_vault_with_root_node(name='Vault For User 1', owner_id=test_user_1_obj.id)
    return vault

@pytest.fixture(scope='function')
def test_vault_2_obj(test_user_2_obj):
    """Erstellt einen Vault für Benutzer 2 und gibt das SQLAlchemy-Vault-Objekt zurück."""
    vault = create_vault_with_root_node(name='Vault For User 2', owner_id=test_user_2_obj.id)
    return vault


# --- 5. Fixtures, die den Client für API-Integrationstests verwenden ---

@pytest.fixture(scope='function')
def auth_headers_1(client, test_user_1_obj):
    login_res = client.post('/api/login',
                            data=json.dumps({'username': 'user1', 'password': 'password123'}),
                            content_type='application/json')
    assert login_res.status_code == 200, "Login für user1 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}

@pytest.fixture(scope='function')
def auth_headers_2(client, test_user_2_obj):
    login_res = client.post('/api/login',
                            data=json.dumps({'username': 'user2', 'password': 'password456'}),
                            content_type='application/json')
    assert login_res.status_code == 200, "Login für user2 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}

@pytest.fixture(scope='function')
def test_vault_1(client, auth_headers_1):
    response = client.post('/api/vaults',
                           headers=auth_headers_1,
                           data=json.dumps({'name': 'API Test Vault 1'}),
                           content_type='application/json')
    assert response.status_code == 201
    yield response.get_json()

@pytest.fixture(scope='function')
def test_vault_2(client, auth_headers_2):
    response = client.post('/api/vaults',
                           headers=auth_headers_2,
                           data=json.dumps({'name': 'API Test Vault 2'}),
                           content_type='application/json')
    assert response.status_code == 201
    yield response.get_json()


# --- Optional: Aliase für Rückwärtskompatibilität ---
@pytest.fixture(scope='function')
def auth_headers(auth_headers_1):
    return auth_headers_1

@pytest.fixture(scope='function')
def test_vault(test_vault_1):
    return test_vault_1


# +++==============================================================+++
# |    NEUE FIXTURES FÜR PERSISTENTE INTEGRATIONSTESTS (ADD-ON)      |
# +++==============================================================+++
# These fixtures create a database state ONCE for an entire test file (module).

@pytest.fixture(scope='module')
def db_session_persistent(app):
    """
    Sets up the database ONCE per module for integration tests.
    It cleans the DB and seeds it with necessary data.
    """
    with app.app_context():
        # Clean the slate at the beginning of the module
        db.drop_all()
        db.create_all()

        # Seed the database with a user for integration tests
        integration_user = User(username='integration_user', display_name='Integration User', user_type='human')
        integration_user.set_password('integration_pass')
        db.session.add(integration_user)
        db.session.commit()

        yield db
        # Final cleanup is handled by the 'app' fixture teardown


@pytest.fixture(scope='module')
def auth_headers_persistent(client, db_session_persistent):
    """
    Logs in the persistent integration user ONCE per module and provides auth headers.
    """
    login_res = client.post('/api/login',
                            data=json.dumps({'username': 'integration_user', 'password': 'integration_pass'}),
                            content_type='application/json')
    assert login_res.status_code == 200, "Login für integration_user fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}

# +++==============================================================+++