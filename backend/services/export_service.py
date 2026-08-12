# backend/services/export_service.py
"""
Export service for Nexidion vaults.

Produces a self-contained .nexidion JSON file that can be imported on any
Nexidion instance. The format is versioned so future importers can detect
incompatible exports early.

Format contract (version 1):
  - Nodes are ordered breadth-first (parents before children).
  - Versions are ordered oldest-first within each node (ascending version number).
  - Internal [[uuid]] links in content are preserved verbatim — the importer
    remaps them after creating fresh UUIDs.
  - author_display_name on versions (not author_id) — IDs are meaningless
    across instances; display names survive the round-trip as attribution.
  - VaultAccess rows are NOT exported — sharing is instance-specific.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from typing import Any

from backend.models import db, Node, Vault, Version


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_vault(vault_id: int, user_id: int) -> str:
    """
    Serialise vault *vault_id* to a .nexidion JSON string.

    Only the vault owner may export.  A shared member with EDITOR access gets
    a PermissionError (caller maps this to HTTP 403).

    Returns the raw JSON string — caller sets Content-Disposition / Content-Type.

    Raises:
        ValueError:      vault not found.
        PermissionError: caller is not the vault owner.
    """
    vault = db.session.get(Vault, vault_id)
    if vault is None:
        raise ValueError(f"Vault {vault_id} not found.")

    if vault.owner_id != user_id:
        # Shared members (even EDITORs) may not export — exporting is an
        # owner-only action because it includes the full version history.
        raise PermissionError("Only the vault owner may export this vault.")

    payload = _build_export(vault)
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_export(vault: Vault) -> dict[str, Any]:
    """Assemble the full export payload dict."""
    return {
        "nexidion_export_version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vault": {
            "name": vault.name,
        },
        "nodes": _export_nodes_bfs(vault.id),
    }


def _export_nodes_bfs(vault_id: int) -> list[dict[str, Any]]:
    """
    Walk the node tree breadth-first and return serialised nodes.

    BFS guarantees every parent appears before its children, so the importer
    can process the list top-to-bottom without a sorting pass.
    """
    # Load all nodes for this vault in one query, indexed by id for fast lookup.
    all_nodes: dict[str, Node] = {
        n.id: n
        for n in db.session.execute(
            db.select(Node).filter_by(vault_id=vault_id)
        ).scalars().all()
    }

    # Build a parent→children map (using None as the key for root nodes).
    children_of: dict[str | None, list[str]] = {}
    for node_id, node in all_nodes.items():
        children_of.setdefault(node.parent_id, []).append(node_id)

    # BFS from root nodes (parent_id is None).
    ordered: list[dict[str, Any]] = []
    queue: deque[str] = deque(children_of.get(None, []))

    while queue:
        node_id = queue.popleft()
        node = all_nodes[node_id]
        ordered.append(_serialise_node(node))
        for child_id in children_of.get(node_id, []):
            queue.append(child_id)

    return ordered


# In backend/services/export_service.py

def _serialise_node(node: Node) -> dict[str, Any]:
    """Convert a single Node (with all its versions) to a dict."""
    # Load versions ordered oldest-first so the importer can replay history
    # in the correct sequence.
    versions = db.session.execute(
        db.select(Version)
        .filter_by(node_id=node.id)
        .order_by(Version.version.asc())
    ).scalars().all()

    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "icon": node.icon,
        "ai_summary": node.ai_summary,                           # <-- ADDED
        "summary_is_current": node.summary_is_current,           # <-- ADDED
        # title and content come from the current version
        "title": versions[-1].title if versions else "",
        "content": versions[-1].content if versions else "",
        "created_at": versions[0].timestamp.isoformat() + "Z" if versions else None,
        "updated_at": versions[-1].timestamp.isoformat() + "Z" if versions else None,
        "versions": [_serialise_version(v) for v in versions],
    }

def _serialise_version(version: Version) -> dict[str, Any]:
    """Serialise a single version. Uses display_name instead of author_id."""
    author_name = (
        version.author.display_name if version.author else "Unknown"
    )
    return {
        "version": version.version,
        "title": version.title,
        "content": version.content,
        "created_at": version.timestamp.isoformat() + "Z",
        "author_display_name": author_name,
    }
