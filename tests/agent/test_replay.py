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
  7. Corrupted remap table fails with a clear logged error.
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from agent.replay import _run_replay


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_recording(steps: list) -> dict:
    return {"nexidion_recording_version": 1, "steps": steps}


def _make_task(status: str = "pending_demo", meta: dict | None = None) -> dict:
    return {
        "id":               "task-uuid-1234",
        "vault_id":         42,
        "instruction":      "Demo task",
        "context_node_ids": [],
        "created_at":       __import__("datetime").datetime(2025, 1, 1),
        "status":           status,
        "meta":             json.dumps(meta or {
            "uuid_remap":      {"demo-parent": "live-parent", "demo-child": "live-child"},
            "recording_path":  "/recordings/demo.json",
        }),
    }


# ---------------------------------------------------------------------------
# Unit tests for _remap_uuids
# ---------------------------------------------------------------------------

class TestRemapUuids:
    from agent.replay import _remap_uuids

    def test_simple_substitution(self):
        from agent.replay import _remap_uuids
        op     = {"type": "move_node", "node_id": "demo-child", "new_parent_id": "demo-parent"}
        remap  = {"demo-child": "live-child", "demo-parent": "live-parent"}
        result = _remap_uuids(op, remap)
        assert result == {"type": "move_node", "node_id": "live-child", "new_parent_id": "live-parent"}

    def test_unknown_uuids_passthrough(self):
        from agent.replay import _remap_uuids
        op    = {"type": "create_node", "parent_id": "not-in-remap", "title": "Test"}
        remap = {"demo-a": "live-a"}
        assert _remap_uuids(op, remap)["parent_id"] == "not-in-remap"

    def test_nested_dict_remapped(self):
        from agent.replay import _remap_uuids
        op    = {"type": "x", "inner": {"node_id": "demo-a"}}
        remap = {"demo-a": "live-a"}
        assert _remap_uuids(op, remap)["inner"]["node_id"] == "live-a"

    def test_non_string_values_untouched(self):
        from agent.replay import _remap_uuids
        op    = {"type": "create_node", "count": 3, "flag": True}
        remap = {"demo-a": "live-a"}
        result = _remap_uuids(op, remap)
        assert result["count"] == 3
        assert result["flag"] is True


# ---------------------------------------------------------------------------
# Integration-style tests for _run_replay
# ---------------------------------------------------------------------------

@pytest.fixture
def recording_file(tmp_path):
    """Write a minimal recording to a temp file and return its path."""
    recording = _make_recording([
        {
            "status_message": "Creating folder structure...",
            "delay_seconds":  0,          # zero delay for tests
            "operation": {
                "type":      "create_node",
                "title":     "Work",
                "parent_id": "demo-parent",
                "content":   "## Work",
                "ai_summary": "- Work node\n- Created by agent\n- Demo step",
            },
        },
        {
            "status_message": "Moving node...",
            "delay_seconds":  0,
            "operation": {
                "type":        "move_node",
                "node_id":     "demo-child",
                "new_parent_id": "demo-parent",
            },
        },
    ])
    p = tmp_path / "demo.json"
    p.write_text(json.dumps(recording), encoding="utf-8")
    return str(p)


def _build_replay_mocks(recording_path: str):
    """Return a dict of mock dependencies for _run_replay."""
    mock_vault       = MagicMock()
    mock_vault_owner = MagicMock()
    mock_vault.owner = mock_vault_owner

    mock_db       = MagicMock()
    mock_db.session.get.return_value = mock_vault

    mock_DemoState = MagicMock()
    mock_DemoState.UNLOCKED = "UNLOCKED"

    mock_Vault   = MagicMock()
    flask_app    = MagicMock()
    # Make flask_app.app_context() work as a context manager
    flask_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
    flask_app.app_context.return_value.__exit__  = MagicMock(return_value=False)

    status_calls: list = []
    log_calls:    list = []

    def update_status(task_id, status, log=None):
        status_calls.append((status, log))

    return {
        "flask_app":        flask_app,
        "db":               mock_db,
        "Vault":            mock_Vault,
        "DemoState":        mock_DemoState,
        "update_status_fn": update_status,
        "log_fn":           lambda msg: log_calls.append(msg),
        "mock_vault":       mock_vault,
        "_status_calls":    status_calls,
        "_log_calls":       log_calls,
    }


class TestRunReplay:
    """_run_replay integration tests (service layer mocked)."""

    def _run(self, task_row, recording_path, mocks):
        from agent.replay import _run_replay
        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "live-new"}}),
            patch("agent.replay.svc_move_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_summary",
                  return_value={"ok": True}),
        ):
            return asyncio.run(_run_replay(
                task_row         = task_row,
                vault_id         = task_row["vault_id"],
                agent_user_id    = 99,
                remap            = {"demo-parent": "live-parent", "demo-child": "live-child"},
                recording_path   = recording_path,
                flask_app        = mocks["flask_app"],
                db               = mocks["db"],
                Vault            = mocks["Vault"],
                DemoState        = mocks["DemoState"],
                update_status_fn = mocks["update_status_fn"],
                log_fn           = mocks["log_fn"],
            ))

    # 1. Replay completes; status stages appear in order
    def test_status_stages_in_order(self, recording_file):
        task   = _make_task()
        mocks  = _build_replay_mocks(recording_file)
        result = self._run(task, recording_file, mocks)

        statuses = [s for s, _ in mocks["_status_calls"]]
        # Each step emits "processing", final emit is "completed"
        assert statuses.count("processing") == 2
        assert statuses[-1] == "completed"
        assert "Replay complete" in result

    # 2. demo_state is UNLOCKED after completion
    def test_demo_state_unlocked(self, recording_file):
        task  = _make_task()
        mocks = _build_replay_mocks(recording_file)
        self._run(task, recording_file, mocks)

        assert mocks["mock_vault"].owner.demo_state == mocks["DemoState"].UNLOCKED
        mocks["db"].session.commit.assert_called()

    # 3. Node structure matches expected post-agent state
    def test_operations_dispatched_correctly(self, recording_file):
        from agent.replay import _run_replay
        task  = _make_task()
        mocks = _build_replay_mocks(recording_file)

        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "live-new"}}) as mock_create,
            patch("agent.replay.svc_move_node",
                  return_value={"ok": True}) as mock_move,
            patch("agent.replay.svc_update_node",
                  return_value={"ok": True}),
            patch("agent.replay.svc_update_summary",
                  return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={"demo-parent": "live-parent", "demo-child": "live-child"},
                recording_path=recording_file,
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        # create_node called with remapped parent_id
        mock_create.assert_called_once()
        create_kwargs = mock_create.call_args.kwargs
        assert create_kwargs["parent_id"] == "live-parent"
        assert create_kwargs["title"]     == "Work"

        # move_node called with both UUIDs remapped
        mock_move.assert_called_once()
        move_kwargs = mock_move.call_args.kwargs if mock_move.call_args.kwargs else {}
        move_args   = mock_move.call_args.args
        # svc_move_node(vault_id, node_id, new_parent_id, agent_user_id)
        assert "live-child"  in move_args
        assert "live-parent" in move_args

    # 4. Version history authored by agent user
    #    (Verified indirectly: svc_create_node / svc_update_node are called
    #    with the correct agent_user_id, which node_service uses for authorship.)
    def test_agent_user_id_passed_to_svc(self, recording_file):
        task  = _make_task()
        mocks = _build_replay_mocks(recording_file)

        with (
            patch("agent.replay.svc_create_node",
                  return_value={"ok": True, "node": {"id": "x"}}) as mock_create,
            patch("agent.replay.svc_move_node",  return_value={"ok": True}),
            patch("agent.replay.svc_update_node", return_value={"ok": True}),
            patch("agent.replay.svc_update_summary", return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=7,
                remap={"demo-parent": "live-parent", "demo-child": "live-child"},
                recording_path=recording_file,
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        assert mock_create.call_args.kwargs["agent_user_id"] == 7

    # 5. Rollback restores pre-agent content
    #    (node_service.update_node creates a version entry; the rollback API
    #    fetches the previous version. Tested here at the agent boundary:
    #    svc_update_node must be called so a version record is created.)
    def test_write_node_produces_version_via_svc(self, tmp_path):
        recording = _make_recording([{
            "status_message": "Writing node...",
            "delay_seconds":  0,
            "operation": {
                "type":      "write_node",
                "node_id":   "demo-node",
                "content":   "New content",
                "ai_summary": "- a\n- b\n- c",
            },
        }])
        p = tmp_path / "write_rec.json"
        p.write_text(json.dumps(recording))

        task  = _make_task()
        mocks = _build_replay_mocks(str(p))

        with (
            patch("agent.replay.svc_update_node",
                  return_value={"ok": True}) as mock_update,
            patch("agent.replay.svc_update_summary", return_value={"ok": True}),
        ):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={"demo-node": "live-node"},
                recording_path=str(p),
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

        # svc_update_node was called with the remapped node id
        mock_update.assert_called_once()
        args = mock_update.call_args.args
        assert "live-node" in args

    # 6. Real task (pending, not pending_demo) is not affected by replay path
    def test_real_task_not_handled_by_replay(self, recording_file):
        """_run_replay should never be called for a normal 'pending' task.
        Verified by checking loop._execute_task routing in loop.py — the
        replay branch is guarded by ``orig_status == 'pending_demo'``."""
        with patch("sqlalchemy.orm.Query.first") as mock_first:
            mock_user = MagicMock()
            mock_user.id = 99
            mock_first.return_value = mock_user
            from agent import loop

        task = _make_task(status="pending")

        dispatched_to_replay = False
        dispatched_to_agent  = False

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
            patch.object(loop, "run_agent",   side_effect=fake_agent),
            patch.object(loop, "mark_task_raw"),
            patch.object(loop, "flask_app") as mock_app,
        ):
            mock_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
            mock_app.app_context.return_value.__exit__  = MagicMock(return_value=False)
            loop._execute_task(task, conn)

        assert dispatched_to_agent  is True,  "Real task must reach run_agent"
        assert dispatched_to_replay is False, "Real task must NOT reach _run_replay"

    # 7. Corrupted remap table → clear error
    def test_missing_remap_raises(self, recording_file):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks(recording_file)

        with pytest.raises(RuntimeError, match="UUID remap failed"):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap=None, recording_path=recording_file,
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

    def test_nonexistent_recording_file_raises(self):
        from agent.replay import _run_replay
        task = _make_task()
        mocks = _build_replay_mocks("/nonexistent/path/recording.json")

        with pytest.raises(RuntimeError, match="recording not found"):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={"a": "b"}, recording_path="/nonexistent/path/recording.json",
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

    def test_invalid_recording_json_raises(self, tmp_path):
        from agent.replay import _run_replay
        task        = _make_task()
        p = tmp_path / "bad.json"
        p.write_text("not-valid-json{")
        mocks       = _build_replay_mocks(str(p))

        with pytest.raises(RuntimeError, match="not valid JSON"):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={}, recording_path=str(p),
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))

    def test_unknown_operation_type_raises(self, tmp_path):
        recording = _make_recording([{
            "status_message": "??",
            "delay_seconds":  0,
            "operation":      {"type": "explode_node", "node_id": "x"},
        }])
        p = tmp_path / "bad_op.json"
        p.write_text(json.dumps(recording))

        task  = _make_task()
        mocks = _build_replay_mocks(str(p))

        with pytest.raises(RuntimeError, match="unknown operation type"):
            asyncio.run(_run_replay(
                task_row=task, vault_id=42, agent_user_id=99,
                remap={}, recording_path=str(p),
                flask_app=mocks["flask_app"], db=mocks["db"],
                Vault=mocks["Vault"], DemoState=mocks["DemoState"],
                update_status_fn=mocks["update_status_fn"], log_fn=mocks["log_fn"],
            ))