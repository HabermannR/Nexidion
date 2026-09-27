"""Executes queued ingestion runs and recovers runs whose worker died.

Runs are claimed with FOR UPDATE SKIP LOCKED, so any number of executors can
share the queue: the in-app thread started by `start_worker` (default, needs no
extra service) and the optional task runner (agent/loop.py) both call
`process_next_run`.

Liveness is a heartbeat: while a run executes, a side thread refreshes
`heartbeat_at` on its own connection. A run still 'processing' whose heartbeat is
older than STALE_AFTER was abandoned by a dead worker (container restart, OOM,
gunicorn timeout); `recover_stale_runs` re-queues it once if it can be replayed
from its stored request, and otherwise marks it failed with an explanation.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, and_, update

from backend.models import db, IngestionRun

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = int(os.environ.get("NEXIDION_INGEST_HEARTBEAT_SECONDS", "30"))
STALE_AFTER = timedelta(seconds=int(os.environ.get("NEXIDION_INGEST_STALE_SECONDS", "300")))
POLL_SECONDS = float(os.environ.get("NEXIDION_INGEST_POLL_SECONDS", "10"))
MAX_ATTEMPTS = 2
INTERRUPTED = "Interrupted: the worker stopped before this import finished."


def _now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def heartbeat(app, run_id: str, interval: float = HEARTBEAT_SECONDS):
    """Refresh the run's heartbeat on a separate connection until the block exits."""
    stop = threading.Event()

    def beat():
        while not stop.wait(interval):
            try:
                with app.app_context(), db.engine.begin() as connection:
                    connection.execute(update(IngestionRun.__table__)
                                       .where(IngestionRun.__table__.c.id == run_id)
                                       .values(heartbeat_at=_now()))
            except Exception:  # never let liveness bookkeeping kill the import
                log.exception("Heartbeat for ingestion run %s failed", run_id)

    thread = threading.Thread(target=beat, name=f"ingest-heartbeat-{run_id[:8]}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)


def recover_stale_runs(now: datetime | None = None) -> dict:
    now = now or _now()
    cutoff = now - STALE_AFTER
    stale = (IngestionRun.query
             .filter(IngestionRun.status == "processing",
                     or_(IngestionRun.heartbeat_at < cutoff,
                         and_(IngestionRun.heartbeat_at.is_(None), IngestionRun.created_at < cutoff)))
             .with_for_update(skip_locked=True).all())
    requeued = failed = 0
    for run in stale:
        if run.request_json and (run.attempts or 0) < MAX_ATTEMPTS:
            run.status, run.error, run.heartbeat_at = "pending", f"{INTERRUPTED} Retrying.", None
            requeued += 1
        else:
            run.status, run.completed_at = "failed", now
            run.error = (f"{INTERRUPTED} Upload the file again." if not run.request_json
                         else f"{INTERRUPTED} Gave up after {run.attempts} attempts.")
            failed += 1
    db.session.commit()
    if stale:
        log.warning("Recovered stale ingestion runs: %d re-queued, %d failed", requeued, failed)
    return {"requeued": requeued, "failed": failed}


def claim_next_run() -> IngestionRun | None:
    run = (IngestionRun.query
           .filter(IngestionRun.status == "pending", IngestionRun.artifact_id.isnot(None))
           .order_by(IngestionRun.created_at.asc())
           .with_for_update(skip_locked=True).first())
    if run is None:
        db.session.rollback()
        return None
    now = _now()
    run.status, run.started_at, run.heartbeat_at = "processing", now, now
    run.attempts = (run.attempts or 0) + 1
    db.session.commit()
    return run


def process_next_run(app) -> bool:
    """Claim and execute one queued run. Returns False when the queue is empty."""
    from backend.services.pdf_ingestion_service import execute_queued_run

    run = claim_next_run()
    if run is None:
        return False
    run_id = run.id
    with heartbeat(app, run_id):
        try:
            execute_queued_run(run)
        except Exception as exc:
            db.session.rollback()
            failed = db.session.get(IngestionRun, run_id)
            if failed.status != "failed":  # run_connector records its own failures
                failed.status, failed.error, failed.completed_at = "failed", str(exc), _now()
                db.session.commit()
            log.warning("Ingestion run %s failed: %s", run_id, exc)
    return True


_wake = threading.Event()
_lock = threading.Lock()
_thread: threading.Thread | None = None


def notify() -> None:
    """Wake the in-app worker now instead of at its next poll."""
    _wake.set()


def _loop(app) -> None:
    while True:
        try:
            with app.app_context():
                recover_stale_runs()
                while process_next_run(app):
                    pass
        except Exception:
            log.exception("Ingestion worker loop error")
        finally:
            with app.app_context():
                db.session.remove()
        _wake.wait(POLL_SECONDS)
        _wake.clear()


def worker_started() -> bool:
    return _thread is not None and _thread.is_alive()


def start_worker(app) -> bool:
    """Start the in-app worker thread once per process. Disabled in tests and with
    NEXIDION_INGEST_WORKER=off (e.g. when only the task runner should execute)."""
    global _thread
    if app.testing or os.environ.get("NEXIDION_INGEST_WORKER", "on").lower() in {"off", "0", "false"}:
        return False
    with _lock:
        if _thread is not None and _thread.is_alive():
            return True
        _thread = threading.Thread(target=_loop, args=(app,), name="ingestion-worker", daemon=True)
        _thread.start()
    return True
