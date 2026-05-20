"""
agent/svc.py
=====================
Thin wrappers around node_service that fix vault_id + agent user ID on every
call.  All content reads and writes go through these functions so the agent
uses the exact same business-logic path as the Flask API.

The module-level cache (_agent_tree_etags / _cached_agent_trees) is
intentionally process-scoped: a single agent process handles one vault at a
time, and the cache is invalidated server-side via ETags.
"""

import time

from backend.services import node_service


# ---------------------------------------------------------------------------
# In-process ETag cache for the vault tree
# ---------------------------------------------------------------------------
_agent_tree_etags:   dict = {}
_cached_agent_trees: dict = {}


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def svc_get_tree(vault_id: int, agent_user_id: int, log_fn) -> list:
    global _agent_tree_etags, _cached_agent_trees

    client_etag = _agent_tree_etags.get(vault_id)

    tree_data, etag, is_not_modified = node_service.get_nodes_as_tree(
        vault_id=vault_id,
        user_id=agent_user_id,
        format_type='agent_tree',
        client_etag=client_etag,
    )

    if is_not_modified:
        log_fn(f"[Cache Hit] Using in-memory tree for vault {vault_id}")
        return _cached_agent_trees[vault_id]

    _agent_tree_etags[vault_id]   = etag
    _cached_agent_trees[vault_id] = tree_data
    return tree_data


def svc_get_node(vault_id: int, node_id: str, agent_user_id: int) -> dict | None:
    return node_service.get_node_by_id(node_id, vault_id, agent_user_id)


def svc_get_node_summary(vault_id: int, node_id: str, agent_user_id: int) -> dict | None:
    node = svc_get_node(vault_id, node_id, agent_user_id)
    if node is None:
        return {"error": f"Node {node_id} not found."}
    return {
        "id":         node.get("id"),
        "title":      node.get("title"),
        "parent_id":  node.get("parent_id"),
        "icon":       node.get("icon"),
        "ai_summary": node.get("ai_summary"),
    }


def svc_search(vault_id: int, query: str, agent_user_id: int, limit: int = 15) -> dict:
    results = node_service.search_nodes_fulltext(query, vault_id, agent_user_id, limit=limit)
    return {
        "count":   len(results),
        "results": [{"id": n.get("id"), "title": n.get("title"),
                     "ai_summary": n.get("ai_summary")} for n in results],
    }


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def svc_update_node(vault_id: int, node_id: str, agent_user_id: int,
                    content: str | None = None, title: str | None = None) -> dict:
    try:
        node_service.update_node(node_id, vault_id, agent_user_id,
                                 title=title, content=content)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_update_summary(vault_id: int, node_id: str, agent_user_id: int,
                       ai_summary: str) -> dict:
    try:
        node_service.update_node_ai_summary(node_id, vault_id, agent_user_id, ai_summary)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_move_node(vault_id: int, node_id: str, new_parent_id: str,
                  agent_user_id: int) -> dict:
    try:
        node_service.move_node(node_id, new_parent_id, vault_id, agent_user_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_create_node(vault_id: int, title: str, parent_id: str,
                    agent_user_id: int,
                    content: str = "", ai_summary: str = "") -> dict:
    try:
        new_node = node_service.create_node(
            title=title, content=content, parent_id=parent_id,
            vault_id=vault_id, author_id=agent_user_id,
        )
        if ai_summary:
            node_service.update_node_ai_summary(
                new_node.id, vault_id, agent_user_id, ai_summary
            )
        return {"ok": True, "node": {"id": new_node.id}}
    except Exception as e:
        return {"ok": False, "error": str(e)}
