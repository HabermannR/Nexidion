"""PDF upload pipeline, shared by synchronous uploads and queued background runs.

A synchronous upload validates, extracts and imports inside the request. A
background upload only validates and stores the PDF (SourceArtifact.payload) plus
the request on a pending IngestionRun; ingestion_worker executes it later with
exactly the same code path, `execute_pdf_ingestion`.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

from werkzeug.utils import secure_filename

from backend.ingestion.pdf import extract_pdf
from backend.models import (db, ConnectorInstallation, IngestionRun, SourceItem, User, UserType,
                            SourceArtifact, CurationJob, NodeSourceLink)
from backend.services.curation_service import PROMPT_VERSION
from backend.services.image_asset_service import create_asset
from backend.services.ingestion_service import VALID_POLICIES, run_connector
from backend.services.vault_service import get_vault_access, assert_write_allowed

MAX_PDF_BYTES = 100 * 1024 * 1024
WORKFLOWS = {'extract', 'extract_and_curate', 'curate_only'}
GRANULARITIES = {'auto', 'document', 'chapter', 'page'}
PROVIDERS = {'local', 'openai', 'openrouter'}
VISUAL_MODES = {'off', 'auto', 'all'}


@dataclass
class PdfRequest:
    vault_id: int
    user_id: int
    filename: str
    parent_id: str | None
    workflow: str
    granularity: str
    policy: str
    provider: str
    model: str | None
    visual_mode: str
    executor_id: int | None

    def to_json(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_json(cls, data: dict) -> "PdfRequest":
        return cls(**{key: data.get(key) for key in cls.__dataclass_fields__})


def parse_request(vault_id: int, user_id: int, form, upload_filename: str | None) -> PdfRequest:
    """Validate every option up front, so a queued run cannot fail on bad input later."""
    _, role = get_vault_access(vault_id, user_id)
    assert_write_allowed(role, db.session.get(User, user_id))
    if not upload_filename:
        raise ValueError("A PDF is required in multipart field 'file'.")
    filename = secure_filename(upload_filename)
    if not filename or not filename.lower().endswith('.pdf'):
        raise ValueError("The uploaded file must have a .pdf extension.")
    workflow = form.get('mode', 'extract')
    if workflow not in WORKFLOWS:
        raise ValueError('mode must be extract, extract_and_curate, or curate_only')
    granularity = form.get('granularity', 'auto')
    if granularity not in GRANULARITIES:
        raise ValueError('granularity must be auto, document, chapter, or page')
    policy = form.get('policy', 'managed')
    if policy not in VALID_POLICIES:
        raise ValueError(f"policy must be one of: {', '.join(sorted(VALID_POLICIES))}")
    provider = form.get('provider', 'local')
    visual_mode = form.get('visual_mode', 'off')
    executor_id = None
    if workflow != 'extract':
        if provider not in PROVIDERS:
            raise ValueError('provider must be local, openai, or openrouter')
        if visual_mode not in VISUAL_MODES:
            raise ValueError('visual_mode must be off, auto, or all')
        executor = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
        if not executor:
            raise ValueError("No LLM assistant user is configured.")
        get_vault_access(vault_id, executor.id)
        executor_id = executor.id
    return PdfRequest(vault_id=vault_id, user_id=user_id, filename=filename,
                      parent_id=form.get('parent_id') or None, workflow=workflow,
                      granularity=granularity, policy=policy, provider=provider,
                      model=form.get('model') or None, visual_mode=visual_mode,
                      executor_id=executor_id)


def spool_upload(stream) -> str:
    """Copy the upload to a temp file, enforcing size and PDF magic. Caller deletes it."""
    fd, path = tempfile.mkstemp(prefix='nexidion_pdf_', suffix='.pdf')
    try:
        size = 0
        with os.fdopen(fd, 'wb') as target:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise ValueError("PDF exceeds the 100 MiB upload limit.")
                target.write(chunk)
        with open(path, 'rb') as probe:
            if probe.read(5) != b'%PDF-':
                raise ValueError("The uploaded file is not a valid PDF.")
        return path
    except BaseException:
        os.unlink(path)
        raise


def pdf_installation(vault_id: int, user_id: int) -> ConnectorInstallation:
    installation = ConnectorInstallation.query.filter_by(
        vault_id=vault_id, plugin_name='pdf', name='PDF uploads').first()
    if not installation:
        installation = ConnectorInstallation(
            vault_id=vault_id, plugin_name='pdf', name='PDF uploads', mode='ingest',
            config={"policy": "managed"}, created_by_id=user_id)
        db.session.add(installation)
        db.session.commit()
    return installation


def store_artifact(installation: ConnectorInstallation, filename: str, payload: bytes,
                   extraction=None) -> SourceArtifact:
    """The stored PDF for this exact content, created once. A new version of the
    same file marks provenance links to earlier versions stale."""
    content_hash = hashlib.sha256(payload).hexdigest()
    artifact = SourceArtifact.query.filter_by(connector_id=installation.id, external_id=filename,
                                              content_hash=content_hash).first()
    if not artifact:
        previous_ids = db.session.execute(db.select(SourceArtifact.id).filter_by(
            connector_id=installation.id, external_id=filename)).scalars().all()
        if previous_ids:
            NodeSourceLink.query.filter(NodeSourceLink.artifact_id.in_(previous_ids)).update(
                {"is_stale": True}, synchronize_session=False)
        artifact = SourceArtifact(connector_id=installation.id, external_id=filename,
                                  content_hash=content_hash, mime_type='application/pdf',
                                  source_uri=f"upload://{filename}", payload=payload,
                                  extracted_json={}, metadata_json={})
        db.session.add(artifact)
    if extraction is not None and not artifact.extracted_json:
        artifact.extracted_json = {"pages": extraction.pages, "outline": extraction.outline}
        artifact.metadata_json = extraction.metadata
    db.session.commit()
    return artifact


def execute_pdf_ingestion(request: PdfRequest, installation: ConnectorInstallation,
                          artifact: SourceArtifact, path: str, *, extraction=None,
                          run: IngestionRun | None = None):
    """Extract, store images, import canonical nodes and queue curation.

    Returns (run, curation_job). `run` is created by run_connector unless a queued
    run is passed in; curate_only produces no import run of its own.
    """
    if extraction is None:
        extraction = extract_pdf(path)
    if not artifact.extracted_json:
        artifact.extracted_json = {"pages": extraction.pages, "outline": extraction.outline}
        artifact.metadata_json = extraction.metadata
        db.session.commit()

    image_urls_by_page: dict[str, list[str]] = {}
    stem = os.path.splitext(request.filename)[0]
    for ordinal, image in enumerate(extraction.images, 1):
        try:
            asset = create_asset(request.vault_id, request.user_id, image['data'],
                                 f"{stem}-page-{image['page']}-{ordinal}.{image['extension']}",
                                 source_artifact_id=artifact.id, page_number=image['page'])
        except ValueError:
            continue
        image_urls_by_page.setdefault(str(image['page']), []).append(
            f'/api/vaults/{request.vault_id}/assets/{asset.id}')

    if request.workflow != 'curate_only':
        run = run_connector(installation.id, request.user_id, run=run, config_override={
            "path": path, "external_id": request.filename, "title": stem,
            "source_uri": f"upload://{request.filename}", "parent_id": request.parent_id,
            "policy": request.policy, "granularity": request.granularity,
            "image_urls_by_page": image_urls_by_page, "extraction": extraction,
        })

    job = None
    if request.workflow != 'extract':
        curation_parent_id = request.parent_id
        if request.workflow != 'curate_only':
            container = SourceItem.query.filter_by(
                connector_id=installation.id, external_id=f"{request.filename}#container").first()
            if container and container.node_id:
                curation_parent_id = container.node_id
        job = CurationJob(artifact_id=artifact.id, vault_id=request.vault_id,
                          parent_id=curation_parent_id, mode=request.workflow,
                          provider=request.provider, model=request.model,
                          visual_mode=request.visual_mode, prompt_version=PROMPT_VERSION,
                          requested_by_id=request.user_id, executed_by_id=request.executor_id)
        db.session.add(job)
        db.session.commit()
        if run is not None:
            run.stats = {**(run.stats or {}), "curation_job_id": job.id}
            db.session.commit()
    return run, job


def ingest_now(request: PdfRequest, stream):
    """Synchronous upload: everything happens inside the request."""
    installation = pdf_installation(request.vault_id, request.user_id)
    path = spool_upload(stream)
    try:
        extraction = extract_pdf(path)
        with open(path, 'rb') as handle:
            artifact = store_artifact(installation, request.filename, handle.read(), extraction)
        run, job = execute_pdf_ingestion(request, installation, artifact, path, extraction=extraction)
        return run, installation, job, artifact
    finally:
        _unlink(path)


def enqueue(request: PdfRequest, stream):
    """Background upload: store the PDF and a pending run, return at once."""
    installation = pdf_installation(request.vault_id, request.user_id)
    path = spool_upload(stream)
    try:
        with open(path, 'rb') as handle:
            artifact = store_artifact(installation, request.filename, handle.read())
    finally:
        _unlink(path)
    run = IngestionRun(connector_id=installation.id, requested_by_id=request.user_id,
                       executed_by_id=request.user_id, status="pending", stats={},
                       artifact_id=artifact.id, request_json=request.to_json())
    db.session.add(run)
    db.session.commit()
    return run, installation, artifact


def execute_queued_run(run: IngestionRun) -> None:
    """Worker entry point for a claimed pending run."""
    request = PdfRequest.from_json(run.request_json or {})
    installation = db.session.get(ConnectorInstallation, run.connector_id)
    artifact = db.session.get(SourceArtifact, run.artifact_id) if run.artifact_id else None
    if installation is None or artifact is None or not artifact.payload:
        raise ValueError("The stored PDF for this run no longer exists.")
    # Access may have been revoked between upload and execution.
    _, role = get_vault_access(request.vault_id, request.user_id)
    assert_write_allowed(role, db.session.get(User, request.user_id))
    fd, path = tempfile.mkstemp(prefix='nexidion_pdf_', suffix='.pdf')
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(artifact.payload)
        execute_pdf_ingestion(request, installation, artifact, path, run=run)
        if request.workflow == 'curate_only':
            # No import happened; the run only tracked extraction and queueing.
            run = db.session.get(IngestionRun, run.id)
            run.status = "completed"
            run.stats = {"created": 0, "updated": 0, "unchanged": 0, "total": 0, "items": [],
                         **(run.stats or {})}
            run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
    finally:
        _unlink(path)


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
