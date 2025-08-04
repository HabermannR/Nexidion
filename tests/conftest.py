# tests/conftest.py
import pytest
import json
import os

# Passe die Importe an deine Projektstruktur an
from backend.app import create_app
from backend.models import db, User, ChatSession, ChatMessage, Node
from backend.config import Config
from backend.services import vault_service, node_service

# --- 1. Konfiguration für die Testumgebung ---
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    JWT_SECRET_KEY = 'super-secret-key-for-tests-only'


# --- 2. Basis-Fixtures für App und Client (Scope: module) ---
@pytest.fixture(scope='module')
def app():
    # Now create the app. It will be built with the correct configuration.
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
    """
    Erstellt einen Vault für Benutzer 1 direkt über den Service.
    Dies ist die sauberste Methode, da sie die API umgeht.
    """
    vault = vault_service.create_vault(name='Vault For User 1', owner_id=test_user_1_obj.id)
    return vault

@pytest.fixture(scope='function')
def test_vault_2_obj(test_user_2_obj):
    """Erstellt einen Vault für Benutzer 2 direkt über den Service."""
    vault = vault_service.create_vault(name='Vault For User 2', owner_id=test_user_2_obj.id)
    return vault


# --- 5. Fixtures, die den Client für API-Integrationstests verwenden ---

@pytest.fixture(scope='function')
def auth_headers_1(client, test_user_1_obj):
    login_res = client.post('/api/auth/login',
                            data=json.dumps({'username': 'user1', 'password': 'password123'}),
                            content_type='application/json')
    assert login_res.status_code == 200, "Login für user1 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}

@pytest.fixture(scope='function')
def auth_headers_2(client, test_user_2_obj):
    login_res = client.post('/api/auth/login',
                            data=json.dumps({'username': 'user2', 'password': 'password456'}),
                            content_type='application/json')
    assert login_res.status_code == 200, "Login für user2 fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}


# --- Optional: Aliase für Rückwärtskompatibilität ---
@pytest.fixture(scope='function')
def auth_headers(auth_headers_1):
    return auth_headers_1

# NOTE: This alias was pointing to a non-existent fixture 'test_vault_1'.
# Correcting it to point to 'test_vault_1_obj'.
@pytest.fixture(scope='function')
def test_vault(test_vault_1_obj):
    return test_vault_1_obj


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
    login_res = client.post('/api/auth/login',
                            json={'username': 'integration_user', 'password': 'integration_pass'})
    assert login_res.status_code == 200, "Login für integration_user fehlgeschlagen"
    access_token = login_res.get_json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}


@pytest.fixture
def proposal_setup(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Stellt die Datenbankobjekte für die Proposal-Tests bereit:
    - Einen Kontext-Node
    - Einen Ziel-Node
    - Eine Chat-Session mit Verlauf
    Gibt ein Dictionary mit den relevanten IDs zurück.

    ### KORREKTUR ###
    Die Argumente 'node_service', 'ChatSession', 'ChatMessage' und 'Node' wurden aus der
    Signatur entfernt, da sie keine Fixtures sind. Sie werden stattdessen direkt importiert.
    """
    # Hol den Root-Node, der beim Erstellen des Vaults angelegt wurde.
    root_node = db_session.session.query(Node).filter_by(
        vault_id=test_vault_1_obj.id,
        parent_id=None
    ).one()

    # Erstelle die nötigen Nodes. Wir verwenden das importierte `node_service`-Modul.
    context_node_dict = node_service.create_node(
        title="Project Requirements",
        content="The project must be completed by Q4.",
        parent_id=root_node.id, vault_id=test_vault_1_obj.id, author_id=test_user_1_obj.id
    )

    target_node_dict = node_service.create_node(
        title="Team Allocation",
        content="Current team: Alice (Lead).",
        parent_id=root_node.id, vault_id=test_vault_1_obj.id, author_id=test_user_1_obj.id
    )

    # Erstelle die Chat-Historie. Wir verwenden die importierten Modell-Klassen.
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_user_1_obj.id)
    msg1 = ChatMessage(session=session, role='user', content="Who else should be on the team?",
                       author_id=test_user_1_obj.id, sort_order=1)
    msg2 = ChatMessage(session=session, role='assistant', content="We should add Bob and Carol.",
                       author_id=test_user_1_obj.id, sort_order=2)

    db_session.session.add_all([session, msg1, msg2])
    db_session.session.commit()

    # Gib alle nötigen Informationen als Dictionary zurück
    return {
        "user_id": test_user_1_obj.id,
        "session_id": session.id,
        "target_node_id": target_node_dict['id'],
        "context_node_ids": [context_node_dict['id']]
    }


# =========================================================================
# |            MODULAR LLM TEST GENERATION (UPDATED AND EXPANDED)         |
# =========================================================================

# --- 1. Centralized Model Definitions ---
# This makes it easy to add new models or update model names in one place.
AVAILABLE_MODELS = {
    'local': 'local',
    'gemini': 'gemini-2.5-flash',
    'openai': 'gpt-4o-mini',
    'claude': 'claude-3-5-haiku-20241022',
}

# --- 2. Helper Dictionaries for Cloud Models ---
# This maps the internal model key to its required environment variable for the API key.
# It's highly scalable: to add a new cloud provider, just add an entry here.
API_KEY_ENV_VARS = {
    'gemini': 'GEMINI_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'claude': 'ANTHROPIC_API_KEY', # Anthropic's official env var name
}
# A set for quick lookups to see if a model is a cloud-based one.
CLOUD_MODELS = set(API_KEY_ENV_VARS.keys())


def pytest_addoption(parser):
    """Adds the --llm command-line option to pytest with expanded choices."""
    parser.addoption(
        "--llm",
        action="store",
        default="none",
        choices=[
            'none',           # Skips all LLM tests
            'local',          # Runs only local model tests
            'gemini',         # Runs only Gemini tests
            'openai',         # Runs only OpenAI tests
            'claude',         # Runs only Claude tests
            'local-gemini',   # Runs local and Gemini tests
            'local-openai',   # Runs local and OpenAI tests
            'local-claude',   # Runs local and Claude tests
            'all'             # Runs local and all cloud models
        ],
        help=(
            "Specify which LLM(s) to run E2E tests against. "
            "Cloud models (gemini, openai, claude) require their respective API keys "
            "to be set as environment variables (e.g., GEMINI_API_KEY). "
            "Examples: --llm=local, --llm=local-openai, --llm=all"
        )
    )


def pytest_generate_tests(metafunc):
    """
    This hook dynamically creates test cases based on the --llm flag.
    It looks for tests that request the 'llm_model_name' fixture.
    """
    if 'llm_model_name' not in metafunc.fixturenames:
        return # This test doesn't need LLM parametrization, so we do nothing.

    llm_option = metafunc.config.getoption("--llm")

    # Determine which models were requested based on the command-line option.
    # This logic is clean and scalable. E.g., 'local-openai' becomes ['local', 'openai'].
    requested_keys = []
    if llm_option == 'none':
        pass # The list remains empty
    elif llm_option == 'all':
        requested_keys = list(AVAILABLE_MODELS.keys())
    else:
        requested_keys = llm_option.split('-')

    # Build the list of pytest parameters, adding skip logic for cloud models.
    models_to_run = []
    for key in requested_keys:
        if key not in AVAILABLE_MODELS:
            continue # Should not happen due to 'choices' in addoption, but safe to have.

        model_name = AVAILABLE_MODELS[key]

        if key in CLOUD_MODELS:
            # For cloud models, create a 'pytest.param' that carries its own skip logic.
            # This logic runs *after* the .env file is loaded, solving the timing problem.
            env_var = API_KEY_ENV_VARS[key]
            param = pytest.param(
                model_name,
                marks=pytest.mark.skipif(
                    not os.environ.get(env_var),
                    reason=f"{env_var} not set in environment variables"
                )
            )
            models_to_run.append(param)
        else:
            # For the 'local' model, no special logic is needed.
            models_to_run.append(model_name)


    # If the final list is empty (e.g., --llm=none), we explicitly skip the test.
    if not models_to_run:
        pytest.skip("Skipping LLM tests. Use --llm=[local|gemini|openai|claude|all|...] to run.")

    # This is the magic: Pytest will now create variants of the test function,
    # feeding each entry from 'models_to_run' into the 'llm_model_name' fixture.
    metafunc.parametrize("llm_model_name", models_to_run)