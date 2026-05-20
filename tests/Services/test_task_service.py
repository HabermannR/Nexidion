# tests/services/test_task_service.py

import pytest
from backend.services import task_service, vault_service
from backend.models import Task, VaultAccess, VaultRole



# ========================================================================
# CREATE TASK TESTS
# ========================================================================

def test_create_task_success(db_session, test_user_1_obj):
    """Testet das erfolgreiche Erstellen eines Tasks."""
    # ARRANGE
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Task-Create-Vault", user_id)

    instruction = "Fasse diese Dokumente zusammen"
    context_nodes = ["node-id-1", "node-id-2"]

    # ACT
    task = task_service.create_task(vault.id, instruction, context_nodes, user_id)

    # ASSERT
    assert isinstance(task, Task)
    assert task.id is not None
    assert task.vault_id == vault.id
    assert task.instruction == instruction
    assert task.context_node_ids == context_nodes
    assert task.status == "pending"  # Default-Wert prüfen

    # Sicherstellen, dass es in der DB ist
    db_task = db_session.session.get(Task, task.id)
    assert db_task is not None


def test_create_task_validation_errors(test_user_1_obj):
    """Testet, dass ungültige Eingaben abgefangen werden."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Validation-Vault", user_id)

    # 1. Leere Instruction
    with pytest.raises(ValueError, match="Instruction cannot be empty"):
        task_service.create_task(vault.id, "   ", [], user_id)

    # 2. context_node_ids ist keine Liste (sondern z.B. String oder None)
    with pytest.raises(ValueError, match="context_node_ids must be a list"):
        task_service.create_task(vault.id, "Valid Instruction", "not-a-list", user_id)


def test_create_task_permission_denied(test_user_1_obj, test_user_2_obj):
    """Testet, dass User 2 keinen Task in User 1's Vault erstellen kann."""
    vault = vault_service.create_vault("User1-Vault", test_user_1_obj.id)

    with pytest.raises(PermissionError):
        task_service.create_task(vault.id, "Hack the vault", [], test_user_2_obj.id)


# ========================================================================
# GET TASKS TESTS (LIST)
# ========================================================================

def test_get_tasks_success_and_ordering(db_session, test_user_1_obj):
    """Testet, dass Tasks abgerufen werden können und nach created_at (desc) sortiert sind."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("List-Vault", user_id)

    # Erstelle 3 Tasks
    task1 = task_service.create_task(vault.id, "Task 1", [], user_id)
    task2 = task_service.create_task(vault.id, "Task 2", [], user_id)
    task3 = task_service.create_task(vault.id, "Task 3", [], user_id)

    # ACT
    tasks = task_service.get_tasks(vault.id, user_id)

    # ASSERT
    assert len(tasks) == 3
    # Neueste zuerst (descending)
    assert tasks[0].id == task3.id
    assert tasks[1].id == task2.id
    assert tasks[2].id == task1.id


def test_get_tasks_with_status_filter(db_session, test_user_1_obj):
    """Testet das Filtern von Tasks nach Status."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Filter-Vault", user_id)

    # Tasks erstellen und Status manuell manipulieren (da create_task immer pending setzt)
    task1 = task_service.create_task(vault.id, "Pending Task", [], user_id)

    task2 = task_service.create_task(vault.id, "Completed Task", [], user_id)
    task2.status = "completed"

    task3 = task_service.create_task(vault.id, "Another Completed Task", [], user_id)
    task3.status = "completed"

    db_session.session.commit()

    # ACT
    completed_tasks = task_service.get_tasks(vault.id, user_id, status="completed")
    pending_tasks = task_service.get_tasks(vault.id, user_id, status="pending")

    # ASSERT
    assert len(completed_tasks) == 2
    assert all(t.status == "completed" for t in completed_tasks)

    assert len(pending_tasks) == 1
    assert pending_tasks[0].id == task1.id


def test_get_tasks_with_limit_filter(db_session, test_user_1_obj):
    """Testet die Limit-Funktion."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Limit-Vault", user_id)

    for i in range(5):
        task_service.create_task(vault.id, f"Task {i}", [], user_id)

    # ACT
    tasks = task_service.get_tasks(vault.id, user_id, limit=2)

    # ASSERT
    assert len(tasks) == 2


def test_get_tasks_validation_errors(test_user_1_obj):
    """Testet ungültige Parameter für get_tasks."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Invalid-Params-Vault", user_id)

    # Ungültiger Status
    with pytest.raises(ValueError, match="Invalid status"):
        task_service.get_tasks(vault.id, user_id, status="unknown-status")

    # Ungültiges Limit
    with pytest.raises(ValueError, match="Limit must be a positive integer"):
        task_service.get_tasks(vault.id, user_id, limit=-5)


# ========================================================================
# GET SINGLE TASK TESTS
# ========================================================================

def test_get_task_by_id_success(test_user_1_obj):
    """Testet den erfolgreichen Abruf eines einzelnen Tasks."""
    user_id = test_user_1_obj.id
    vault = vault_service.create_vault("Single-Task-Vault", user_id)

    created_task = task_service.create_task(vault.id, "Finde die Antwort", [], user_id)

    # ACT
    fetched_task = task_service.get_task_by_id(created_task.id, user_id)

    # ASSERT
    assert fetched_task.id == created_task.id
    assert fetched_task.instruction == "Finde die Antwort"


def test_get_task_by_id_not_found(test_user_1_obj):
    """Testet das Verhalten, wenn ein Task nicht existiert."""
    with pytest.raises(ValueError, match="not found"):
        task_service.get_task_by_id("fake-uuid-1234", test_user_1_obj.id)


def test_get_task_by_id_permission_denied(test_user_1_obj, test_user_2_obj):
    """Testet, dass man Tasks aus fremden Vaults nicht über die ID abrufen kann."""
    vault = vault_service.create_vault("User1-Private-Vault", test_user_1_obj.id)
    created_task = task_service.create_task(vault.id, "Geheimer Task", [], test_user_1_obj.id)

    # User 2 versucht auf den Task von User 1 zuzugreifen
    with pytest.raises(PermissionError):
        task_service.get_task_by_id(created_task.id, test_user_2_obj.id)

# ========================================================================
# LLM AGENT ACCESS TESTS
# ========================================================================

def test_llm_agent_task_permissions(db_session, test_user_1_obj, test_llm_agent_obj):
    """
    Testet, dass der LLM-Agent Tasks nur in Vaults erstellen/abrufen kann,
    für die er explizit freigeschaltet wurde.
    """
    owner_id = test_user_1_obj.id
    llm_id = test_llm_agent_obj.id

    # 1. Vaults erstellen
    vault_granted = vault_service.create_vault("Vault-With-LLM-Access", owner_id)
    vault_denied = vault_service.create_vault("Vault-Without-LLM-Access", owner_id)

    # 2. LLM-Agent explizit Zugriff auf den ersten Vault geben
    access = VaultAccess(user_id=llm_id, vault_id=vault_granted.id, role=VaultRole.EDITOR.value )
    db_session.session.add(access)
    db_session.session.commit()

    # 3. SUCCESS: LLM erstellt einen Task in Vault 1
    task = task_service.create_task(vault_granted.id, "Analysiere Dokumente", [], llm_id)
    assert task is not None
    assert task.vault_id == vault_granted.id

    # 4. SUCCESS: LLM ruft den Task in Vault 1 ab
    fetched_task = task_service.get_task_by_id(task.id, llm_id)
    assert fetched_task.id == task.id

    # 5. DENIED: LLM versucht einen Task in Vault 2 zu erstellen
    with pytest.raises(PermissionError):
        task_service.create_task(vault_denied.id, "Versuche einzudringen", [], llm_id)

    # 6. DENIED: LLM versucht Tasks aus Vault 2 aufzulisten
    with pytest.raises(PermissionError):
        task_service.get_tasks(vault_denied.id, llm_id)