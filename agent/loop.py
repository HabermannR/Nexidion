"""
agent/loop.py
======================
Task Runner — Database Access Model

This agent uses two DB access patterns intentionally:

1. Raw psycopg2 (claim_oldest_task, mark_task_raw):
   FOR UPDATE SKIP LOCKED is a Postgres primitive for safe concurrent
   task claiming. It has no clean ORM equivalent and requires explicit
   transaction boundaries. Used only for task queue operations.

2. SQLAlchemy via Flask app context (all svc_* calls):
   All content writes go through the same node_service functions the
   Flask API uses. Version history, internal links, and all business
   logic run through the same code path as regular user actions.

Authorization: the agent does not call assert_write_allowed() or
_verify_vault_access(). This is intentional — the task row is the proof
of authorization. A task only exists if an authenticated user created it
through the API. The agent is a trusted internal process, not a public
endpoint.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from backend.app import create_app
from backend.models import db, User, UserType, SummaryArtifact, CurationJob
from backend.services.summary_generation import process_summary_artifact
from backend.services.curation_service import process_curation_job, fail_curation_job
from backend.services.vault_service import get_vault_access
from agent.audit import Audit
from agent.agent import run_agent

flask_app = create_app()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GPT_TOKEN         = os.environ.get("OPENAI_API_KEY")
GPT_MODEL         = os.environ.get("OPENAI_MODEL", "gpt-4o")
LOCAL_LLM_URL     = os.environ.get("LOCAL_LLM_URL")
LOCAL_LLM_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "not-needed")
LOCAL_LLM_MODEL   = os.environ.get("LOCAL_LLM_MODEL") or "local"
OPENROUTER_TOKEN  = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL    = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL  = os.environ.get("OPENROUTER_MODEL")

POLL_INTERVAL = int(os.environ.get("NEXIDION_POLL_INTERVAL", "5"))
AUDIT_DIR     = os.environ.get("NEXIDION_AUDIT_DIR", "./audit_logs")
STREAM_DEBUG_DIR = os.environ.get("NEXIDION_STREAM_DEBUG_DIR", "./audit_logs/streams")
CAPTURE_STREAM_PAYLOADS = os.environ.get("NEXIDION_CAPTURE_STREAM_PAYLOADS", "false").lower() == "true"
REQUEST_TIMEOUT_S = float(os.environ.get("NEXIDION_LLM_REQUEST_TIMEOUT_SECONDS", "1800"))
HARD_TURN_TIMEOUT_S = float(os.environ.get("NEXIDION_LLM_HARD_TURN_TIMEOUT_SECONDS", "1800"))
REASONING_EFFORT = os.environ.get("NEXIDION_REASONING_EFFORT") or None
MAX_OUTPUT_TOKENS = int(os.environ.get("NEXIDION_MAX_OUTPUT_TOKENS", "12000"))

MAX_LOOP_TURNS   = 25
MAX_TOOL_FETCHES = 20

# Nodes with this icon are write-protected — agent may MOVE but never edit content.
BLACKLIST_ICON = "bxs-lock-alt"

# Nodes with this icon are fully private — agent cannot read OR write content.
READ_LOCK_ICON = "bxs-no-entry"

if not GPT_TOKEN and not LOCAL_LLM_URL and not OPENROUTER_TOKEN:
    print("ERROR: No local, OpenAI, or OpenRouter LLM provider is configured", flush=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# AGENT USER RESOLUTION
# ---------------------------------------------------------------------------

def _resolve_agent_user() -> int:
    with flask_app.app_context():
        agent = User.query.filter_by(
            user_type=UserType.LLM_ASSISTANT
        ).first()
        if not agent:
            print(
                "ERROR: No LLM agent user found. "
                "Run 'flask create-llm-agent' first.",
                flush=True,
            )
            sys.exit(1)
        return agent.id


AGENT_USER_ID = _resolve_agent_user()


# ---------------------------------------------------------------------------
# RAW DB — task claiming (FOR UPDATE SKIP LOCKED)
# ---------------------------------------------------------------------------

def db_connect():
    """Build DSN from the same env vars that config.py uses — shared .env file."""
    dsn = (
        f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ.get('DB_HOST', 'localhost')}:{os.environ.get('DB_PORT', '5432')}"
        f"/{os.environ['DB_NAME']}"
    )
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)


def claim_oldest_task(conn):
    """Atomically grab the oldest pending task and mark it processing."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH grabbed AS (
                SELECT id, vault_id, instruction, context_node_ids, created_at, status,
                       requested_by_id, executed_by_id, llm_provider, llm_model,
                       allowed_write_node_ids, allowed_write_operations
                FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            ),
            updated AS (
                UPDATE tasks
                SET status = 'processing'
                WHERE id = (SELECT id FROM grabbed)
            )
            SELECT * FROM grabbed;
        """)
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def mark_task_raw(conn, task_id: str, status: str,
                  summary: str = None, operations: list = None,
                  log: str = None):
    """Update task status via raw connection (used for the claimed task)."""
    with conn.cursor() as cur:
        if status in ('completed', 'failed'):
            now = datetime.now(timezone.utc)
            ops_json = json.dumps(operations) if operations is not None else None
            cur.execute("""
                UPDATE tasks
                SET status         = %s,
                    finish_summary = %s,
                    operations     = %s,
                    completed_at   = %s
                WHERE id = %s
            """, (status, summary, ops_json, now, task_id))
        else:
            # Write the log message into finish_summary during processing so the
            # frontend's polling can show live step progress ("Creating node...", etc.)
            # without needing a separate status_log column.
            if log:
                cur.execute(
                    "UPDATE tasks SET status = %s, finish_summary = %s WHERE id = %s",
                    (status, log, task_id)
                )
            else:
                cur.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))

        conn.commit()

    _log(f"Task {task_id} → {status}" + (f" ({log})" if log else ""))


# ---------------------------------------------------------------------------
# TASK DISPATCH
# ---------------------------------------------------------------------------

def _execute_task(task_row: dict, conn) -> None:
    """Run a queued LLM task."""
    task_id     = task_row["id"]
    vault_id    = task_row["vault_id"]
    task_agent_user_id = task_row.get("executed_by_id") or AGENT_USER_ID

    with flask_app.app_context():
        audit = Audit(
            task_id=task_id,
            vault_id=vault_id,
            instruction=task_row["instruction"],
            context_node_ids=task_row["context_node_ids"],
            created_at=task_row["created_at"],
        )

        try:
            # NULL provider preserves the pre-selection behaviour: a configured
            # local endpoint wins, otherwise OpenAI, then OpenRouter.
            provider = task_row.get("llm_provider") or (
                "local" if LOCAL_LLM_URL else "openai" if GPT_TOKEN else "openrouter"
            )
            provider_config = {
                "local": (LOCAL_LLM_API_KEY, task_row.get("llm_model") or LOCAL_LLM_MODEL, LOCAL_LLM_URL, None),
                "openai": (GPT_TOKEN, task_row.get("llm_model") or GPT_MODEL, None, None),
                "openrouter": (
                    OPENROUTER_TOKEN,
                    task_row.get("llm_model") or OPENROUTER_MODEL,
                    OPENROUTER_URL,
                    {
                        key: value for key, value in {
                            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER"),
                            "X-Title": os.environ.get("OPENROUTER_APP_TITLE"),
                        }.items() if value
                    },
                ),
            }
            if provider not in provider_config:
                raise RuntimeError(f"Unsupported LLM provider: {provider}")
            token, model, base_url, default_headers = provider_config[provider]
            if provider == "local" and not base_url:
                raise RuntimeError("Local LLM provider is not configured")
            if provider != "local" and not token:
                raise RuntimeError(f"{provider.title()} API key is not configured")
            if not model:
                raise RuntimeError(f"No model is configured for {provider}")
            _log(f"Mode: REAL LLM ({provider})")
            summary = run_agent(
                task_row=task_row,
                audit=audit,
                agent_user_id=task_agent_user_id,
                gpt_token=token,
                gpt_model=model,
                local_llm_url=base_url,
                local_llm_api_key=token or LOCAL_LLM_API_KEY,
                default_headers=default_headers,
                max_loop_turns=MAX_LOOP_TURNS,
                max_tool_fetches=MAX_TOOL_FETCHES,
                blacklist_icon=BLACKLIST_ICON,
                read_lock_icon=READ_LOCK_ICON,
                log_fn=_log,
                record_full_text=False,
                request_timeout_s=REQUEST_TIMEOUT_S,
                hard_turn_timeout_s=HARD_TURN_TIMEOUT_S,
                reasoning_effort=REASONING_EFFORT,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                stream_debug_dir=STREAM_DEBUG_DIR,
                capture_stream_payloads=CAPTURE_STREAM_PAYLOADS,
            )
            mark_task_raw(conn, task_id, "completed", summary=summary,
                          operations=audit.writes)
            audit.save("completed", summary, AUDIT_DIR, model, _log)
            _log(f"✅ {summary}")


        except Exception as e:
            conn.rollback()  # <-- ADD THIS LINE to clear the aborted transaction
            _log(f"✗ Task failed: {e}")
            mark_task_raw(conn, task_id, "failed", summary=str(e),
                          operations=audit.writes)
            audit.save("failed", str(e), AUDIT_DIR, task_row.get("llm_model") or "unknown", _log)


# ---------------------------------------------------------------------------
# POLLING LOOP
# ---------------------------------------------------------------------------

def run_loop():
    _log("=" * 60)
    _log("Nexidion Task Runner")
    with flask_app.app_context():
        agent = db.session.get(User, AGENT_USER_ID)
        _log(f"Agent user ID : {AGENT_USER_ID} ({agent.username})")
    _log(f"Poll interval : {POLL_INTERVAL}s")
    _log("Vault ID      : read from each task")
    _log("=" * 60)

    conn = db_connect()
    _log("DB connection established.")

    while True:
        with flask_app.app_context():
            curation_job = (
                CurationJob.query.filter_by(status="pending")
                .order_by(CurationJob.created_at.asc())
                .with_for_update(skip_locked=True).first()
            )
            if curation_job:
                curation_job.status = "processing"
                db.session.commit()
                try:
                    process_curation_job(curation_job)
                except Exception as exc:
                    db.session.rollback()
                    curation_job = db.session.get(CurationJob, curation_job.id)
                    fail_curation_job(curation_job, exc)
                _log(f"Curation {curation_job.id} → {curation_job.status}")
                continue

            artifact = (
                SummaryArtifact.query.filter_by(status="pending")
                .order_by(SummaryArtifact.created_at.asc())
                .with_for_update(skip_locked=True).first()
            )
            if artifact:
                artifact.status = "processing"
                db.session.commit()
                process_summary_artifact(artifact)
                db.session.commit()
                _log(f"Summary {artifact.id} → {artifact.status}")
                continue

        try:
            task_row = claim_oldest_task(conn)
        except Exception as e:
            _log(f"DB error during poll: {e} — reconnecting...")
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)
            conn = db_connect()
            continue

        if task_row is None:
            time.sleep(POLL_INTERVAL)
            continue

        _log(f"Claimed task : {task_row['id']}")
        _log(f"Instruction  : {task_row['instruction']}")

        # Pre-flight: verify the agent user has access to the vault BEFORE
        # dispatching. Without this, the task fails mid-run with
        # "LLM has no access to the vault" after work has already started.
        try:
            with flask_app.app_context():
                get_vault_access(task_row["vault_id"], task_row.get("executed_by_id") or AGENT_USER_ID)
        except (PermissionError, ValueError) as e:
            _log(f"✗ Vault access check failed for vault {task_row['vault_id']}: {e}")
            mark_task_raw(conn, task_row["id"], "failed",
                          summary=f"LLM has no access to the vault: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        _execute_task(task_row, conn)

        time.sleep(POLL_INTERVAL)
