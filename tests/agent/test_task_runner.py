import json
import pytest
from unittest.mock import patch, MagicMock

from backend.models import Node, VaultAccess, VaultRole
from runner.audit import Audit
from runner.agent import run_agent

# Import for the subtree check (adjust if you redact in a custom tools.py wrapper instead)
#from runner.helpers import get_subtree_summary

BLACKLIST_ICON = "bxs-lock-alt"
READ_LOCK_ICON = "bxs-no-entry"

def run_agent_helper(task_row, audit, agent_id):
    """
    Helper function to wrap run_agent call with the required parameters
    that used to be hardcoded or resolved dynamically in loop.py.
    """
    return run_agent(
        task_row=task_row,
        audit=audit,
        agent_user_id=agent_id,
        gpt_token="dummy",
        gpt_model="gpt-4",
        local_llm_url=None,
        local_llm_api_key=None,
        max_loop_turns=5,
        max_tool_fetches=5,
        blacklist_icon=BLACKLIST_ICON,
        read_lock_icon=READ_LOCK_ICON,
        log_fn=lambda msg: None
    )


# ========================================================================
# FIXTURES FÜR DEN AGENTEN
# ========================================================================

@pytest.fixture
def setup_agent_env(db_session, test_vault_1_obj, test_llm_agent_obj, test_node_obj):
    """
    Bereitet die Umgebung für den Task Runner vor:
    Gibt dem LLM Agenten Zugriff auf den Test-Vault.
    """
    access = VaultAccess(user_id=test_llm_agent_obj.id, vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR.value)
    db_session.session.add(access)
    db_session.session.commit()

    class MockTask:
        id = "mock-task-1234"
        vault_id = test_vault_1_obj.id
        instruction = "Do the test task"
        context_node_ids = [test_node_obj.id]
        created_at = test_vault_1_obj.created_at

    return test_vault_1_obj, test_llm_agent_obj, test_node_obj, MockTask()


def create_mock_tool_call(name: str, arguments: dict):
    mock_item = MagicMock()
    mock_item.type = "function_call"
    mock_item.name = name
    mock_item.arguments = json.dumps(arguments)
    mock_item.call_id = f"call_{name}_123"
    return mock_item


# ========================================================================
# TESTS FÜR DIE WORKFLOWS (TOOL EXECUTION)
# ========================================================================

@patch("runner.agent.OpenAI")
def test_agent_workflow_write_node(mock_openai_class, setup_agent_env, db_session):
    vault, agent, node, mock_task = setup_agent_env

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("write_node", {
            "node_id": node.id,
            "content": "This is the newly written content by the agent.",
            "ai_summary": "- Bullet 1\n- Bullet 2\n- Bullet 3"
        }),
        create_mock_tool_call("finish", {"summary": "I updated the node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )

    task_row = {
        "instruction": "Update the node content.",
        "vault_id": vault.id,
        "context_node_ids": [node.id]
    }

    result_summary = run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    updated_node = db_session.session.get(Node, node.id)

    assert result_summary == "I updated the node."
    assert updated_node.current_version_object.content == "This is the newly written content by the agent."
    assert updated_node.ai_summary == "- Bullet 1\n- Bullet 2\n- Bullet 3"

    assert len(audit.writes) == 1
    assert audit.writes[0]["operation"] == "write_node"


@patch("runner.agent.OpenAI")
def test_agent_workflow_move_node(mock_openai_class, setup_agent_env, db_session):
    vault, agent, child_node, mock_task = setup_agent_env

    from backend.services.node_service import create_node
    parent_node = create_node("Target Parent", "", None, vault.id, agent.id)

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("move_node", {
            "node_id": child_node.id,
            "new_parent_id": parent_node.id
        }),
        create_mock_tool_call("finish", {"summary": "Moved the node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Move it.", "vault_id": vault.id, "context_node_ids": [child_node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    moved_node = db_session.session.get(Node, child_node.id)
    assert moved_node.parent_id == parent_node.id
    assert audit.writes[0]["operation"] == "move_node"


@patch("runner.agent.OpenAI")
def test_agent_workflow_protected_node_handling(mock_openai_class, setup_agent_env, db_session):
    vault, agent, node, mock_task = setup_agent_env

    original_content = node.current_version_object.content
    node.icon = BLACKLIST_ICON
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("write_node", {
            "node_id": node.id,
            "content": "MALICIOUS AGENT CONTENT",
            "ai_summary": "- Updated Summary 1\n- Updated Summary 2\n- Updated Summary 3"
        }),
        create_mock_tool_call("finish", {"summary": "Tried to override protected node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Hack it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    protected_node = db_session.session.get(Node, node.id)

    assert protected_node.current_version_object.content == original_content
    assert protected_node.current_version_object.content != "MALICIOUS AGENT CONTENT"
    assert "Updated Summary 1" in protected_node.ai_summary
    assert audit.writes[0]["operation"] == "write_node_summary_only"


@patch("runner.agent.OpenAI")
def test_agent_workflow_summary_validation_fails(mock_openai_class, setup_agent_env, db_session):
    vault, agent, node, mock_task = setup_agent_env
    original_content = node.current_version_object.content

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("write_node", {
            "node_id": node.id,
            "content": "New text",
            "ai_summary": "- Only one bullet point"
        }),
        create_mock_tool_call("finish", {"summary": "Done."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Write it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    unchanged_node = db_session.session.get(Node, node.id)

    assert unchanged_node.current_version_object.content == original_content
    assert audit.turns[0]["tool_calls"][0]["result"] == "error"
    assert "must be exactly 3 lines" in audit.turns[0]["tool_calls"][0]["detail"]


@patch("runner.agent.OpenAI")
def test_agent_workflow_fully_private_node_read(mock_openai_class, setup_agent_env, db_session):
    vault, agent, node, mock_task = setup_agent_env

    node.icon = READ_LOCK_ICON
    node.ai_summary = "- Secret 1\n- Secret 2\n- Secret 3"
    node.current_version_object.content = "Top Secret Content"
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("get_subtree", {"node_id": node.id}),
        create_mock_tool_call("get_node_summary", {"node_id": node.id}),
        create_mock_tool_call("get_node_content", {"node_id": node.id}),
        create_mock_tool_call("finish", {"summary": "Attempted to read private node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Read the private node.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    summary_call = audit.turns[0]["tool_calls"][1]
    assert summary_call["name"] == "get_node_summary"
    assert summary_call["result"] == "blocked"
    assert "private (bxs-no-entry)" in summary_call["detail"]

    content_call = audit.turns[0]["tool_calls"][2]
    assert content_call["name"] == "get_node_content"
    assert content_call["result"] == "blocked"
    assert "private (bxs-no-entry)" in content_call["detail"]


@patch("runner.agent.OpenAI")
def test_agent_workflow_fully_private_node_write(mock_openai_class, setup_agent_env, db_session):
    vault, agent, node, mock_task = setup_agent_env

    original_content = node.current_version_object.content
    node.icon = READ_LOCK_ICON
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("write_node", {
            "node_id": node.id,
            "content": "MALICIOUS OVERWRITE",
            "ai_summary": "- Write Sum 1\n- Write Sum 2\n- Write Sum 3"
        }),
        create_mock_tool_call("patch_node", {
            "node_id": node.id,
            "patches": [{"find": original_content[:5], "replace": "HACK"}],
            "ai_summary": "- Patch Sum 1\n- Patch Sum 2\n- Patch Sum 3"
        }),
        create_mock_tool_call("finish", {"summary": "Attempted to modify private node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Write and patch the private node.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    protected_node = db_session.session.get(Node, node.id)

    assert protected_node.current_version_object.content == original_content
    assert "MALICIOUS OVERWRITE" not in protected_node.current_version_object.content
    assert "HACK" not in protected_node.current_version_object.content

    assert "Patch Sum 1" in protected_node.ai_summary
    assert "Patch Sum 2" in protected_node.ai_summary

    write_call = audit.turns[0]["tool_calls"][0]
    assert write_call["name"] == "write_node"
    assert write_call["result"] == "ok"
    assert "summary was updated" in write_call["detail"]

    patch_call = audit.turns[0]["tool_calls"][1]
    assert patch_call["name"] == "patch_node"
    assert patch_call["result"] == "ok"
    assert "summary was updated" in patch_call["detail"]

    operations = [w["operation"] for w in audit.writes]
    assert "write_node_summary_only" in operations
    assert "patch_node_summary_only" in operations


@patch("runner.agent.OpenAI")
def test_agent_workflow_create_node(mock_openai_class, setup_agent_env, db_session):
    """
    Testet das erfolgreiche Erstellen eines neuen Nodes (create_node).
    """
    vault, agent, parent_node, mock_task = setup_agent_env

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("create_node", {
            "parent_id": parent_node.id,
            "title": "Brand New Node",
            "content": "Fresh content created by agent.",
            "ai_summary": "- Item 1\n- Item 2\n- Item 3"
        }),
        create_mock_tool_call("finish", {"summary": "Created a new node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Create it.", "vault_id": vault.id, "context_node_ids": [parent_node.id]}

    run_agent_helper(task_row, audit, agent.id)

    # Assertions
    db_session.session.expire_all()
    new_node = db_session.session.query(Node).filter_by(title="Brand New Node").first()

    assert new_node is not None
    assert new_node.parent_id == parent_node.id
    assert new_node.current_version_object.content == "Fresh content created by agent."
    assert "Item 1" in new_node.ai_summary

    assert len(audit.writes) == 1
    assert audit.writes[0]["operation"] == "create_node"


@patch("runner.agent.OpenAI")
def test_agent_workflow_patch_node_success(mock_openai_class, setup_agent_env, db_session):
    """
    Testet das erfolgreiche Patchen (patch_node) eines normalen Nodes.
    """
    vault, agent, node, mock_task = setup_agent_env

    node.current_version_object.content = "The quick brown fox jumps over the lazy dog."
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("patch_node", {
            "node_id": node.id,
            "patches": [{"find": "brown fox", "replace": "red fox"}],
            "ai_summary": "- Updated sum 1\n- Updated sum 2\n- Updated sum 3"
        }),
        create_mock_tool_call("finish", {"summary": "Patched the node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Patch it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    updated_node = db_session.session.get(Node, node.id)

    assert "red fox" in updated_node.current_version_object.content
    assert "brown fox" not in updated_node.current_version_object.content
    assert "Updated sum 1" in updated_node.ai_summary
    assert audit.writes[0]["operation"] == "patch_node"


@patch("runner.agent.OpenAI")
def test_agent_workflow_rename_node(mock_openai_class, setup_agent_env, db_session):
    """
    Testet das erfolgreiche Umbenennen eines Nodes (rename_node).
    """
    vault, agent, node, mock_task = setup_agent_env

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("rename_node", {
            "node_id": node.id,
            "title": "A Much Better Title"  # <--- Changed from new_title to title
        }),
        create_mock_tool_call("finish", {"summary": "Renamed the node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Rename it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    db_session.session.expire_all()
    updated_node = db_session.session.get(Node, node.id)

    assert updated_node.title == "A Much Better Title"
    assert audit.writes[0]["operation"] == "rename_node"


@patch("runner.agent.OpenAI")
def test_agent_workflow_search_nodes(mock_openai_class, setup_agent_env, db_session):
    """
    Testet, dass search_nodes erfolgreich aufgerufen wird und Ergebnisse liefert.
    """
    vault, agent, node, mock_task = setup_agent_env

    node.title = "A unique search keyword"
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("search_nodes", {
            "query": "unique search keyword"
        }),
        create_mock_tool_call("finish", {"summary": "Searched the vault."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Search it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    search_call = audit.turns[0]["tool_calls"][0]
    assert search_call["name"] == "search_nodes"
    assert search_call["result"] == "ok"
    assert "Found 1 results" in search_call["detail"]


@patch("runner.agent.OpenAI")
def test_agent_workflow_read_node_success(mock_openai_class, setup_agent_env, db_session):
    """
    Testet den unblockierten Lesezugriff (get_node_content und get_node_summary)
    auf normale (nicht private) Nodes.
    """
    vault, agent, node, mock_task = setup_agent_env

    node.current_version_object.content = "Very specific and accessible content."
    node.ai_summary = "- Fact 1\n- Fact 2\n- Fact 3"
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("get_node_summary", {"node_id": node.id}),
        create_mock_tool_call("get_node_content", {"node_id": node.id}),
        create_mock_tool_call("finish", {"summary": "Read everything."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = Audit(
        task_id=mock_task.id,
        vault_id=mock_task.vault_id,
        instruction=mock_task.instruction,
        context_node_ids=mock_task.context_node_ids,
        created_at=mock_task.created_at
    )
    task_row = {"instruction": "Read it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    run_agent_helper(task_row, audit, agent.id)

    summary_call = audit.turns[0]["tool_calls"][0]
    assert summary_call["name"] == "get_node_summary"
    assert summary_call["result"] == "ok"
    assert "detail" in summary_call

    content_call = audit.turns[0]["tool_calls"][1]
    assert content_call["name"] == "get_node_content"
    # Content reads can trigger context budget limits to protect the LLM.
    # As long as it is not 'blocked' or 'error', the tool executed successfully.
    assert content_call["result"] in ["ok", "budget"]
    assert "detail" in content_call