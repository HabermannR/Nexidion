import json
import pytest
from unittest.mock import patch, MagicMock

# Importiere den task_runner. Da er auf Modul-Ebene Flask initialisiert,
# stellen wir sicher, dass dies innerhalb der Test-Umgebung sauber läuft.
import task_runner
from backend.models import Node, VaultAccess, VaultRole


# ========================================================================
# FIXTURES FÜR DEN AGENTEN
# ========================================================================

@pytest.fixture
def setup_agent_env(db_session, test_vault_1_obj, test_llm_agent_obj, test_node_obj, monkeypatch):
    """
    Bereitet die Umgebung für den Task Runner vor:
    1. Gibt dem LLM Agenten Zugriff auf den Test-Vault.
    2. Setzt die AGENT_USER_ID im task_runner auf die dynamische ID unseres Test-Agents.
    """
    access = VaultAccess(user_id=test_llm_agent_obj.id, vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR.value)
    db_session.session.add(access)
    db_session.session.commit()

    monkeypatch.setattr(task_runner, "AGENT_USER_ID", test_llm_agent_obj.id)

    # Erstelle einen leeren Dummy-Task für das Audit-Objekt
    class MockTask:
        id = "mock-task-1234"
        vault_id = test_vault_1_obj.id
        instruction = "Do the test task"
        context_node_ids = [test_node_obj.id]
        created_at = test_vault_1_obj.created_at  # Fallback Timestamp

    return test_vault_1_obj, test_llm_agent_obj, test_node_obj, MockTask()


def create_mock_tool_call(name: str, arguments: dict):
    """Hilfsfunktion zum Erstellen einer gemockten Tool-Call-Antwort von OpenAI."""
    mock_item = MagicMock()
    mock_item.type = "function_call"
    mock_item.name = name
    mock_item.arguments = json.dumps(arguments)
    mock_item.call_id = f"call_{name}_123"
    return mock_item


# ========================================================================
# TESTS FÜR DIE WORKFLOWS (TOOL EXECUTION)
# ========================================================================

@patch("task_runner.OpenAI")
def test_agent_workflow_write_node(mock_openai_class, setup_agent_env, db_session):
    """
    Simuliert, dass das LLM entscheidet, einen Node zu überschreiben und danach abzuschließen.
    """
    vault, agent, node, mock_task = setup_agent_env

    # 1. OpenAI Client Mock konfigurieren
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    # Simuliere die Antwort in Turn 1: Das LLM ruft `write_node` und `finish` auf
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

    # 2. Audit-Log initialisieren und Agenten starten
    audit = task_runner.Audit(mock_task)

    task_row = {
        "instruction": "Update the node content.",
        "vault_id": vault.id,
        "context_node_ids": [node.id]
    }

    # 3. Agenten-Loop ausführen
    result_summary = task_runner.run_agent(task_row, audit)

    # 4. Assertions: Wurde die DB wirklich verändert?
    db_session.session.expire_all()
    updated_node = db_session.session.get(Node, node.id)

    assert result_summary == "I updated the node."
    assert updated_node.current_version_object.content == "This is the newly written content by the agent."
    assert updated_node.ai_summary == "- Bullet 1\n- Bullet 2\n- Bullet 3"

    # Prüfen, ob das Audit-Log den Schreibvorgang registriert hat
    assert len(audit.writes) == 1
    assert audit.writes[0]["operation"] == "write_node"


@patch("task_runner.OpenAI")
def test_agent_workflow_move_node(mock_openai_class, setup_agent_env, db_session):
    """
    Simuliert, dass das LLM einen Node verschiebt (reparenting).
    """
    vault, agent, child_node, mock_task = setup_agent_env

    # Erstelle einen neuen Parent-Node in der Datenbank
    from backend.services.node_service import create_node
    parent_node = create_node("Target Parent", "", None, vault.id, agent.id)

    # Mocks einrichten
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

    audit = task_runner.Audit(mock_task)
    task_row = {"instruction": "Move it.", "vault_id": vault.id, "context_node_ids": [child_node.id]}

    # Ausführen
    task_runner.run_agent(task_row, audit)

    # Assertions
    db_session.session.expire_all()
    moved_node = db_session.session.get(Node, child_node.id)
    assert moved_node.parent_id == parent_node.id
    assert audit.writes[0]["operation"] == "move_node"


@patch("task_runner.OpenAI")
def test_agent_workflow_protected_node_handling(mock_openai_class, setup_agent_env, db_session):
    """
    Sicherstellen, dass der Agent bei Protected Nodes (bxs-lock-alt) den Content
    nicht überschreiben kann, die AI-Summary aber aktualisiert wird.
    """
    vault, agent, node, mock_task = setup_agent_env

    # Node "schützen"
    original_content = node.current_version_object.content
    node.icon = task_runner.BLACKLIST_ICON
    db_session.session.commit()

    # Agent versucht, den Node komplett zu überschreiben
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

    audit = task_runner.Audit(mock_task)
    task_row = {"instruction": "Hack it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    task_runner.run_agent(task_row, audit)

    db_session.session.expire_all()
    protected_node = db_session.session.get(Node, node.id)

    # WICHTIG: Der Content MUSS gleich geblieben sein!
    assert protected_node.current_version_object.content == original_content
    assert protected_node.current_version_object.content != "MALICIOUS AGENT CONTENT"

    # WICHTIG: Die Summary DARF aktualisiert worden sein
    assert "Updated Summary 1" in protected_node.ai_summary

    # Prüfen, ob das Audit dies korrekt als 'write_node_summary_only' verbucht hat
    assert audit.writes[0]["operation"] == "write_node_summary_only"


@patch("task_runner.OpenAI")
def test_agent_workflow_summary_validation_fails(mock_openai_class, setup_agent_env, db_session):
    """
    Testet, dass das Tool fehlschlägt, wenn die AI-Summary nicht genau 3 Bulletpoints hat.
    Das LLM sollte einen Error-String zurückbekommen und der Node bleibt unverändert.
    """
    vault, agent, node, mock_task = setup_agent_env
    original_content = node.current_version_object.content

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("write_node", {
            "node_id": node.id,
            "content": "New text",
            "ai_summary": "- Only one bullet point"  # FEHLER: Müssen 3 sein
        }),
        create_mock_tool_call("finish", {"summary": "Done."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = task_runner.Audit(mock_task)
    task_row = {"instruction": "Write it.", "vault_id": vault.id, "context_node_ids": [node.id]}

    task_runner.run_agent(task_row, audit)

    db_session.session.expire_all()
    unchanged_node = db_session.session.get(Node, node.id)

    # Content darf NICHT geschrieben worden sein
    assert unchanged_node.current_version_object.content == original_content

    # Im Audit sollte ein Fehler für diesen Tool-Call stehen
    assert audit.turns[0]["tool_calls"][0]["result"] == "error"
    assert "must be exactly 3 lines" in audit.turns[0]["tool_calls"][0]["detail"]

@patch("task_runner.OpenAI")
def test_agent_workflow_fully_private_node_read(mock_openai_class, setup_agent_env, db_session):
    """
    Tests that a fully private node (bxs-no-entry) blocks the agent from
    reading the summary or the content, and correctly redacts data in get_subtree.
    """
    vault, agent, node, mock_task = setup_agent_env

    # 1. Make the node fully private (Read and Write locked)
    node.icon = task_runner.READ_LOCK_ICON
    node.ai_summary = "- Secret 1\n- Secret 2\n- Secret 3"
    node.current_version_object.content = "Top Secret Content"
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    # 2. Agent tries to read the node using all available read tools
    mock_response = MagicMock()
    mock_response.output = [
        create_mock_tool_call("get_subtree", {"node_id": node.id}),
        create_mock_tool_call("get_node_summary", {"node_id": node.id}),
        create_mock_tool_call("get_node_content", {"node_id": node.id}),
        create_mock_tool_call("finish", {"summary": "Attempted to read private node."})
    ]
    mock_client.responses.create.return_value = mock_response

    audit = task_runner.Audit(mock_task)
    task_row = {"instruction": "Read the private node.", "vault_id": vault.id, "context_node_ids": [node.id]}

    task_runner.run_agent(task_row, audit)

    # 3. Assertions

    # A: Verify `get_subtree` safely redacts the private summary and only shows title/id
    subtree_result = task_runner.get_subtree_summary(vault.id, node.id)
    assert subtree_result["ai_summary"] == "[private — content not accessible to agent]"
    assert subtree_result["id"] == node.id
    assert subtree_result["title"] == node.title

    # B: Verify `get_node_summary` tool execution was blocked
    summary_call = audit.turns[0]["tool_calls"][1]
    assert summary_call["name"] == "get_node_summary"
    assert summary_call["result"] == "blocked"
    assert "private (bxs-no-entry)" in summary_call["detail"]

    # C: Verify `get_node_content` tool execution was blocked
    content_call = audit.turns[0]["tool_calls"][2]
    assert content_call["name"] == "get_node_content"
    assert content_call["result"] == "blocked"
    assert "private (bxs-no-entry)" in content_call["detail"]


@patch("task_runner.OpenAI")
def test_agent_workflow_fully_private_node_write(mock_openai_class, setup_agent_env, db_session):
    """
    Tests that a fully private node (bxs-no-entry) behaves like a protected node
    during write operations: content changes are ignored, but AI summaries are allowed.
    """
    vault, agent, node, mock_task = setup_agent_env

    # 1. Ensure node has initial content and is marked fully private
    original_content = node.current_version_object.content
    node.icon = task_runner.READ_LOCK_ICON
    db_session.session.commit()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    # 2. Agent tries to aggressively overwrite and patch the content and summary
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

    audit = task_runner.Audit(mock_task)
    task_row = {"instruction": "Write and patch the private node.", "vault_id": vault.id, "context_node_ids": [node.id]}

    task_runner.run_agent(task_row, audit)

    db_session.session.expire_all()
    protected_node = db_session.session.get(Node, node.id)

    # 3. Assertions

    # A: The original content MUST remain completely untouched
    assert protected_node.current_version_object.content == original_content
    assert "MALICIOUS OVERWRITE" not in protected_node.current_version_object.content
    assert "HACK" not in protected_node.current_version_object.content

    # B: The AI Summary CAN be updated (should reflect the last action: patch_node)
    assert "Patch Sum 1" in protected_node.ai_summary
    assert "Patch Sum 2" in protected_node.ai_summary

    # C: Verify correct Audit Logging
    write_call = audit.turns[0]["tool_calls"][0]
    assert write_call["name"] == "write_node"
    assert write_call["result"] == "ok"
    assert "summary was updated" in write_call["detail"]

    patch_call = audit.turns[0]["tool_calls"][1]
    assert patch_call["name"] == "patch_node"
    assert patch_call["result"] == "ok"
    assert "summary was updated" in patch_call["detail"]

    # D: Verify the DB Audit writes are properly categorized
    operations = [w["operation"] for w in audit.writes]
    assert "write_node_summary_only" in operations
    assert "patch_node_summary_only" in operations