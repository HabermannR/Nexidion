# backend/services/task_service.py

"""
Service-Schicht für Task-Operationen.

Diese Schicht enthält die Geschäftslogik für die Verwaltung von Tasks.
Sie wird von der API-Schicht (Blueprints) aufgerufen und interagiert
direkt mit den Datenbank-Models.
"""

import os

from backend.models import db, Node, SourceItem, Task, User, UserType
from backend.services.vault_service import (_verify_vault_access, assert_write_allowed,
                                            get_vault_access)

# Valid status values, used for validation across create and filter operations.
VALID_STATUSES = {'pending', 'processing', 'completed', 'failed'}
VALID_LLM_PROVIDERS = {'local', 'openai', 'openrouter'}
VALID_WRITE_OPERATIONS = {'write_node', 'patch_node', 'rename_node', 'move_node', 'create_node'}


def create_task(vault_id: int, instruction: str, context_node_ids: list, user_id: int,
                llm_provider: str | None = None, llm_model: str | None = None,
                allowed_write_node_ids: list | None = None,
                allowed_write_operations: list | None = None) -> Task:
    """
    Erstellt einen neuen Task für einen Vault, nachdem der Zugriff überprüft wurde.
    Wirft Fehler bei ungültigen Daten oder fehlenden Berechtigungen.
    """
    instruction_stripped = instruction.strip() if isinstance(instruction, str) else ""
    if not instruction_stripped:
        raise ValueError("Instruction cannot be empty.")
    if not isinstance(context_node_ids, list):
        raise ValueError("context_node_ids must be a list.")
    if llm_provider is not None:
        if not isinstance(llm_provider, str) or llm_provider not in VALID_LLM_PROVIDERS:
            raise ValueError(f"llm_provider must be one of: {', '.join(sorted(VALID_LLM_PROVIDERS))}.")
        configured = {
            'local': bool(os.environ.get('LOCAL_LLM_URL')),
            'openai': bool(os.environ.get('OPENAI_API_KEY')),
            'openrouter': bool(os.environ.get('OPENROUTER_API_KEY')),
        }
        if not configured[llm_provider]:
            raise ValueError(f"LLM provider '{llm_provider}' is not configured.")
    if llm_model is not None:
        if not isinstance(llm_model, str) or not llm_model.strip():
            raise ValueError("llm_model must be a non-empty string.")
        if len(llm_model.strip()) > 255:
            raise ValueError("llm_model must not exceed 255 characters.")
    if (allowed_write_node_ids is None) != (allowed_write_operations is None):
        raise ValueError("Both write-scope allowlists must be provided together.")
    if allowed_write_node_ids is not None:
        if not isinstance(allowed_write_node_ids, list) or not allowed_write_node_ids:
            raise ValueError("allowed_write_node_ids must be a non-empty list.")
        if not all(isinstance(node_id, str) for node_id in allowed_write_node_ids):
            raise ValueError("allowed_write_node_ids must contain strings.")
        if (not isinstance(allowed_write_operations, list) or not allowed_write_operations or
                not set(allowed_write_operations).issubset(VALID_WRITE_OPERATIONS)):
            raise ValueError("allowed_write_operations contains an unsupported operation.")

    # Task creation can mutate vault content, so viewer access is insufficient.
    vault, requester_role = get_vault_access(vault_id, user_id)
    assert_write_allowed(requester_role, db.session.get(User, user_id))
    if allowed_write_node_ids is not None:
        found = {row[0] for row in db.session.query(Node.id).filter(
            Node.vault_id == vault_id, Node.id.in_(set(allowed_write_node_ids)),
        ).all()}
        if found != set(allowed_write_node_ids):
            raise ValueError("Every allowed write node must belong to the task vault.")
        frozen = db.session.query(SourceItem.node_id).filter(
            SourceItem.node_id.in_(set(allowed_write_node_ids)),
            SourceItem.policy.in_(("snapshot", "managed")),
        ).first()
        if frozen:
            raise ValueError("A frozen connector-managed source cannot be included in the write scope.")

    # Resolve the service account exactly like agent/loop.py does.
    agent = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
    if not agent:
        raise PermissionError("System Error: No AI Agent user found in the database. Please run 'flask create-llm-agent' first.")

    try:
        _verify_vault_access(vault_id, agent.id)
    except PermissionError:
        raise PermissionError(
            "AI is disabled for this vault. Enable an AI agent in Vault access settings."
        )

    try:
        task = Task(
            vault_id=vault_id,
            instruction=instruction_stripped,
            context_node_ids=context_node_ids,
            llm_provider=llm_provider,
            llm_model=llm_model.strip() if llm_model else None,
            allowed_write_node_ids=allowed_write_node_ids,
            allowed_write_operations=allowed_write_operations,
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
