import os
import tempfile

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from backend.ingestion import connector_registry
from backend.models import (db, ConnectorInstallation, IngestionRun, SourceItem, User,
                            UserType, SourceArtifact, CurationJob, NodeSourceLink, Node)
from backend.ingestion.pdf import extract_pdf
from backend.services.curation_service import PROMPT_VERSION, serialize_curation_job
from backend.services.image_asset_service import create_asset
from backend.services.ingestion_service import (
    VALID_MODES, VALID_POLICIES, run_connector, serialize_run, serialize_item,
)
from backend.services.vault_service import get_vault_access, assert_write_allowed
from backend.services.node_policy_service import assert_readable, is_ai_actor

connectors_bp = Blueprint('connectors', __name__, url_prefix='/api/connectors')
MAX_PDF_BYTES = 100 * 1024 * 1024


def _installation_dict(row):
    return {"id": row.id, "vault_id": row.vault_id, "name": row.name,
            "plugin_name": row.plugin_name, "mode": row.mode, "enabled": row.enabled,
            "config": row.config, "credential_ref": row.credential_ref,
            "created_at": row.created_at.isoformat()}


def _require_vault_writer(vault_id, user_id):
    _, role = get_vault_access(vault_id, user_id)
    assert_write_allowed(role, db.session.get(User, user_id))


def _include_quarantined():
    return request.args.get('include_quarantined', 'false').lower() == 'true'


def ingest_pdf_upload(vault_id: int, user_id: int):
    """Run deterministic PDF ingestion for a multipart upload."""
    _require_vault_writer(vault_id, user_id)
    upload = request.files.get('file')
    if not upload or not upload.filename:
        raise ValueError("A PDF is required in multipart field 'file'.")
    filename = secure_filename(upload.filename)
    if not filename or not filename.lower().endswith('.pdf'):
        raise ValueError("The uploaded file must have a .pdf extension.")
    parent_id = request.form.get('parent_id') or None
    workflow = request.form.get('mode', 'extract')
    if workflow not in {'extract', 'extract_and_curate', 'curate_only'}:
        raise ValueError('mode must be extract, extract_and_curate, or curate_only')
    granularity = request.form.get('granularity', 'auto')
    if granularity not in {'auto', 'document', 'chapter', 'page'}:
        raise ValueError('granularity must be auto, document, chapter, or page')
    policy = request.form.get('policy', 'managed')
    if policy not in VALID_POLICIES:
        raise ValueError(f"policy must be one of: {', '.join(sorted(VALID_POLICIES))}")

    installation = ConnectorInstallation.query.filter_by(
        vault_id=vault_id, plugin_name='pdf', name='PDF uploads'
    ).first()
    if not installation:
        installation = ConnectorInstallation(
            vault_id=vault_id, plugin_name='pdf', name='PDF uploads', mode='ingest',
            config={"policy": "managed"}, created_by_id=user_id,
        )
        db.session.add(installation)
        db.session.commit()

    fd, path = tempfile.mkstemp(prefix='nexidion_pdf_', suffix='.pdf')
    try:
        size = 0
        with os.fdopen(fd, 'wb') as target:
            while chunk := upload.stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise ValueError("PDF exceeds the 100 MiB upload limit.")
                target.write(chunk)
        with open(path, 'rb') as probe:
            if probe.read(5) != b'%PDF-':
                raise ValueError("The uploaded file is not a valid PDF.")
        extraction = extract_pdf(path)
        artifact = SourceArtifact.query.filter_by(connector_id=installation.id,
            external_id=filename, content_hash=extraction.content_hash).first()
        if not artifact:
            previous_artifact_ids = db.session.execute(db.select(SourceArtifact.id).filter_by(
                connector_id=installation.id, external_id=filename)).scalars().all()
            if previous_artifact_ids:
                NodeSourceLink.query.filter(NodeSourceLink.artifact_id.in_(previous_artifact_ids)).update(
                    {"is_stale": True}, synchronize_session=False)
            artifact = SourceArtifact(connector_id=installation.id, external_id=filename,
                content_hash=extraction.content_hash, mime_type='application/pdf',
                source_uri=f"upload://{filename}", payload=extraction.payload,
                extracted_json={"pages": extraction.pages, "outline": extraction.outline},
                metadata_json=extraction.metadata)
            db.session.add(artifact)
            db.session.commit()

        image_urls_by_page = {}
        for image in extraction.images:
            try:
                asset = create_asset(vault_id, user_id, image['data'],
                    f"{os.path.splitext(filename)[0]}-page-{image['page']}-{image['xref']}.{image['extension']}",
                    source_artifact_id=artifact.id, page_number=image['page'])
                image_urls_by_page.setdefault(str(image['page']), []).append(
                    f'/api/vaults/{vault_id}/assets/{asset.id}')
            except ValueError:
                continue

        run = None
        if workflow != 'curate_only':
            run = run_connector(installation.id, user_id, config_override={
                "path": path, "external_id": filename, "title": os.path.splitext(filename)[0],
                "source_uri": f"upload://{filename}", "parent_id": parent_id, "policy": policy,
                "granularity": granularity,
                "image_urls_by_page": image_urls_by_page,
            })

        job = None
        if workflow != 'extract':
            provider = request.form.get('provider', 'local')
            visual_mode = request.form.get('visual_mode', 'off')
            if provider not in {'local', 'openai', 'openrouter'}:
                raise ValueError('provider must be local, openai, or openrouter')
            if visual_mode not in {'off', 'auto', 'all'}:
                raise ValueError('visual_mode must be off, auto, or all')
            executor = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
            if not executor:
                raise ValueError("No LLM assistant user is configured.")
            get_vault_access(vault_id, executor.id)
            curation_parent_id = parent_id
            if run:
                container_binding = SourceItem.query.filter_by(
                    connector_id=installation.id, external_id=f"{filename}#container").first()
                if container_binding and container_binding.node_id:
                    curation_parent_id = container_binding.node_id
            job = CurationJob(artifact_id=artifact.id, vault_id=vault_id, parent_id=curation_parent_id,
                mode=workflow, provider=provider, model=request.form.get('model') or None,
                visual_mode=visual_mode, prompt_version=PROMPT_VERSION,
                requested_by_id=user_id, executed_by_id=executor.id)
            db.session.add(job)
            db.session.commit()
        return run, installation, job, artifact
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


@connectors_bp.get('/plugins')
@jwt_required()
def plugins():
    return jsonify([{"name": name, "capabilities": sorted(connector_registry.get(name).capabilities)}
                    for name in connector_registry.names()])


@connectors_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
def installations():
    user_id = int(get_jwt_identity())
    vault_id = request.args.get('vault_id', type=int)
    if not vault_id:
        return jsonify({"error": "vault_id is required"}), 400
    get_vault_access(vault_id, user_id)
    rows = ConnectorInstallation.query.filter_by(vault_id=vault_id).order_by(ConnectorInstallation.name).all()
    return jsonify([_installation_dict(row) for row in rows])


@connectors_bp.route('', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_installation():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    try:
        vault_id = int(data['vault_id'])
        plugin_name, name = data['plugin_name'].strip(), data['name'].strip()
        mode = data.get('mode', 'ingest')
        if mode not in VALID_MODES:
            raise ValueError("mode must be read, ingest, or both")
        connector_registry.get(plugin_name)
        _, role = get_vault_access(vault_id, user_id)
        assert_write_allowed(role, db.session.get(User, user_id))
        row = ConnectorInstallation(vault_id=vault_id, plugin_name=plugin_name, name=name,
                                    mode=mode, config=data.get('config') or {},
                                    credential_ref=data.get('credential_ref'), created_by_id=user_id)
        db.session.add(row)
        db.session.commit()
        return jsonify(_installation_dict(row)), 201
    except KeyError as exc:
        return jsonify({"error": f"missing field: {exc.args[0]}"}), 400
    except (ValueError, PermissionError) as exc:
        return jsonify({"error": str(exc)}), 400 if isinstance(exc, ValueError) else 403


@connectors_bp.post('/<string:connector_id>/run')
@jwt_required()
def run_installation(connector_id):
    user_id = int(get_jwt_identity())
    try:
        run = run_connector(connector_id, user_id)
        return jsonify(serialize_run(run))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403


@connectors_bp.post('/pdf/ingest')
@jwt_required()
def upload_pdf():
    user_id = int(get_jwt_identity())
    try:
        vault_id = request.form.get('vault_id', type=int)
        if not vault_id:
            raise ValueError("vault_id is required.")
        run, installation, job, artifact = ingest_pdf_upload(vault_id, user_id)
        payload = serialize_run(run) if run else {"status": "accepted", "stats": {}}
        payload["connector"] = _installation_dict(installation)
        payload["artifact_id"] = artifact.id
        payload["curation_job"] = serialize_curation_job(job) if job else None
        return jsonify(payload), 202 if job else 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403


@connectors_bp.get('/<string:connector_id>/runs')
@jwt_required()
def list_runs(connector_id):
    user_id = int(get_jwt_identity())
    installation = db.session.get(ConnectorInstallation, connector_id)
    if not installation:
        return jsonify({"error": "Connector not found."}), 404
    try:
        get_vault_access(installation.vault_id, user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    rows = IngestionRun.query.filter_by(connector_id=connector_id).order_by(IngestionRun.created_at.desc()).all()
    return jsonify([serialize_run(row) for row in rows])


@connectors_bp.get('/runs/<string:run_id>')
@jwt_required()
def get_run(run_id):
    user_id = int(get_jwt_identity())
    run = db.session.get(IngestionRun, run_id)
    if not run:
        return jsonify({"error": "Ingestion run not found."}), 404
    installation = db.session.get(ConnectorInstallation, run.connector_id)
    try:
        get_vault_access(installation.vault_id, user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    return jsonify(serialize_run(run))


@connectors_bp.get('/<string:connector_id>/items')
@jwt_required()
def list_items(connector_id):
    user_id = int(get_jwt_identity())
    installation = db.session.get(ConnectorInstallation, connector_id)
    if not installation:
        return jsonify({"error": "Connector not found."}), 404
    try:
        get_vault_access(installation.vault_id, user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    rows = SourceItem.query.filter_by(connector_id=connector_id).order_by(SourceItem.external_id).all()
    actor_type = get_jwt().get('actor_type')
    if is_ai_actor(user_id, actor_type):
        visible = []
        for row in rows:
            node = db.session.get(Node, row.node_id) if row.node_id else None
            if not node:
                visible.append(row)
                continue
            try:
                assert_readable(node, user_id, actor_type=actor_type,
                                include_quarantined=_include_quarantined())
            except PermissionError:
                continue
            visible.append(row)
        rows = visible
    return jsonify([serialize_item(row) for row in rows])


@connectors_bp.get('/curation-jobs/<string:job_id>')
@jwt_required()
def get_curation_job(job_id):
    user_id = int(get_jwt_identity())
    job = db.session.get(CurationJob, job_id)
    if not job:
        return jsonify({"error": "Curation job not found."}), 404
    try:
        get_vault_access(job.vault_id, user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    return jsonify(serialize_curation_job(job))


@connectors_bp.get('/provenance/nodes/<string:node_id>')
@jwt_required()
def node_provenance(node_id):
    user_id = int(get_jwt_identity())
    node = db.session.get(Node, node_id)
    if not node:
        return jsonify({"error": "Node not found."}), 404
    try:
        get_vault_access(node.vault_id, user_id)
        assert_readable(node, user_id, actor_type=get_jwt().get('actor_type'),
                        include_quarantined=_include_quarantined())
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    links = NodeSourceLink.query.filter_by(node_id=node_id).order_by(NodeSourceLink.id).all()
    result = []
    for link in links:
        artifact = db.session.get(SourceArtifact, link.artifact_id)
        result.append({"artifact_id": link.artifact_id, "curation_job_id": link.curation_job_id,
            "external_id": artifact.external_id if artifact else None,
            "source_uri": artifact.source_uri if artifact else None,
            "source_content_hash": link.source_content_hash, "page_from": link.page_from,
            "page_to": link.page_to, "is_stale": link.is_stale})
    return jsonify(result)
