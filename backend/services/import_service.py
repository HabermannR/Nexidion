# backend/services/import_service.py
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from backend.models import db, Node, Vault, Version, User, DemoState
from backend.exceptions import DemoLockError
from backend.services.vault_service import invalidate_vault_list_cache
from backend.services.node_service import rebuild_vault_tree_cache


def import_vault(
        path: str | Path | dict,
        owner_id: int,
        vault_name_override: str | None = None,
) -> tuple[int, dict[str, str]]:
    """
    Imports a .nexidion vault snapshot.
    Returns (vault_id, uuid_remap) where uuid_remap maps
    original UUIDs to fresh UUIDs created for this import.
    """
    # Accept a raw dict or a filepath string to provide flexibility
    if isinstance(path, dict):
        data = path
    else:
        data = json.loads(Path(path).read_text(encoding='utf-8'))

    _validate_version(data)

    # Validate security rules
    user = db.session.get(User, owner_id)
    if not user:
        raise ValueError(f"User {owner_id} not found.")
    if user.is_guest and user.demo_state == DemoState.READ_ONLY:
        raise DemoLockError("Complete the demo task to unlock importing.")

    vault_name = vault_name_override or data['vault']['name']
    vault_name = vault_name.strip()

    # Prevent collision
    if db.session.execute(db.select(Vault).filter_by(name=vault_name, owner_id=owner_id)).first():
        raise ValueError(f"You already own a vault named '{vault_name}'.")

    # Bypassing standard vault_service.create_vault here.
    # Why? `create_vault` automatically generates a default 'Summary' root node.
    # The import will supply its own root node. Using the underlying ORM bypasses this issue cleanly.
    vault = Vault(name=vault_name, owner_id=owner_id)
    db.session.add(vault)
    db.session.flush()

    remap: dict[str, str] = {}

    # First pass: create nodes in BFS order (parents before children guaranteed)
    for node_data in data.get('nodes', []):
        new_id = _create_node_from_export(
            node_data=node_data,
            vault_id=vault.id,
            owner_id=owner_id,
            remap=remap,
        )
        remap[node_data['id']] = new_id

    # Second pass: rewrite internal [[uuid]] links throughout the vault
    _rewrite_internal_links(vault.id, remap)

    # Invalidate and rebuild caches
    invalidate_vault_list_cache(owner_id)
    rebuild_vault_tree_cache(vault.id)

    db.session.commit()
    return vault.id, remap


def _validate_version(data: dict[str, Any]):
    if data.get("nexidion_export_version") != 1:
        raise ValueError("Unsupported or missing export format version.")
    if "vault" not in data or "nodes" not in data:
        raise ValueError("Invalid export format: missing 'vault' or 'nodes'.")


def _create_node_from_export(
        node_data: dict[str, Any],
        vault_id: int,
        owner_id: int,
        remap: dict[str, str],
) -> str:
    # 1. Provide a fresh UUID for the local installation
    new_id = str(uuid.uuid4())

    # 2. Extract parent id, remap to the new UUID variant if it exists
    old_parent_id = node_data.get('parent_id')
    new_parent_id = remap.get(old_parent_id) if old_parent_id else None

    versions_data = node_data.get('versions', [])
    current_version_num = len(versions_data) if versions_data else 1

    node = Node(
        id=new_id,
        vault_id=vault_id,
        parent_id=new_parent_id,
        icon=node_data.get('icon'),
        current_version=current_version_num,
        # AI Summaries are generally generated contextually, left out here to regen
    )
    db.session.add(node)
    db.session.flush()

    if not versions_data:
        # Fallback to general object data if versions array is somehow missing
        version = Version(
            node_id=new_id,
            version=1,
            title=node_data.get('title', 'Imported Node'),
            content=node_data.get('content', ''),
            author_id=owner_id,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(version)
    else:
        for v_data in versions_data:
            # Parse imported timestamp, handling ISO Z format
            ts_str = v_data.get('created_at')
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            else:
                ts = datetime.now(timezone.utc)

            version = Version(
                node_id=new_id,
                version=v_data.get('version', 1),
                title=v_data.get('title', 'Imported Node'),
                content=v_data.get('content', ''),
                author_id=owner_id,  # Local mapping makes the importer the technical author
                timestamp=ts
            )
            db.session.add(version)

    return new_id


def _rewrite_internal_links(vault_id: int, remap: dict[str, str]):
    # Fetch all versions within the freshly imported vault
    versions = db.session.query(Version).join(Node).filter(Node.vault_id == vault_id).all()

    for version in versions:
        if not version.content:
            continue

        content = version.content
        changed = False

        # Bulk replace all old UUIDs with their freshly generated counterparts
        for old_uuid, new_uuid in remap.items():
            if old_uuid in content:
                content = content.replace(old_uuid, new_uuid)
                changed = True

        if changed:
            version.content = content