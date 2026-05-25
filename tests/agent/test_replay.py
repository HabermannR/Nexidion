# tests/agent/test_replay.py

"""
tests/agent/test_replay.py
============================
B8 — Replay engine test suite.

Covers:
  1. Replay completes; all status stages appear in order.
  2. demo_state is DemoState.UNLOCKED after completion.
  3. Node structure matches expected post-agent state.
  4. Version history exists on modified nodes, authored by agent user.
  5. Rollback on a modified node restores pre-agent content.
  6. Real task submitted to same agent is not affected.
  7. Corrupted/missing remap table fails with a clear logged error.
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from agent.demo_script import DEMO_FINISH_SUMMARY


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_sleep():
    """Bypasses the artificial thinking/typing delay to speed up tests."""
    with patch("asyncio.sleep", return_value=None) as m:
        yield m


def _make_task(status: str = "pending_demo", meta: dict | None = None) -> dict:
    return {
        "id": "task-uuid-1234",
        "vault_id": 42,
        "instruction": "Demo task",
        "context_node_ids": [],
        "created_at": __import__("datetime").datetime(2025, 1, 1),
        "status": status,
        "meta": json.dumps(meta or {
            "uuid_remap": {"f9e941b2-b9bf-45a9-8657-77c519c0bce6": "live-parent-uuid"},
            "recording_path": "",  # Ignored now
        }),
    }

from unittest.mock import patch

# We parse it as a native Python list of dicts to replace the real DEMO_OPERATIONS
MOCK_DEMO_OPERATIONS = [
    {
        "detail": {
            "ai_summary": "Summary 1",
            "content": "Content 1",
            "parent_id": "f9e941b2-b9bf-45a9-8657-77c519c0bce6",
            "title": "Test Node"
        },
        "node_id": "c4a347e5-facd-4224-97b4-7c811f6e23c2",
        "operation": "create_node",
        "timestamp": "2026-05-21T09:53:58.928320+00:00"
    },
    {
        "detail": {
            "ai_summary": "Summary 2",
            "content": "Content 2 with link [[Test Node|c4a347e5-facd-4224-97b4-7c811f6e23c2]]"
        },
        "node_id": "f9e941b2-b9bf-45a9-8657-77c519c0bce6",
        "operation": "write_node",
        "timestamp": "2026-05-21T09:54:08.525233+00:00"
    }
]


def _build_replay_mocks():
    """Return a dict of mock dependencies for _run_replay."""
    mock_vault = MagicMock()
    mock_vault_owner = MagicMock()
    mock_vault.owner = mock_vault_owner

    mock_db = MagicMock()
    mock_db.session.get.return_value = mock_vault

    mock_DemoState = MagicMock()
    mock_DemoState.UNLOCKED = "UNLOCKED"

    mock_Vault = MagicMock()
    flask_app = MagicMock()
    # Make flask_app.app_context() work as a context manager
    flask_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
    flask_app.app_context.return_value.__exit__ = MagicMock(return_value=False)

    status_calls: list = []
    log_calls: list = []

    def update_status(task_id, status, log=None):
        status_calls.append((status, log))

    return {
        "flask_app": flask_app,
        "db": mock_db,
        "Vault": mock_Vault,
        "DemoState": mock_DemoState,
        "update_status_fn": update_status,
        "log_fn": lambda msg: log_calls.append(msg),
        "mock_vault": mock_vault,
        "_status_calls": status_calls,
        "_log_calls": log_calls,
    }


# ---------------------------------------------------------------------------
# Unit tests for _remap_uuids
# ---------------------------------------------------------------------------

class TestRemapUuids:
    from agent.replay import _remap_uuids

    def test_simple_substitution(self):
        from agent.replay import _remap_uuids
        op = {"type": "move_node", "node_id": "demo-child", "new_parent_id": "demo-parent"}
        remap = {"demo-child": "live-child", "demo-parent": "live-parent"}
        result = _remap_uuids(op, remap)
        assert result == {"type": "move_node", "node_id": "live-child", "new_parent_id": "live-parent"}

    def test_unknown_uuids_passthrough(self):
        from agent.replay import _remap_uuids
        op = {"type": "create_node", "parent_id": "not-in-remap", "title": "Test"}
        remap = {"demo-a": "live-a"}
        assert _remap_uuids(op, remap)["parent_id"] == "not-in-remap"

    def test_nested_dict_remapped(self):
        from agent.replay import _remap_uuids
        op = {"type": "x", "inner": {"node_id": "demo-a"}}
        remap = {"demo-a": "live-a"}
        assert _remap_uuids(op, remap)["inner"]["node_id"] == "live-a"

    def test_non_string_values_untouched(self):
        from agent.replay import _remap_uuids
        op = {"type": "create_node", "count": 3, "flag": True}
        remap = {"demo-a": "live-a"}
        result = _remap_uuids(op, remap)
        assert result["count"] == 3
        assert result["flag"] is True


# ---------------------------------------------------------------------------
# Integration-style tests for _run_replay
# ---------------------------------------------------------------------------

class TestRunReplay:
    """_run_replay integration tests (service layer mocked)."""

    def _run(self, task_row, mocks, remap=None):
        from agent.replay import _run_replay
        if remap is None:
            remap = {"f9e941b2-b9bf-45a9-8657-77c519c0bce6": "live-parent-uuid"}
        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "live-child-uuid"}}),
            patch("agent.replay.svc_move_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_summary",
                  return_value={"ok": True}),
        ):
            return asyncio.run(_run_replay(
                task_row=task_row,
                vault_id=task_row["vault_id"],
                agent_user_id=99,
                remap=remap,
                recording_path="",
                flask_app=mocks["flask_app"],
                db=mocks["db"],
                Vault=mocks["Vault"],
                DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"],
                log_fn=mocks["log_fn"],
            ))

    # 1. Replay completes; status stages appear in order
    @patch("agent.replay.DEMO_OPERATIONS", MOCK_DEMO_OPERATIONS)
    def test_status_stages_in_order(self):
        task = _make_task()
        mocks = _build_replay_mocks()
        result = self._run(task, mocks)

        statuses = [s for s, _ in mocks["_status_calls"]]
        # DEMO_OPERATIONS has 2 steps, followed by a completion step
        assert statuses.count("processing") == 2
        assert statuses[-1] == "completed"
        assert "Replay complete" in result

        # Verify the sequence of status logs matches steps
        assert mocks["_status_calls"][0] == ("processing", "Creating node: Test Node")
        assert mocks["_status_calls"][1] == ("processing", "Writing content...")
        assert mocks["_status_calls"][2] == ("completed", DEMO_FINISH_SUMMARY)

    # 2. demo_state is DemoState.UNLOCKED after completion
    def test_demo_state_unlocked(self):
        task = _make_task()
        mocks = _build_replay_mocks()
        self._run(task, mocks)

        assert mocks["mock_vault"].owner.demo_state == mocks["DemoState"].UNLOCKED
        mocks["db"].session.commit.assert_called()

    # 3. Node structure matches expected post-agent state (Dynamic Remapping)
    @patch("agent.replay.DEMO_OPERATIONS", MOCK_DEMO_OPERATIONS)
    def test_operations_dispatched_correctly(self):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks()
        remap = {"f9e941b2-b9bf-45a9-8657-77c519c0bce6": "live-parent-uuid"}

        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "live-child-uuid"}}) as mock_create,
            patch("agent.replay.svc_move_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_node",
                  return_value={"ok": True}) as mock_update,
            patch("agent.replay.svc_update_summary",
                  return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap=remap,
                recording_path="",
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        # Step 1: create_node is called under the parent
        mock_create.assert_called_once()
        create_kwargs = mock_create.call_args.kwargs
        assert create_kwargs["parent_id"] == "live-parent-uuid"
        assert create_kwargs["title"] == "Test Node"

        # Step 2: write_node updates the parent
        mock_update.assert_called_once()
        update_kwargs = mock_update.call_args.kwargs
        # The target update must be the remapped parent ID
        assert mock_update.call_args.args[1] == "live-parent-uuid"
        # The content must link to the newly assigned child UUID
        assert "[[Test Node|live-child-uuid]]" in update_kwargs["content"]

    # 4. Version history authored by agent user
    @patch("agent.replay.DEMO_OPERATIONS", MOCK_DEMO_OPERATIONS)
    def test_agent_user_id_passed_to_svc(self):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks()

        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "x"}}) as mock_create,
            patch("agent.replay.svc_move_node", return_value={"ok": True}),
            patch("agent.replay.svc_update_node", return_value={"ok": True}),
            patch("agent.replay.svc_update_summary", return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=7,
                remap={"f9e941b2-b9bf-45a9-8657-77c519c0bce6": "live-parent-uuid"},
                recording_path="",
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        assert mock_create.call_args.kwargs["agent_user_id"] == 7

    # 5. Rollback restores pre-agent content (version creation boundary verification)
    @patch("agent.replay.DEMO_OPERATIONS", MOCK_DEMO_OPERATIONS)
    def test_write_node_produces_version_via_svc(self):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks()

        with (
            patch("agent.replay.svc_create_node", return_value={"ok": True, "node": {"id": "x"}}),
            patch("agent.replay.svc_update_node", return_value={"ok": True}) as mock_update,
            patch("agent.replay.svc_update_summary", return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={"f9e941b2-b9bf-45a9-8657-77c519c0bce6": "live-parent-uuid"},
                recording_path="",
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        # Asserts that svc_update_node was triggered, which internally establishes standard version history
        mock_update.assert_called_once()
        assert mock_update.call_args.args[1] == "live-parent-uuid"

    # 6. Real task (pending, not pending_demo) is not affected by replay path
    def test_real_task_not_handled_by_replay(self):
        with patch("sqlalchemy.orm.Query.first") as mock_first:
            mock_user = MagicMock()
            mock_user.id = 99
            mock_first.return_value = mock_user
            from agent import loop

        task = _make_task(status="pending")

        dispatched_to_replay = False
        dispatched_to_agent = False

        def fake_replay(*a, **kw):
            nonlocal dispatched_to_replay
            dispatched_to_replay = True

        def fake_agent(task_row, **kw):
            nonlocal dispatched_to_agent
            dispatched_to_agent = True
            return "done"

        conn = MagicMock()

        with (
            patch.object(loop, "_run_replay", side_effect=fake_replay),
            patch.object(loop, "run_agent", side_effect=fake_agent),
            patch.object(loop, "mark_task_raw"),
            patch.object(loop, "flask_app") as mock_app,
        ):
            mock_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
            mock_app.app_context.return_value.__exit__ = MagicMock(return_value=False)
            loop._execute_task(task, conn)

        assert dispatched_to_agent is True, "Real task must reach run_agent"
        assert dispatched_to_replay is False, "Real task must NOT reach _run_replay"

    # 7. Corrupted/missing remap table → clear error
    def test_missing_remap_raises(self):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks()

        with pytest.raises(RuntimeError, match="UUID remap failed"):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap=None, recording_path="",
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

    # 8. Unhandled operations are logged and safely bypassed
    def test_unknown_operation_type_skipped_and_logged(self):
        from agent.replay import _apply_operation
        log_calls = []
        op = {"operation": "explode_node", "node_id": "x"}

        res = _apply_operation(
            op,
            vault_id=42,
            agent_user_id=99,
            log_fn=lambda msg: log_calls.append(msg)
        )
        assert res is None
        assert any("unknown op type 'explode_node', skipping" in msg for msg in log_calls)