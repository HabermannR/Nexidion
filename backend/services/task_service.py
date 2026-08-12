# backend/services/task_service.py

"""
Service-Schicht für Task-Operationen.

Diese Schicht enthält die Geschäftslogik für die Verwaltung von Tasks.
Sie wird von der API-Schicht (Blueprints) aufgerufen und interagiert
direkt mit den Datenbank-Models.
"""

from backend.models import db, Task, User, UserType
from backend.services.vault_service import _verify_vault_access

# Valid status values, used for validation across create and filter operations.
VALID_STATUSES = {'pending', 'processing', 'completed', 'failed'}


def create_task(vault_id: int, instruction: str, context_node_ids: list, user_id: int) -> Task:
    """
    Erstellt einen neuen Task für einen Vault, nachdem der Zugriff überprüft wurde.
    Wirft Fehler bei ungültigen Daten oder fehlenden Berechtigungen.
    """
    instruction_stripped = instruction.strip() if isinstance(instruction, str) else ""
    if not instruction_stripped:
        raise ValueError("Instruction cannot be empty.")
    if not isinstance(context_node_ids, list):
        raise ValueError("context_node_ids must be a list.")

    # 1. Always verify HUMAN vault access
    _verify_vault_access(vault_id, user_id)

    # 2. PRE-FLIGHT CHECK: Check if the LLM AGENT has access to the vault!
    # Resolve the agent user exactly like agent/loop.py does
    agent = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
    if not agent:
        raise PermissionError("System Error: No AI Agent user found in the database. Please run 'flask create-llm-agent' first.")

    try:
        # Test if the AI Agent is a member of this vault
        _verify_vault_access(vault_id, agent.id)
    except PermissionError:
        # If the LLM has no access, block the queue and throw an error to the frontend!
        raise PermissionError("Warning: The AI Agent does not have access to this vault. Please add the Agent as a member first.")

    try:
        task = Task(
            vault_id=vault_id,
            instruction=instruction_stripped,
            context_node_ids=context_node_ids,
            requested_by_id=user_id,
            executed_by_id=agent.id,
        )
        db.session.add(task)
        db.session.commit()
        return task
    except Exception as e:
        db.session.rollback()
        raise e


def get_tasks(vault_id: int, user_id: int, status: str | None = None, limit: int | None = None) -> list[Task]:
    """
    Ruft Tasks für einen Vault ab, optional gefiltert nach Status und mit einem Limit.

    Args:
        vault_id:  ID des Vaults, dessen Tasks abgerufen werden sollen.
        user_id:   ID des anfragenden Benutzers (für die Zugriffsprüfung).
        status:    Optionaler Statusfilter ('pending', 'processing', 'completed', 'failed').
        limit:     Optionale maximale Anzahl zurückgegebener Tasks (neueste zuerst).

    Raises:
        ValueError:     Wenn der Vault nicht gefunden wird oder der Status ungültig ist.
        PermissionError: Wenn der Benutzer keinen Zugriff auf den Vault hat.
    """
    # Zugriff auf den Vault prüfen
    _verify_vault_access(vault_id, user_id)

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}.")

    query = Task.query.filter_by(vault_id=vault_id).order_by(Task.created_at.desc())

    if status is not None:
        query = query.filter(Task.status == status)

    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("Limit must be a positive integer.")
        query = query.limit(limit)

    return query.all()


def get_task_by_id(task_id: str, user_id: int) -> Task:
    """
    Ruft einen einzelnen Task anhand seiner ID ab, nachdem der Zugriff überprüft wurde.

    Raises:
        ValueError:      Wenn der Task nicht gefunden wird.
        PermissionError: Wenn der Benutzer keinen Zugriff auf den zugehörigen Vault hat.
    """
    task = db.session.get(Task, task_id)
    if not task:
        raise ValueError(f"Task with ID '{task_id}' not found.")

    # Zugriff über den übergeordneten Vault prüfen
    _verify_vault_access(task.vault_id, user_id)
    return task
