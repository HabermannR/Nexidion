"""Queued PDF ingestion: enqueue, worker execution and recovery of dead runs."""
import io
from datetime import datetime, timedelta, timezone

import pymupdf

from backend.models import (db, IngestionRun, Node, SourceArtifact, CurationJob, VaultAccess,
                            VaultRole)
from backend.services import ingestion_worker


def _pdf(text):
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def _enqueue(client, headers, vault_id, payload, filename="queued.pdf", **form):
    return client.post('/api/connectors/pdf/ingest', headers=headers, data={
        "vault_id": str(vault_id), "background": "true",
        "file": (io.BytesIO(payload), filename), **form,
    }, content_type='multipart/form-data')


def test_background_upload_returns_at_once_and_worker_imports_it(
        app, client, auth_headers_1, test_vault_1_obj, db_session):
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("Queued body"))

    assert response.status_code == 202
    data = response.get_json()
    assert data["status"] == "pending"
    assert Node.query.count() == 0  # nothing extracted inside the request
    assert SourceArtifact.query.filter_by(id=data["artifact_id"]).one().payload

    assert ingestion_worker.process_next_run(app) is True
    assert ingestion_worker.process_next_run(app) is False

    run = client.get(f'/api/connectors/runs/{data["id"]}', headers=auth_headers_1).get_json()
    assert run["status"] == "completed"
    assert run["attempts"] == 1
    assert run["stats"]["created"] == 2
    page = Node.query.filter_by(content_kind="canonical_source").one()
    assert "Queued body" in page.current_version_object.content
    artifact = db.session.get(SourceArtifact, data["artifact_id"])
    assert artifact.extracted_json["pages"]  # curation reads this


def test_background_upload_validates_before_queueing(client, auth_headers_1, test_vault_1_obj, db_session):
    fake = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "background": "true",
        "file": (io.BytesIO(b"nope"), "fake.pdf")}, content_type='multipart/form-data')
    bad_mode = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("x"), mode="shred")

    assert fake.status_code == 400
    assert bad_mode.status_code == 400
    assert IngestionRun.query.count() == 0


def test_background_extract_and_curate_queues_curation_after_extraction(
        app, client, auth_headers_1, test_vault_1_obj, test_llm_agent_obj, db_session):
    db_session.session.add(VaultAccess(user_id=test_llm_agent_obj.id,
                                       vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR))
    db_session.session.commit()
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("Curate me"),
                        mode="extract_and_curate", provider="local", visual_mode="off")
    assert CurationJob.query.count() == 0

    ingestion_worker.process_next_run(app)

    run = client.get(f'/api/connectors/runs/{response.get_json()["id"]}', headers=auth_headers_1).get_json()
    job = CurationJob.query.one()
    assert run["curation_job_id"] == job.id
    container = Node.query.filter_by(content_kind="source_container").one()
    assert job.parent_id == container.id


def test_background_curate_only_completes_without_importing(
        app, client, auth_headers_1, test_vault_1_obj, test_llm_agent_obj, db_session):
    db_session.session.add(VaultAccess(user_id=test_llm_agent_obj.id,
                                       vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR))
    db_session.session.commit()
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("Only curate"),
                        mode="curate_only", provider="local", visual_mode="off")

    ingestion_worker.process_next_run(app)

    run = client.get(f'/api/connectors/runs/{response.get_json()["id"]}', headers=auth_headers_1).get_json()
    assert run["status"] == "completed"
    assert run["curation_job_id"] == CurationJob.query.one().id
    assert Node.query.count() == 0


def test_failed_run_records_the_error(app, client, auth_headers_1, test_vault_1_obj, db_session, monkeypatch):
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("Broken"))
    monkeypatch.setattr("backend.services.pdf_ingestion_service.extract_pdf",
                        lambda *_: (_ for _ in ()).throw(RuntimeError("parser exploded")))

    ingestion_worker.process_next_run(app)

    run = db.session.get(IngestionRun, response.get_json()["id"])
    assert run.status == "failed"
    assert "parser exploded" in run.error


def test_stale_runs_are_requeued_once_then_failed(app, client, auth_headers_1, test_vault_1_obj, db_session):
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("Crash"))
    run = db.session.get(IngestionRun, response.get_json()["id"])
    long_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    # First crash: claimed, then the worker died (heartbeat stopped).
    run.status, run.attempts, run.heartbeat_at = "processing", 1, long_ago
    db.session.commit()
    assert ingestion_worker.recover_stale_runs() == {"requeued": 1, "failed": 0}
    assert db.session.get(IngestionRun, run.id).status == "pending"

    # Second crash: give up with an explanation.
    run = db.session.get(IngestionRun, run.id)
    run.status, run.attempts, run.heartbeat_at = "processing", 2, long_ago
    db.session.commit()
    assert ingestion_worker.recover_stale_runs() == {"requeued": 0, "failed": 1}
    run = db.session.get(IngestionRun, run.id)
    assert run.status == "failed" and "Interrupted" in run.error


def test_legacy_stuck_synchronous_run_is_failed_not_retried(
        app, client, auth_headers_1, test_vault_1_obj, db_session):
    sync = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "file": (io.BytesIO(_pdf("sync")), "sync.pdf")},
        content_type='multipart/form-data')
    run = db.session.get(IngestionRun, sync.get_json()["id"])
    run.status, run.heartbeat_at = "processing", None
    run.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.session.commit()

    assert ingestion_worker.recover_stale_runs() == {"requeued": 0, "failed": 1}


def test_live_runs_are_left_alone(app, client, auth_headers_1, test_vault_1_obj, db_session):
    response = _enqueue(client, auth_headers_1, test_vault_1_obj.id, _pdf("alive"))
    run = db.session.get(IngestionRun, response.get_json()["id"])
    run.status, run.attempts, run.heartbeat_at = "processing", 1, datetime.now(timezone.utc)
    db.session.commit()

    assert ingestion_worker.recover_stale_runs() == {"requeued": 0, "failed": 0}
