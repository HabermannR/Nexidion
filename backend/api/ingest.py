"""Compatibility route for clients using the original vault-scoped PDF URL."""
from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.api.connectors import ingest_pdf_upload
from backend.extensions import limiter
from backend.services.ingestion_service import serialize_run


ingest_bp = Blueprint('ingest', __name__, url_prefix='/api/vaults/<int:vault_id>/ingest')


@ingest_bp.route('/pdf', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("5 per minute; 20 per hour")
def api_ingest_pdf(vault_id: int):
    user_id = int(get_jwt_identity())
    try:
        run, installation, job, artifact = ingest_pdf_upload(vault_id, user_id)
        payload = serialize_run(run) if run else {"status": "accepted", "stats": {}}
        payload["connector_id"] = installation.id
        payload["artifact_id"] = artifact.id
        payload["curation_job_id"] = job.id if job else None
        return jsonify(payload), 202 if job else 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
