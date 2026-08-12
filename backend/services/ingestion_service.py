from __future__ import annotations

from datetime import datetime, timezone

from backend.ingestion import ConnectorContext, connector_registry
from backend.models import db, User, ConnectorInstallation, IngestionRun, SourceItem, Node
from backend.services import node_service
from backend.services.vault_service import get_vault_access, assert_write_allowed

VALID_MODES = {"read", "ingest", "both"}
VALID_POLICIES = {"snapshot", "managed", "forkable", "editable_copy"}


def serialize_run(run: IngestionRun) -> dict:
    return {
        "id": run.id, "connector_id": run.connector_id, "status": run.status,
        "stats": run.stats or {}, "error": run.error,
        "requested_by_id": run.requested_by_id, "executed_by_id": run.executed_by_id,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def serialize_item(item: SourceItem) -> dict:
    return {
        "id": item.id, "connector_id": item.connector_id, "external_id": item.external_id,
        "node_id": item.node_id, "source_uri": item.source_uri,
        "source_version": item.source_version, "content_hash": item.content_hash,
        "policy": item.policy, "metadata": item.metadata_json or {},
        "mime_type": item.mime_type, "sync_status": item.sync_status,
        "imported_at": item.imported_at.isoformat(),
        "last_seen_at": item.last_seen_at.isoformat(),
        "external_modified_at": item.external_modified_at.isoformat() if item.external_modified_at else None,
    }


def run_connector(connector_id: str, requested_by_id: int, executed_by_id: int | None = None,
                  config_override: dict | None = None) -> IngestionRun:
    installation = db.session.get(ConnectorInstallation, connector_id)
    if not installation or not installation.enabled:
        raise ValueError("Connector is missing or disabled.")
    vault, role = get_vault_access(installation.vault_id, requested_by_id)
    assert_write_allowed(role, db.session.get(User, requested_by_id))
    connector = connector_registry.get(installation.plugin_name)
    if "ingest" not in connector.capabilities or installation.mode == "read":
        raise PermissionError("This connector installation is not allowed to ingest.")

    actor_id = executed_by_id or requested_by_id
    run = IngestionRun(connector_id=connector_id, requested_by_id=requested_by_id,
                       executed_by_id=actor_id, status="processing")
    db.session.add(run)
    db.session.commit()
    created = updated = unchanged = 0
    try:
        config = {**(installation.config or {}), **(config_override or {})}
        policy = config.get("policy", "managed")
        if policy not in VALID_POLICIES:
            raise ValueError(f"Unknown ingestion policy: {policy}")
        context = ConnectorContext(config=config)
        item_results = []
        for document in connector.discover(context):
            binding = SourceItem.query.filter_by(connector_id=connector_id, external_id=document.external_id).first()
            desired_parent_id = config.get("parent_id")
            if document.parent_external_id:
                parent_binding = SourceItem.query.filter_by(
                    connector_id=connector_id, external_id=document.parent_external_id).first()
                if not parent_binding or not parent_binding.node_id:
                    raise ValueError(f"Parent source document was not ingested first: {document.parent_external_id}")
                desired_parent_id = parent_binding.node_id
            if binding and binding.node_id and binding.content_hash == document.content_hash:
                node = db.session.get(Node, binding.node_id)
                if node.parent_id != desired_parent_id:
                    node.parent_id = desired_parent_id
                unchanged += 1
                binding.last_seen_at = datetime.now(timezone.utc)
                binding.sync_status = "current"
                item_results.append({"external_id": document.external_id, "node_id": binding.node_id,
                                     "status": "unchanged", "content_hash": document.content_hash})
                continue
            if binding and binding.node_id:
                node_service.update_node(binding.node_id, vault.id, actor_id,
                                         title=document.title, content=document.markdown,
                                         allow_managed_source=True)
                node = db.session.get(Node, binding.node_id)
                node.parent_id = desired_parent_id
                updated += 1
                result_status = "updated"
            else:
                node = node_service.create_node(document.title, document.markdown,
                                                desired_parent_id, vault.id, actor_id)
                if binding:
                    binding.node_id = node.id
                else:
                    binding = SourceItem(connector_id=connector_id, external_id=document.external_id,
                                         node_id=node.id, content_hash=document.content_hash)
                    db.session.add(binding)
                created += 1
                result_status = "created"
            node.content_kind = ("source_container" if document.metadata.get("source_container")
                                 else "canonical_source")
            node.authority = document.authority
            node.language = document.language
            node.metadata_json = document.metadata
            binding.source_uri = document.source_uri
            binding.source_version = document.source_version
            binding.content_hash = document.content_hash
            binding.policy = policy
            binding.metadata_json = document.metadata
            binding.mime_type = document.mime_type
            binding.external_modified_at = document.external_modified_at
            binding.last_seen_at = datetime.now(timezone.utc)
            binding.sync_status = "current"
            binding.imported_at = datetime.now(timezone.utc)
            item_results.append({"external_id": document.external_id, "node_id": binding.node_id,
                                 "status": result_status, "content_hash": document.content_hash})
        run.status = "completed"
        run.stats = {"created": created, "updated": updated, "unchanged": unchanged,
                     "total": created + updated + unchanged, "items": item_results}
        run.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return run
    except Exception as exc:
        db.session.rollback()
        run = db.session.get(IngestionRun, run.id)
        run.status, run.error, run.completed_at = "failed", str(exc), datetime.now(timezone.utc)
        db.session.commit()
        raise
