"""
backend/runner/helpers.py
=========================
Pure helper functions used by both the agent loop and the replay engine.
No Flask, no OpenAI — just logic.
"""

import json
import time
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------

def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Agent message-list helpers
# ---------------------------------------------------------------------------

def _append(input_list: list, call_id: str, output: str):
    input_list.append({
        "type":    "function_call_output",
        "call_id": call_id,
        "output":  output,
    })


def _fmt(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) \
        if isinstance(data, (dict, list)) else str(data)


# ---------------------------------------------------------------------------
# Fetch-budget guard
# ---------------------------------------------------------------------------

def _check_budget(node_id: str, seen: set, count: int, max_fetches: int) -> str | None:
    if node_id in seen:
        return f"Already fetched {node_id} — use your prior context."
    if count >= max_fetches:
        return f"Fetch budget exhausted ({max_fetches} calls). Finish with what you have."
    return None


# ---------------------------------------------------------------------------
# AI-summary validator
# ---------------------------------------------------------------------------

def _validate_summary(ai_summary: str) -> str | None:
    if not ai_summary:
        return "ai_summary is empty."
    bullets = [ln for ln in ai_summary.splitlines() if ln.startswith("- ")]
    if len(bullets) != 3:
        return f"ai_summary has {len(bullets)} bullet(s); must be exactly 3 lines starting with '- '."
    return None


# ---------------------------------------------------------------------------
# Tree traversal
# ---------------------------------------------------------------------------

def get_children_from_tree(parent_id: str, tree: list) -> list:
    def find(nodes, pid):
        for node in nodes:
            if node["id"] == pid:
                return node.get("children", [])
            found = find(node.get("children", []), pid)
            if found is not None:
                return found
        return None
    return find(tree, parent_id) or []


def find_root_for_node(node_id: str, tree: list) -> dict | None:
    def find_path(nodes, target, path):
        for node in nodes:
            new_path = path + [node]
            if node["id"] == target:
                return new_path
            result = find_path(node.get("children", []), target, new_path)
            if result:
                return result
        return None
    path = find_path(tree, node_id, [])
    return path[0] if path else None


# ---------------------------------------------------------------------------
# Privacy / lock helpers
# These need the svc layer to resolve node icons; the svc module is passed
# in to avoid a circular import between helpers ↔ svc.
# ---------------------------------------------------------------------------

def is_read_locked(svc_get_node, read_lock_icon: str,
                   vault_id: int, node_id: str) -> bool:
    """Returns True for bxs-no-entry nodes — agent cannot read or write content."""
    node = svc_get_node(vault_id, node_id)
    return node.get("icon") == read_lock_icon if node else False


def is_blacklisted(svc_get_node, blacklist_icon: str, read_lock_icon: str,
                   vault_id: int, node_id: str) -> bool:
    """Returns True for bxs-lock-alt (write-lock) OR bxs-no-entry (full lock)."""
    node = svc_get_node(vault_id, node_id)
    if not node:
        return False
    return node.get("icon") in (blacklist_icon, read_lock_icon)


def _redact_if_private(read_lock_icon: str, node_summary: dict) -> dict:
    """Replace summary content with a privacy notice for bxs-no-entry nodes."""
    if node_summary and node_summary.get("icon") == read_lock_icon:
        return {
            "id":         node_summary["id"],
            "title":      node_summary["title"],
            "parent_id":  node_summary.get("parent_id"),
            "icon":       read_lock_icon,
            "ai_summary": "[private — content not accessible to agent]",
        }
    return node_summary


def get_subtree_summary(svc_get_node_summary, svc_get_tree,
                        read_lock_icon: str,
                        vault_id: int, node_id: str) -> dict:
    node = svc_get_node_summary(vault_id, node_id)
    if "error" in node:
        return node

    node = _redact_if_private(read_lock_icon, node)

    tree = svc_get_tree(vault_id)
    children_stubs = get_children_from_tree(node_id, tree)
    children = [
        _redact_if_private(read_lock_icon, svc_get_node_summary(vault_id, stub["id"]))
        for stub in children_stubs
    ]
    return {**node, "children": children}
