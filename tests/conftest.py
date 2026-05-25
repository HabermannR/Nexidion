import os
import sys
import time
import pytest
from datetime import timedelta
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load the .env file
load_dotenv(os.path.join(project_root, 'backend', '.env'))

# --- OVERRIDE ENV VARS FOR TESTS BEFORE MODULES ARE IMPORTED ---
if os.getenv("DB_HOST") == "postgres" and not os.path.exists("/.dockerenv"):
    os.environ["DB_HOST"] = "localhost"

# Always use the test database for everything that runs in this process
os.environ["DB_NAME"] = "nexidion_test"

os.environ["TESTING"] = "true"

from backend.app import create_app
from backend.models import db, User, Vault, Node, Version, Task, VaultAccess, UserType, VaultRole
from backend.config import Config
Config.RATELIMIT_STORAGE_URI = "memory://"

# --- 1. Konfiguration für die Testumgebung ---
class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    JWT_SECRET_KEY = 'my-super-secret-test-key-string-32'
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_ENABLED = False

    # Verwende timedelta für höhere Kompatibilität mit neueren flask-jwt-extended Versionen
    JWT_LEEWAY = timedelta(seconds=60)

    # Grab user/pass from .env, but FORCE localhost and nexidion_test
    db_user = os.getenv("DB_USER", "nexidion_user")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    # If your .env says "postgres" but you are running locally (not in Docker),
    # override it to localhost so your computer can find the exposed port.
    if db_host == "postgres" and not os.path.exists("/.dockerenv"):
        db_host = "localhost"

    SQLALCHEMY_DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_host}:5432/nexidion_test"


# --- 2. Basis-Fixtures für App und Client ---
@pytest.fixture(scope='session')
def app():
    """Creates a standard Flask app for testing."""
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='session')
def client(app):
    """Provides a Flask test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """
    Garantiert eine saubere Datenbank für jeden einzelnen Test.
    Gibt das `db`-Objekt selbst zurück.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db
        db.session.rollback()
        db.session.remove()


# --- 3. User Fixtures (Direkt via ORM) ---

@pytest.fixture(scope='function')
def test_user_1_obj(db_session):
    """Standard Human User 1"""
    user = User(username='user1', display_name='User One', user_type=UserType.HUMAN)
    user.set_password('password123')
    db_session.session.add(user)
    db_session.session.commit()
    return user


@pytest.fixture(scope='function')
def test_user_2_obj(db_session):
    """Standard Human User 2"""
    user = User(username='user2', display_name='User Two', user_type=UserType.HUMAN)
    user.set_password('password456')
    db_session.session.add(user)
    db_session.session.commit()
    return user


@pytest.fixture(scope='function')
def test_admin_obj(db_session):
    """Admin User"""
    admin = User(username='admin', display_name='Admin User', user_type=UserType.HUMAN, is_admin=True)
    admin.set_password('admin123')
    db_session.session.add(admin)
    db_session.session.commit()
    return admin


@pytest.fixture(scope="function")
def test_llm_agent_obj(db_session):
    """The default LLM Agent account."""
    llm_user = User(username='default-llm', display_name='LLM Assistant', user_type=UserType.LLM_ASSISTANT)
    db_session.session.add(llm_user)
    db_session.session.commit()
    return llm_user

# --- 4. Content Fixtures (Vault, Node, Version, Task) ---
@pytest.fixture(scope='function')
def test_vault_1_obj(db_session, test_user_1_obj):
    """Erstellt einen Vault, der User 1 gehört."""
    vault = Vault(name='Vault For User 1', owner_id=test_user_1_obj.id)
    db_session.session.add(vault)
    db_session.session.commit()

    # Optional: Give User 1 explicit VaultAccess
    access = VaultAccess(user_id=test_user_1_obj.id, vault_id=vault.id, role=VaultRole.EDITOR)
    db_session.session.add(access)
    db_session.session.commit()

    return vault


@pytest.fixture(scope='function')
def test_vault_2_obj(db_session, test_user_2_obj):
    """Erstellt einen Vault, der User 2 gehört."""
    vault = Vault(name='Vault For User 2', owner_id=test_user_2_obj.id)
    db_session.session.add(vault)
    db_session.session.commit()

    # Explicit VaultAccess for User 2
    access = VaultAccess(user_id=test_user_2_obj.id, vault_id=vault.id, role=VaultRole.EDITOR)
    db_session.session.add(access)
    db_session.session.commit()

    return vault


@pytest.fixture(scope='function')
def test_node_obj(db_session, test_vault_1_obj, test_user_1_obj):
    """
    Erstellt einen Basis-Node mit dazugehöriger initialer Version (V1).
    Weil Title und Content nun im Version-Model liegen, müssen wir beides anlegen.
    """
    node = Node(vault_id=test_vault_1_obj.id, current_version=1)
    db_session.session.add(node)
    db_session.session.flush()  # Generates the Node UUID

    version = Version(
        node_id=node.id,
        author_id=test_user_1_obj.id,
        version=1,
        title="Test Node",
        content="This is the content of the test node."
    )
    db_session.session.add(version)
    db_session.session.commit()
    return node


@pytest.fixture(scope='function')
def test_task_obj(db_session, test_vault_1_obj):
    """Erstellt einen ausstehenden (pending) Task für den Task Runner."""
    task = Task(
        vault_id=test_vault_1_obj.id,
        instruction="Please summarize the test node.",
        status="pending",
        context_node_ids=[]  # Kann im Test selbst überschrieben werden
    )
    db_session.session.add(task)
    db_session.session.commit()
    return task


# --- 5. Authentifizierungs-Fixtures (API Tests) ---

@pytest.fixture(scope='function')
def auth_headers_1(client, test_user_1_obj):
    login_res = client.post('/api/auth/login',
                            json={'username': 'user1', 'password': 'password123'})
    assert login_res.status_code == 200, "Login für user1 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']

    # Verhindert PyJWT 'The token is not yet valid (iat)' Exceptions bei schnellen Tests
    time.sleep(0.05)

    return {'Authorization': f'Bearer {access_token}'}


@pytest.fixture(scope='function')
def auth_headers_2(client, test_user_2_obj):
    login_res = client.post('/api/auth/login',
                            json={'username': 'user2', 'password': 'password456'})
    assert login_res.status_code == 200, "Login für user2 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']

    # Verhindert PyJWT 'The token is not yet valid (iat)' Exceptions bei schnellen Tests
    time.sleep(0.05)

    return {'Authorization': f'Bearer {access_token}'}


@pytest.fixture(scope='function')
def admin_headers(client, test_admin_obj):
    login_res = client.post('/api/auth/login',
                            json={'username': 'admin', 'password': 'admin123'})
    assert login_res.status_code == 200, "Login für admin fehlgeschlagen"
    access_token = login_res.get_json()['access_token']

    # Verhindert PyJWT 'The token is not yet valid (iat)' Exceptions bei schnellen Tests
    time.sleep(0.05)

    return {'Authorization': f'Bearer {access_token}'}


# --- Optional: Alias ---
@pytest.fixture(scope='function')
def auth_headers(auth_headers_1):
    return auth_headers_1


@pytest.fixture(scope='function')
def test_vault(test_vault_1_obj):
    return test_vault_1_obj