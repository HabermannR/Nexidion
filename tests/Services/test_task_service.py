# tests/Services/test_task_service.py

import pytest
from unittest.mock import patch
from backend.services import node_service, task_service, vault_service



@pytest.fixture(autouse=True)
def setup_llm_agent_and_access(db_session, test_llm_agent_obj):
    """
    Autouse fixture that ensures the LLM assistant agent user exists,
    and patches _verify_vault_access to automatically grant access to the LLM agent
    so that task creation pre-flight checks pass.
    """
    from backend.services import task_service
    original_verify = task_service._verify_vault_access

    def patched_verify(vault_id, user_id):
        # If checking access for the LLM agent, automatically allow it
        if user_id == test_llm_agent_obj.id:
            return True
        return original_verify(vault_id, user_id)

    with patch("backend.services.task_service._verify_vault_access", side_effect=patched_verify):
        yield


def test_create_task_success(db_session, test_user_1_obj):
    """Testet das erfolgreiche Erstellen eines Tasks."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Task-Create-Vault", user_id)

    instruction = "Fasse diese Dokumente zusammen"
    context_nodes = [
        node_service.create_node("Context 1", "one", None, vault.id, user_id).id,
        node_service.create_node("Context 2", "two", None, vault.id, user_id).id,
    ]

    task = task_service.create_task(vault.id, instruction, context_nodes, user_id)

    assert task is not None
    assert task.vault_id == vault.id
    assert task.instruction == instruction
    assert task.context_node_ids == context_nodes
    assert task.status == "pending"

    from backend.models import VaultAccess, VaultRole
    agent_access = VaultAccess.query.filter_by(
        vault_id=vault.id, user_id=task.executed_by_id,
    ).one()
    assert agent_access.role == VaultRole.EDITOR.value


def test_create_task_persists_explicit_llm_selection(db_session, test_user_1_obj, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    vault = vault_service.create_vault("Task-Provider-Vault", test_user_1_obj.id)

    task = task_service.create_task(
        vault.id, "Summarize", [], test_user_1_obj.id,
        llm_provider="openrouter", llm_model="anthropic/claude-sonnet-4",
    )

    assert task.llm_provider == "openrouter"
    assert task.llm_model == "anthropic/claude-sonnet-4"
    assert task.to_dict()["llm_provider"] == "openrouter"


def test_create_task_rejects_unconfigured_llm_provider(db_session, test_user_1_obj, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    vault = vault_service.create_vault("Task-Unconfigured-Provider", test_user_1_obj.id)
    with pytest.raises(ValueError, match="not configured"):
        task_service.create_task(
            vault.id, "Summarize", [], test_user_1_obj.id,
            llm_provider="openrouter", llm_model="some/model",
        )


def test_create_task_persists_vault_scoped_write_policy(
        db_session, test_user_1_obj, test_node_obj):
    task = task_service.create_task(
        test_node_obj.vault_id, "Bounded write", [test_node_obj.id], test_user_1_obj.id,
        allowed_write_node_ids=[test_node_obj.id],
        allowed_write_operations=["write_node"],
    )
    assert task.allowed_write_node_ids == [test_node_obj.id]
    assert task.allowed_write_operations == ["write_node"]


def test_create_task_rejects_write_node_from_another_vault(
        db_session, test_user_1_obj, test_node_obj):
    vault = vault_service.create_vault("Other write scope", test_user_1_obj.id)
    with pytest.raises(ValueError, match="must belong to the task vault"):
        task_service.create_task(
            vault.id, "Cross-vault write", [], test_user_1_obj.id,
            allowed_write_node_ids=[test_node_obj.id],
            allowed_write_operations=["write_node"],
        )


def test_create_task_empty_instruction(db_session, test_user_1_obj):
    """Testet, dass eine leere Instruction einen Fehler wirft."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Task-Create-Vault", user_id)

    with pytest.raises(ValueError, match="Instruction cannot be empty."):
        task_service.create_task(vault.id, "   ", [], user_id)


def test_create_task_invalid_context_nodes(db_session, test_user_1_obj):
    """Testet, dass context_node_ids eine Liste sein muss."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Task-Create-Vault", user_id)

    with pytest.raises(ValueError, match="context_node_ids must be a list."):
        task_service.create_task(vault.id, "Instruction", "not-a-list", user_id)


def test_create_task_permission_denied(db_session, test_user_1_obj, test_user_2_obj):
    """Testet, dass ein Benutzer ohne Zugriff auf den Vault keine Tasks erstellen kann."""
    vault = vault_service.create_vault("User1-Vault", test_user_1_obj.id)

    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        task_service.create_task(vault.id, "Do something", [], test_user_2_obj.id)


def test_get_tasks_success_and_ordering(db_session, test_user_1_obj):
    """Testet, dass Tasks abgerufen werden können und nach created_at (desc) sortiert sind."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("List-Vault", user_id)

    # Erstelle 3 Tasks
    task1 = task_service.create_task(vault.id, "Task 1", [], user_id)
    task2 = task_service.create_task(vault.id, "Task 2", [], user_id)
    task3 = task_service.create_task(vault.id, "Task 3", [], user_id)

    tasks = task_service.get_tasks(vault.id, user_id)

    assert len(tasks) == 3
    # Neueste zuerst
    assert tasks[0].id == task3.id
    assert tasks[1].id == task2.id
    assert tasks[2].id == task1.id


def test_get_tasks_with_status_filter(db_session, test_user_1_obj):
    """Testet das Filtern von Tasks nach Status."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Filter-Vault", user_id)

    # Tasks erstellen und Status manuell manipulieren (da create_task immer pending setzt)
    task1 = task_service.create_task(vault.id, "Pending Task", [], user_id)
    task2 = task_service.create_task(vault.id, "Processing Task", [], user_id)
    task3 = task_service.create_task(vault.id, "Completed Task", [], user_id)

    task2.status = 'processing'
    task3.status = 'completed'
    db_session.session.commit()

    pending_tasks = task_service.get_tasks(vault.id, user_id, status='pending')
    assert len(pending_tasks) == 1
    assert pending_tasks[0].id == task1.id

    processing_tasks = task_service.get_tasks(vault.id, user_id, status='processing')
    assert len(processing_tasks) == 1
    assert processing_tasks[0].id == task2.id


def test_get_tasks_with_limit_filter(db_session, test_user_1_obj):
    """Testet die Limit-Funktion."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Limit-Vault", user_id)

    for i in range(5):
        task_service.create_task(vault.id, f"Task {i}", [], user_id)

    tasks = task_service.get_tasks(vault.id, user_id, limit=3)
    assert len(tasks) == 3


def test_get_tasks_invalid_status_raises(db_session, test_user_1_obj):
    """Testet, dass ein ungültiger Status-Filter einen Fehler wirft."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Invalid-Filter-Vault", user_id)

    with pytest.raises(ValueError, match="Invalid status"):
        task_service.get_tasks(vault.id, user_id, status="invalid_status_string")


def test_get_tasks_invalid_limit_raises(db_session, test_user_1_obj):
    """Testet, dass ein ungültiges Limit einen Fehler wirft."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Invalid-Limit-Vault", user_id)

    with pytest.raises(ValueError, match="Limit must be a positive integer."):
        task_service.get_tasks(vault.id, user_id, limit=-5)


def test_get_task_by_id_success(db_session, test_user_1_obj):
    """Testet den erfolgreichen Abruf eines einzelnen Tasks."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Single-Task-Vault", user_id)

    created_task = task_service.create_task(vault.id, "Finde die Antwort", [], user_id)

    retrieved_task = task_service.get_task_by_id(created_task.id, user_id)
    assert retrieved_task.id == created_task.id
    assert retrieved_task.instruction == "Finde die Antwort"


def test_get_task_by_id_not_found(db_session, test_user_1_obj):
    """Testet, dass das Abrufen eines nicht existenten Tasks einen Fehler wirft."""
    user_id = test_user_1_obj.id

    with pytest.raises(ValueError, match="Task with ID 'non-existent' not found."):
        task_service.get_task_by_id("non-existent", user_id)


def test_get_task_by_id_permission_denied(db_session, test_user_1_obj, test_user_2_obj):
    """Testet, dass man Tasks aus fremden Vaults nicht über die ID abrufen kann."""
    vault = vault_service.create_vault("User1-Private-Vault", test_user_1_obj.id)
    created_task = task_service.create_task(vault.id, "Geheimer Task", [], test_user_1_obj.id)

    with pytest.raises(PermissionError, match='You do not have permission to access this vault.'):
        task_service.get_task_by_id(created_task.id, test_user_2_obj.id)
