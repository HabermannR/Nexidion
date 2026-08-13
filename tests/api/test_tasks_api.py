import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def setup_llm_agent_and_access(db_session, test_llm_agent_obj):
    """
    Autouse fixture that ensures the LLM assistant agent user exists and
    bypasses pre-flight vault checks for the API testing endpoints.
    """
    from backend.services import task_service
    original_verify = task_service._verify_vault_access

    def patched_verify(vault_id, user_id):
        if user_id == test_llm_agent_obj.id:
            return True
        return original_verify(vault_id, user_id)

    with patch("backend.services.task_service._verify_vault_access", side_effect=patched_verify):
        yield


# ========================================================================
# CREATE TASK TESTS (POST /api/tasks)
# ========================================================================

def test_create_task_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Erstellen eines Tasks via API."""
    payload = {
        "vault_id": test_vault_1_obj.id,
        "instruction": "Please summarize these nodes.",
        "context_node_ids": ["node-xyz-123", "node-abc-456"]
    }

    response = client.post('/api/tasks', headers=auth_headers_1, json=payload)

    assert response.status_code == 201
    data = response.get_json()
    assert data['vault_id'] == test_vault_1_obj.id
    assert data['instruction'] == "Please summarize these nodes."
    assert data['context_node_ids'] == ["node-xyz-123", "node-abc-456"]
    assert data['status'] == "pending"
    assert 'id' in data


def test_create_task_with_llm_selection(client, auth_headers_1, test_vault_1_obj, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    response = client.post('/api/tasks', headers=auth_headers_1, json={
        "vault_id": test_vault_1_obj.id,
        "instruction": "Summarize these nodes.",
        "context_node_ids": [],
        "llm_provider": "openrouter",
        "llm_model": "google/gemini-2.5-flash",
    })
    assert response.status_code == 201
    assert response.get_json()["llm_provider"] == "openrouter"
    assert response.get_json()["llm_model"] == "google/gemini-2.5-flash"


def test_create_task_with_bounded_write_scope(client, auth_headers_1, test_node_obj):
    response = client.post('/api/tasks', headers=auth_headers_1, json={
        "vault_id": test_node_obj.vault_id,
        "instruction": "Bounded roll-up.",
        "context_node_ids": [test_node_obj.id],
        "allowed_write_node_ids": [test_node_obj.id],
        "allowed_write_operations": ["write_node"],
    })
    assert response.status_code == 201
    assert response.get_json()["allowed_write_node_ids"] == [test_node_obj.id]
    assert response.get_json()["allowed_write_operations"] == ["write_node"]


def test_create_ordered_task_batch_in_one_request(
        client, auth_headers_1, test_node_obj, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    jobs = [{
        "instruction": f"Bounded job {index}",
        "context_node_ids": [test_node_obj.id],
        "allowed_write_node_ids": [test_node_obj.id],
        "allowed_write_operations": ["write_node"],
    } for index in range(12)]
    response = client.post('/api/tasks/batch', headers=auth_headers_1, json={
        "vault_id": test_node_obj.vault_id,
        "llm_provider": "openrouter",
        "llm_model": "test/model",
        "jobs": jobs,
    })
    assert response.status_code == 201
    created = response.get_json()["tasks"]
    assert len(created) == 12
    assert [task["instruction"] for task in created] == [
        f"Bounded job {index}" for index in range(12)
    ]


def test_create_task_rejects_unknown_llm_provider(client, auth_headers_1, test_vault_1_obj):
    response = client.post('/api/tasks', headers=auth_headers_1, json={
        "vault_id": test_vault_1_obj.id,
        "instruction": "Summarize.",
        "llm_provider": "mystery",
        "llm_model": "model",
    })
    assert response.status_code == 400
    assert "llm_provider must be one of" in response.get_json()["error"]


def test_create_task_missing_vault_id(client, auth_headers_1):
    """Testet Fehler, wenn die Vault-ID im Payload fehlt."""
    payload = {
        "instruction": "Summarize this."
    }

    response = client.post('/api/tasks', headers=auth_headers_1, json=payload)

    assert response.status_code == 400
    assert "vault_id is required" in response.get_json()['error']


def test_create_task_empty_instruction(client, auth_headers_1, test_vault_1_obj):
    """Testet Fehler bei leerer Instruction, wie im Service definiert."""
    payload = {
        "vault_id": test_vault_1_obj.id,
        "instruction": "   "  # Leerer String/Whitespaces
    }

    response = client.post('/api/tasks', headers=auth_headers_1, json=payload)

    assert response.status_code == 400
    assert "Instruction cannot be empty" in response.get_json()['error']


def test_create_task_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Testet, dass User 2 keinen Task im Vault von User 1 erstellen darf."""
    payload = {
        "vault_id": test_vault_1_obj.id,
        "instruction": "Try to hack vault 1."
    }

    # Request wird mit den Headers von User 2 ausgeführt
    response = client.post('/api/tasks', headers=auth_headers_2, json=payload)

    assert response.status_code == 403


# ========================================================================
# LIST TASKS TESTS (GET /api/tasks)
# ========================================================================

def test_list_tasks_success(client, auth_headers_1, test_vault_1_obj, test_task_obj):
    """Testet das Abrufen der Tasks für einen spezifischen Vault."""
    response = client.get(f'/api/tasks?vault_id={test_vault_1_obj.id}', headers=auth_headers_1)

    assert response.status_code == 200
    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) >= 1
    # Der vorausgefüllte Task aus conftest.py sollte zurückgegeben werden
    assert data[0]['id'] == test_task_obj.id
    assert data[0]['status'] == "pending"


def test_list_tasks_missing_vault_id(client, auth_headers_1):
    """Testet Fehler, wenn kein vault_id Query-Parameter übergeben wird."""
    response = client.get('/api/tasks', headers=auth_headers_1)

    assert response.status_code == 400
    assert "vault_id query parameter is required" in response.get_json()['error']


def test_list_tasks_invalid_vault_id_format(client, auth_headers_1):
    """Testet Fehler, wenn vault_id kein gültiger Integer ist."""
    response = client.get('/api/tasks?vault_id=not-an-int', headers=auth_headers_1)

    assert response.status_code == 400
    assert "vault_id must be an integer" in response.get_json()['error']


def test_list_tasks_invalid_status_filter(client, auth_headers_1, test_vault_1_obj):
    """Testet Validierungsfehler bei ungültigem Task-Status."""
    response = client.get(
        f'/api/tasks?vault_id={test_vault_1_obj.id}&status=unknown',
        headers=auth_headers_1
    )

    assert response.status_code == 400
    assert "Invalid status" in response.get_json()['error']


def test_list_tasks_invalid_limit(client, auth_headers_1, test_vault_1_obj):
    """Testet Validierungsfehler bei ungültigem Limit."""
    response = client.get(
        f'/api/tasks?vault_id={test_vault_1_obj.id}&limit=-5',
        headers=auth_headers_1
    )

    assert response.status_code == 400
    assert "limit must be a positive integer" in response.get_json()['error']


def test_list_tasks_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Testet, dass User 2 die Tasks von User 1's Vault nicht auflisten darf."""
    response = client.get(f'/api/tasks?vault_id={test_vault_1_obj.id}', headers=auth_headers_2)

    assert response.status_code == 403


# ========================================================================
# GET SINGLE TASK TESTS (GET /api/tasks/<task_id>)
# ========================================================================

def test_get_task_success(client, auth_headers_1, test_task_obj):
    """Testet den Abruf eines einzelnen Tasks über die UUID."""
    response = client.get(f'/api/tasks/{test_task_obj.id}', headers=auth_headers_1)

    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == test_task_obj.id
    assert data['instruction'] == test_task_obj.instruction
    assert data['vault_id'] == test_task_obj.vault_id


def test_get_task_not_found(client, auth_headers_1):
    """Testet die Reaktion auf eine unbekannte Task-UUID."""
    fake_uuid = "12345678-1234-1234-1234-123456789012"
    response = client.get(f'/api/tasks/{fake_uuid}', headers=auth_headers_1)

    assert response.status_code == 404
    assert "not found" in response.get_json()['error']


def test_get_task_permission_denied(client, auth_headers_2, test_task_obj):
    """Testet, dass User 2 einen Task von User 1 nicht aufrufen kann."""
    response = client.get(f'/api/tasks/{test_task_obj.id}', headers=auth_headers_2)

    assert response.status_code == 403


# ========================================================================
# UNAUTHENTICATED TESTS
# ========================================================================

def test_unauthenticated_access(client, test_vault_1_obj, test_task_obj):
    """Sicherstellen, dass die Endpunkte ohne gültiges JWT abweisen."""
    # 1. GET /api/tasks
    res1 = client.get(f'/api/tasks?vault_id={test_vault_1_obj.id}')
    assert res1.status_code == 401

    # 2. GET /api/tasks/<id>
    res2 = client.get(f'/api/tasks/{test_task_obj.id}')
    assert res2.status_code == 401

    # 3. POST /api/tasks
    res3 = client.post('/api/tasks', json={"vault_id": test_vault_1_obj.id})
    assert res3.status_code == 401
