"""
agent/replay.py
========================
Demo replay engine.

_run_replay() reads the hardcoded script from agent.demo_script, remaps
demo UUIDs to the live vault's UUIDs, replays every operation through
the real node_service layer, and unlocks the vault's demo state on completion.
"""

import asyncio
import time

from agent.svc import (
    svc_create_node,
    svc_move_node,
    svc_update_node,
    svc_update_summary,
    svc_delete_node
)

# Import the script you extracted from the UI!
from agent.demo_script import DEMO_OPERATIONS, DEMO_FINISH_SUMMARY

# ---------------------------------------------------------------------------
# UUID remapping
# ---------------------------------------------------------------------------

def _remap_uuids(operation: dict, remap: dict) -> dict:
    """Recursively remaps exact UUID fields AND partial matches inside content text."""
    result = {}
    for k, v in operation.items():
        if isinstance(v, str):
            if v in remap:
                # Exact match (e.g., "node_id", "parent_id")
                result[k] = remap[v]
            else:
                # Partial match (e.g., [[uuid]] links embedded in "content")
                new_str = v
                for old_u, new_u in remap.items():
                    if old_u in new_str:
                        new_str = new_str.replace(old_u, new_u)
                result[k] = new_str
        elif isinstance(v, dict):
            result[k] = _remap_uuids(v, remap)
        elif isinstance(v, list):
            # For lists, we just recursively map items if they are dicts/strings
            result[k] = [
                _remap_uuids(item, remap) if isinstance(item, dict) else
                (remap.get(item, item) if isinstance(item, str) else item)
                for item in v
            ]
        else:
            result[k] = v
    return result

# ---------------------------------------------------------------------------
# Operation dispatcher
# ---------------------------------------------------------------------------

def _apply_operation(op: dict, vault_id: int, agent_user_id: int, log_fn) -> str | None:
    """Apply one operation from the DB format. Returns new UUID for create_node."""
    op_type = op.get("operation")
    node_id = op.get("node_id")
    detail = op.get("detail", {})

    if op_type == "create_node":
        res = svc_create_node(
            vault_id      = vault_id,
            title         = detail.get("title", "Untitled"),
            parent_id     = detail.get("parent_id"),
            agent_user_id = agent_user_id,
            content       = detail.get("content", ""),
            ai_summary    = detail.get("ai_summary", ""),
        )
        if not res["ok"]:
            raise RuntimeError(f"replay create_node failed: {res['error']}")
        new_id = res["node"]["id"]
        log_fn(f"  [replay] create_node '{detail.get('title')}' → {new_id}")
        return new_id

    elif op_type in ("write_node", "patch_node", "rename_node"):
        # The DB log treats these very similarly; we just apply whatever is in 'detail'
        res = svc_update_node(
            vault_id, node_id, agent_user_id,
            title=detail.get("title"),
            content=detail.get("content")
        )
        if not res["ok"]:
            raise RuntimeError(f"replay {op_type} failed: {res['error']}")

        if detail.get("ai_summary"):
            svc_update_summary(vault_id, node_id, agent_user_id, detail["ai_summary"])
        log_fn(f"  [replay] {op_type} {node_id}")

    elif op_type == "move_node":
        res = svc_move_node(vault_id, node_id, detail.get("new_parent_id"), agent_user_id)
        if not res["ok"]:
            raise RuntimeError(f"replay move_node failed: {res['error']}")
        log_fn(f"  [replay] move_node {node_id} → {detail.get('new_parent_id')}")


    elif op_type == "delete_node":

        res = svc_delete_node(vault_id, node_id, agent_user_id)

        if not res["ok"]:
            raise RuntimeError(f"replay delete_node failed: {res['error']}")

        log_fn(f"  [replay] delete_node {node_id}")

    else:
        log_fn(f"  [replay] unknown op type '{op_type}', skipping.")

    return None

# ---------------------------------------------------------------------------
# Main replay coroutine
# ---------------------------------------------------------------------------

async def _run_replay(
    task_row:         dict,
    vault_id:         int,
    agent_user_id:    int,
    remap:            dict,
    recording_path:   str, # Ignored now, we use demo_script.py!
    flask_app,
    db,
    Vault,
    DemoState,
    update_status_fn,
    log_fn,
) -> str:
    """Execute the hardcoded demo script imported from agent.demo_script."""

    steps = DEMO_OPERATIONS
    log_fn(f"Replay: {len(steps)} step(s) from demo_script.py")

    for i, raw_op in enumerate(steps, 1):
        op_type = raw_op.get("operation")

        # 1. Generate a realistic-looking status message
        if op_type == "create_node":
            status_msg = f"Creating node: {raw_op.get('detail', {}).get('title', 'Untitled')}"
        elif op_type == "write_node":
            status_msg = "Writing content..."
        elif op_type == "patch_node":
            status_msg = "Refining node..."
        elif op_type == "move_node":
            status_msg = "Organizing vault structure..."
        else:
            status_msg = f"Processing ({op_type})..."

        update_status_fn(task_row["id"], "processing", log=status_msg)
        log_fn(f"  [replay {i}/{len(steps)}] {status_msg}")

        # 2. Fake the LLM "thinking/typing" delay (1.5 seconds per step)
        await asyncio.sleep(1.5)

        # 3. Remap all UUIDs using our live dictionary
        try:
            op = _remap_uuids(raw_op, remap)
        except Exception as exc:
            raise RuntimeError(f"replay: UUID remap failed on step {i}: {exc}") from exc

        # 4. Execute the actual action against the DB
        with flask_app.app_context():
            new_uuid = _apply_operation(op, vault_id, agent_user_id, log_fn)

        # 5. If we created a node, store the mapping so future steps can find it!
        if op_type == "create_node" and new_uuid:
            original_uuid = raw_op.get("node_id")
            if original_uuid:
                remap[original_uuid] = new_uuid

    # Unlock the vault's demo state
    with flask_app.app_context():
        vault = db.session.get(Vault, vault_id)
        if vault is None:
            raise RuntimeError(f"replay: vault {vault_id} not found when unlocking demo state.")
        vault.owner.demo_state = DemoState.UNLOCKED
        db.session.commit()
        log_fn(f"Demo state → UNLOCKED for vault {vault_id}")

    # Set the final output!
    update_status_fn(task_row["id"], "completed", log=DEMO_FINISH_SUMMARY)
    return "Replay complete. Vault is now unlocked."