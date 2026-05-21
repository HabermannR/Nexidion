"""
agent/replay.py
========================
Demo replay engine (B8).

_run_replay() reads a pre-recorded operation log, remaps demo UUIDs to the
live vault's UUIDs, replays every operation through the real node_service
layer (so version history is genuine and rollback works), and unlocks the
vault's demo state on completion.

Status messages and inter-step delays come from the recording, making the
replay indistinguishable from a live agent run.
"""

import asyncio
import json
import time
from pathlib import Path

from agent.svc import (
    svc_create_node,
    svc_move_node,
    svc_update_node,
    svc_update_summary,
)


# ---------------------------------------------------------------------------
# RecordingWriter
# Captures operations during a real agent run so they can be replayed later.
# ---------------------------------------------------------------------------

class RecordingWriter:
    def __init__(self):
        self.steps = []
        self._step_start: float | None = None
        self._pending_message: str = ""
        # Maps created node index (0-based, per create_node step) → live UUID
        # so the replay engine can build the remap table correctly.
        self.created_node_ids: list[str] = []

    def begin_step(self, status_message: str):
        self._step_start      = time.monotonic()
        self._pending_message = status_message

    def record_operation(self, op_type: str, **kwargs):
        delay = round(time.monotonic() - self._step_start, 2)
        self.steps.append({
            "status_message": self._pending_message,
            "delay_seconds":  delay,
            "operation":      {"type": op_type, **kwargs},
        })

    def register_created_node(self, live_uuid: str):
        """Call after a create_node succeeds to record the live UUID for replay remap."""
        self.created_node_ids.append(live_uuid)

    def to_dict(self) -> dict:
        return {
            "nexidion_recording_version": 1,
            "steps": self.steps,
            "created_node_ids": self.created_node_ids,
        }


# ---------------------------------------------------------------------------
# UUID remapping
# ---------------------------------------------------------------------------

def _remap_uuids(operation: dict, remap: dict) -> dict:
    """Return a copy of *operation* with every remap key replaced by its value."""
    result = {}
    for k, v in operation.items():
        if isinstance(v, str) and v in remap:
            result[k] = remap[v]
        elif isinstance(v, dict):
            result[k] = _remap_uuids(v, remap)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Operation dispatcher
# Mirrors the tool handlers in agent.py — same svc_* calls, same code path.
# ---------------------------------------------------------------------------

def _apply_operation(op: dict, vault_id: int, agent_user_id: int, log_fn) -> str | None:
    """Apply one operation. Returns the new node UUID for create_node, None otherwise."""
    op_type = op.get("type")

    if op_type == "create_node":
        res = svc_create_node(
            vault_id      = vault_id,
            title         = op["title"],
            parent_id     = op["parent_id"],
            agent_user_id = agent_user_id,
            content       = op.get("content", ""),
            ai_summary    = op.get("ai_summary", ""),
        )
        if not res["ok"]:
            raise RuntimeError(f"replay create_node failed: {res['error']}")
        new_id = res["node"]["id"]
        log_fn(f"  [replay] create_node '{op['title']}' → {new_id}")
        return new_id

    elif op_type == "write_node":
        res = svc_update_node(vault_id, op["node_id"], agent_user_id,
                              content=op.get("content"))
        if not res["ok"]:
            raise RuntimeError(f"replay write_node failed: {res['error']}")
        if op.get("ai_summary"):
            svc_update_summary(vault_id, op["node_id"], agent_user_id, op["ai_summary"])
        log_fn(f"  [replay] write_node {op['node_id']}")

    elif op_type == "move_node":
        res = svc_move_node(vault_id, op["node_id"], op["new_parent_id"], agent_user_id)
        if not res["ok"]:
            raise RuntimeError(f"replay move_node failed: {res['error']}")
        log_fn(f"  [replay] move_node {op['node_id']} → {op['new_parent_id']}")

    elif op_type == "rename_node":
        res = svc_update_node(vault_id, op["node_id"], agent_user_id,
                              title=op.get("title"))
        if not res["ok"]:
            raise RuntimeError(f"replay rename_node failed: {res['error']}")
        log_fn(f"  [replay] rename_node {op['node_id']} → '{op['title']}'")

    elif op_type == "patch_node":
        res = svc_update_node(vault_id, op["node_id"], agent_user_id,
                              content=op.get("content"))
        if not res["ok"]:
            raise RuntimeError(f"replay patch_node failed: {res['error']}")
        if op.get("ai_summary"):
            svc_update_summary(vault_id, op["node_id"], agent_user_id, op["ai_summary"])
        log_fn(f"  [replay] patch_node {op['node_id']}")

    else:
        raise RuntimeError(
            f"replay: unknown operation type '{op_type}' — "
            "recording may be corrupt or from a newer version."
        )
    return None


# ---------------------------------------------------------------------------
# Main replay coroutine
# ---------------------------------------------------------------------------

async def _run_replay(
    task_row:         dict,
    vault_id:         int,
    agent_user_id:    int,
    remap:            dict,
    recording_path:   str,
    flask_app,
    db,
    Vault,
    DemoState,
    update_status_fn,
    log_fn,
) -> str:
    """
    Execute a recorded demo task.

    Parameters
    ----------
    task_row         : dict from claim_oldest_task
    vault_id         : resolved vault ID
    agent_user_id    : AGENT_USER_ID constant
    remap            : UUID translation table — {recording_uuid: guest_vault_uuid}
                       fetched from vault.owner.demo_remap in loop.py
    recording_path   : path to the .nexidion recording file, from config
    flask_app        : the Flask application instance (for app context)
    db               : SQLAlchemy db object
    Vault            : Vault model class
    DemoState        : DemoState enum
    update_status_fn : callable(task_id, status, log=...) — wraps mark_task_raw
    log_fn           : callable(str) — the _log function from loop.py
    """
    try:
        recording = json.loads(Path(recording_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(f"replay: recording not found at '{recording_path}'.")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"replay: recording file is not valid JSON — {exc}") from exc

    steps = recording.get("steps", [])
    # created_node_ids: list of live UUIDs from the real agent run, in create_node order.
    # We use these to build a per-guest remap so every reference to a dynamically-created
    # node is translated to the guest vault's own newly-created UUID.
    recording_created_ids = recording.get("created_node_ids", [])
    create_node_counter = 0

    log_fn(f"Replay: {len(steps)} step(s) from '{recording_path}'")

    for i, step in enumerate(steps, 1):
        status_msg = step.get("status_message", f"Step {i}…")
        delay      = step.get("delay_seconds", 0)
        raw_op     = step.get("operation", {})

        update_status_fn(task_row["id"], "processing", log=status_msg)
        log_fn(f"  [replay {i}/{len(steps)}] {status_msg} (delay {delay}s)")

        await asyncio.sleep(delay)

        try:
            op = _remap_uuids(raw_op, remap)
        except Exception as exc:
            raise RuntimeError(
                f"replay: UUID remap failed on step {i} ({raw_op.get('type')}): {exc}"
            ) from exc

        with flask_app.app_context():
            new_uuid = _apply_operation(op, vault_id, agent_user_id, log_fn)

        # If this was a create_node, register the new UUID in the remap so
        # subsequent steps that reference this node (e.g. move_node into it)
        # are translated correctly. This fixes the "Tree rehydrate" bug where
        # nodes created mid-recording were not found on subsequent references.
        if new_uuid is not None and create_node_counter < len(recording_created_ids):
            original_uuid = recording_created_ids[create_node_counter]
            remap[original_uuid] = new_uuid
            create_node_counter += 1

    # Unlock the vault's demo state
    with flask_app.app_context():
        vault = db.session.get(Vault, vault_id)
        if vault is None:
            raise RuntimeError(f"replay: vault {vault_id} not found when unlocking demo state.")
        vault.owner.demo_state = DemoState.UNLOCKED
        db.session.commit()
        log_fn(f"Demo state → UNLOCKED for vault {vault_id}")

    update_status_fn(task_row["id"], "completed", log="Done. Vault is now unlocked.")
    return "Replay complete. Vault is now unlocked."