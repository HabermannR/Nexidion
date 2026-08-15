"""Copy nodes between vaults without sharing ownership or connector bindings."""

import copy
import re
import uuid

from sqlalchemy.orm import joinedload

from backend.models import db, Node, User, Vault, Version
from backend.services.node_service import _assert_node_readable
from backend.services import node_policy_service
from backend.services.vault_service import assert_write_allowed, get_vault_access


MANAGED_ASSET_RE = re.compile(r"/api/vaults/\d+/assets/[0-9a-f-]{36}", re.IGNORECASE)
STRONG_LINK_RE = re.compile(
    r"(\[\[(?:[^\]|]*\|)?)([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})(\]\])",
    re.IGNORECASE,
)


def _rewrite_strong_links(content: str | None, remap: dict[str, str]) -> str | None:
    if not content:
        return content

    def replace(match: re.Match) -> str:
        target = match.group(2)
        replacement = remap.get(target.lower())
        return f"{match.group(1)}{replacement or target}{match.group(3)}"

    return STRONG_LINK_RE.sub(replace, content)


def copy_node_to_vault(
    source_node_id: str,
    source_vault_id: int,
    destination_vault_id: int,
    user_id: int,
    *,
    recursive: bool = True,
    destination_parent_id: str | None = None,
    actor_type: str | None = None,
) -> dict:
    """Create independent version-1 copies and return the old-to-new UUID map."""
    if source_vault_id == destination_vault_id:
        raise ValueError("Source and destination vaults must be different.")
    get_vault_access(source_vault_id, user_id)
    _, destination_role = get_vault_access(destination_vault_id, user_id)
    user = db.session.get(User, user_id)
    assert_write_allowed(destination_role, user)

    source = (
        Node.query.options(joinedload(Node.current_version_object))
        .filter_by(id=source_node_id, vault_id=source_vault_id)
        .first()
    )
    if not source:
        raise ValueError("Source node not found in the specified vault.")

    if destination_parent_id is not None:
        parent = db.session.get(Node, destination_parent_id)
        if not parent or parent.vault_id != destination_vault_id:
            raise ValueError("Destination parent not found in the destination vault.")
        node_policy_service.assert_writable(parent, user_id, actor_type=actor_type)

    nodes = []
    queue = [source]
    while queue:
        node = queue.pop(0)
        _assert_node_readable(node, user_id, actor_type=actor_type)
        nodes.append(node)
        if recursive:
            children = (
                Node.query.options(joinedload(Node.current_version_object))
                .filter_by(vault_id=source_vault_id, parent_id=node.id)
                .order_by(Node.id)
                .all()
            )
            queue.extend(children)

    for node in nodes:
        version = node.current_version_object
        if version and MANAGED_ASSET_RE.search(version.content or ""):
            raise ValueError(
                "Cross-vault copy does not support vault-scoped managed image references."
            )

    remap = {node.id.lower(): str(uuid.uuid4()) for node in nodes}
    created = []
    try:
        for node in nodes:
            version = node.current_version_object
            new_node = Node(
                id=remap[node.id.lower()],
                vault_id=destination_vault_id,
                parent_id=(destination_parent_id if node.id == source.id
                           else remap[node.parent_id.lower()]),
                current_version=1,
                icon=node.icon,
                ai_summary=node.ai_summary,
                summary_is_current=node.summary_is_current,
                content_kind=node.content_kind,
                authority=node.authority,
                language=node.language,
                tags=copy.deepcopy(node.tags or []),
                metadata_json=copy.deepcopy(node.metadata_json or {}),
                ai_read_policy=node.ai_read_policy,
                ai_write_locked=node.ai_write_locked,
                human_write_locked=node.human_write_locked,
                policy_note=node.policy_note,
            )
            if (destination_parent_id is not None and
                    node_policy_service.effective_policy(parent).ai_read == "explicit_only"):
                if new_node.ai_read_policy != "deny":
                    new_node.ai_read_policy = "explicit_only"
                new_node.ai_write_locked = True
            db.session.add(new_node)
            db.session.add(Version(
                node_id=new_node.id,
                version=1,
                title=version.title if version else "Untitled",
                content=_rewrite_strong_links(version.content if version else "", remap),
                author_id=user_id,
            ))
            created.append(new_node)

        destination = db.session.get(Vault, destination_vault_id)
        destination.cached_ui_tree = None
        destination.cached_ui_tree_etag = None
        destination.cached_agent_tree = None
        destination.cached_agent_tree_etag = None
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "source_node_id": source.id,
        "destination_vault_id": destination_vault_id,
        "destination_parent_id": destination_parent_id,
        "root_node_id": remap[source.id.lower()],
        "recursive": recursive,
        "copied_count": len(created),
        "uuid_map": {node.id: remap[node.id.lower()] for node in nodes},
        "managed_images": "rejected_if_present",
        "connector_bindings_copied": False,
    }
