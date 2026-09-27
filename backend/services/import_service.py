# backend/services/import_service.py
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from backend.models import db, Node, Vault, Version, User
from backend.services.node_policy_service import AI_READ_VALUES
from backend.services.vault_service import invalidate_vault_list_cache, grant_default_agent_access
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
    if isinstance(path, (dict, list)):  # already-parsed JSON (validated below)
        data = path
    else:
        data = json.loads(Path(path).read_text(encoding='utf-8'))

    _validate_version(data)

    # Validate security rules
    user = db.session.get(User, owner_id)
    if not user:
        raise ValueError(f"User {owner_id} not found.")

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
    grant_default_agent_access(vault.id)
    invalidate_vault_list_cache(owner_id)
    rebuild_vault_tree_cache(vault.id)

    db.session.commit()
    return vault.id, remap


def _validate_version(data: dict[str, Any]):
    if not isinstance(data, dict):
        raise ValueError("Invalid export format: expected a JSON object.")
    if data.get("nexidion_export_version") != 1:
        raise ValueError("Unsupported or missing export format version.")
    if "vault" not in data or "nodes" not in data:
        raise ValueError("Invalid export format: missing 'vault' or 'nodes'.")
    if not isinstance(data["vault"], dict) or not isinstance(data["vault"].get("name"), str):
        raise ValueError("Invalid export format: 'vault' must contain a name.")
    if not isinstance(data["nodes"], list) or not all(
            isinstance(node, dict) and isinstance(node.get("id"), str) for node in data["nodes"]):
        raise ValueError("Invalid export format: every node needs a string 'id'.")


# In backend/services/import_service.py

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
    # The current version is the highest number, not the count: histories can have gaps.
    current_version_num = max((v.get('version', 1) for v in versions_data), default=1)

    node = Node(
        id=new_id,
        vault_id=vault_id,
        parent_id=new_parent_id,
        icon=node_data.get('icon'),
        current_version=current_version_num,
        ai_summary=node_data.get('ai_summary'),                           # <-- ADDED
        summary_is_current=node_data.get('summary_is_current', False),    # <-- ADDED
    )
    _apply_exported_attributes(node, node_data)
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
                # Remove Z and attach actual timezone info for python 3.10 compat, or use fromisoformat if upgraded
                if ts_str.endswith('Z'):
                    ts_str = ts_str[:-1]

                    # Extract the time portion to safely check for an existing timezone offset
                    time_part = ts_str
                    if 'T' in ts_str:
                        time_part = ts_str.split('T')[-1]
                    elif ' ' in ts_str:
                        time_part = ts_str.split(' ')[-1]

                    # Only append +00:00 if an offset is not already present
                    if '+' not in time_part and '-' not in time_part:
                        ts_str += '+00:00'
                ts = datetime.fromisoformat(ts_str)
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


def _apply_exported_attributes(node: Node, node_data: dict[str, Any]) -> None:
    """Restore access policy and provenance. Older exports lack these keys and keep
    the model defaults; an unknown ai_read value fails closed to 'deny'."""
    policy = node_data.get('access_policy') or {}
    if policy:
        ai_read = policy.get('ai_read', 'allow')
        node.ai_read_policy = ai_read if ai_read in AI_READ_VALUES else 'deny'
        node.human_write_locked = bool(policy.get('human_write_locked'))
        node.ai_write_locked = bool(policy.get('ai_write_locked') or node.human_write_locked
                                    or node.ai_read_policy != 'allow')
        note = policy.get('note')
        node.policy_note = note.strip() if isinstance(note, str) and note.strip() else None
    for key, attribute in (('content_kind', 'content_kind'), ('authority', 'authority'),
                           ('language', 'language')):
        if isinstance(node_data.get(key), str):
            setattr(node, attribute, node_data[key])
    if isinstance(node_data.get('tags'), list):
        node.tags = node_data['tags']
    if isinstance(node_data.get('metadata'), dict):
        node.metadata_json = node_data['metadata']


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
