"""
backend/runner/loop.py
======================
Task Runner — Database Access Model

This runner uses two DB access patterns intentionally:

1. Raw psycopg2 (claim_oldest_task, mark_task_raw):
   FOR UPDATE SKIP LOCKED is a Postgres primitive for safe concurrent
   task claiming. It has no clean ORM equivalent and requires explicit
   transaction boundaries. Used only for task queue operations.

2. SQLAlchemy via Flask app context (all svc_* calls):
   All content writes go through the same node_service functions the
   Flask API uses. Version history, internal links, and all business
   logic run through the same code path as regular user actions.

Authorization: the runner does not call assert_write_allowed() or
_verify_vault_access(). This is intentional — the task row is the proof
of authorization. A task only exists if an authenticated user created it
through the API. The runner is a trusted internal process, not a public
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
from backend.models import User, UserType
from runner.audit import Audit
from runner.agent import run_agent
from runner.replay import _run_replay

flask_app = create_app()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GPT_TOKEN         = os.environ.get("OPENAI_API_KEY")
GPT_MODEL         = os.environ.get("OPENAI_MODEL", "gpt-4o")
LOCAL_LLM_URL     = os.environ.get("LOCAL_LLM_URL")
LOCAL_LLM_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "not-needed")

POLL_INTERVAL = int(os.environ.get("NEXIDION_POLL_INTERVAL", "5"))
AUDIT_DIR     = os.environ.get("NEXIDION_AUDIT_DIR", "./audit_logs")

MAX_LOOP_TURNS   = 25
MAX_TOOL_FETCHES = 20

# Nodes with this icon are write-protected — agent may MOVE but never edit content.
BLACKLIST_ICON = "bxs-lock-alt"

# Nodes with this icon are fully private — agent cannot read OR write content.
READ_LOCK_ICON = "bxs-no-entry"

if not GPT_TOKEN and not LOCAL_LLM_URL:
    print("ERROR: Neither OPENAI_API_KEY nor LOCAL_LLM_URL is set in .env", flush=True)
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
            UPDATE tasks
            SET    status = 'processing'
            WHERE  id = (
                SELECT id FROM tasks
                WHERE  status IN ('pending', 'pending_demo')
                ORDER  BY created_at ASC
                LIMIT  1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, vault_id, instruction, context_node_ids, created_at, status, meta
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
            now      = datetime.now(timezone.utc)
            ops_json = json.dumps(operations) if operations is not None else None
            cur.execute("""
                UPDATE tasks
                SET status         = %s,
                    finish_summary = %s,
                    operations     = %s,
                    completed_at   = %s
                WHERE id = %s
            """, (status, summary, ops_json, now, task_id))
        elif log is not None:
            # Intermediate status update with a progress log message
            cur.execute("""
                UPDATE tasks
                SET status = %s, status_log = %s
                WHERE id = %s
            """, (status, log, task_id))
        else:
            cur.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))
        conn.commit()
    _log(f"Task {task_id} → {status}" + (f" ({log})" if log else ""))


# ---------------------------------------------------------------------------
# TASK DISPATCH
# ---------------------------------------------------------------------------

def _execute_task(task_row: dict, conn) -> None:
    """Run either the real LLM agent or the replay engine, depending on task status."""
    task_id      = task_row["id"]
    vault_id     = task_row["vault_id"]
    orig_status  = task_row["status"]   # value before claim set it to 'processing'

    with flask_app.app_context():
        audit = Audit(
            task_id=task_id,
            vault_id=vault_id,
            instruction=task_row["instruction"],
            context_node_ids=task_row["context_node_ids"],
            created_at=task_row["created_at"],
        )

        try:
            if orig_status == "pending_demo":
                _log(f"Mode: REPLAY (pending_demo)")

                # Import lazily to avoid pulling ORM models at module load time
                from backend.models import db, Vault, DemoState  # noqa: PLC0415

                def _update_status(tid, status, log=None):
                    mark_task_raw(conn, tid, status, log=log)

                summary = asyncio.run(_run_replay(
                    task_row      = task_row,
                    vault_id      = vault_id,
                    agent_user_id = AGENT_USER_ID,
                    flask_app     = flask_app,
                    db            = db,
                    Vault         = Vault,
                    DemoState     = DemoState,
                    update_status_fn = _update_status,
                    log_fn        = _log,
                ))
                mark_task_raw(conn, task_id, "completed", summary=summary,
                              operations=audit.writes)
                audit.save("completed", summary, AUDIT_DIR, GPT_MODEL, _log)
                _log(f"✅ {summary}")

            else:
                _log(f"Mode: REAL LLM")
                summary = run_agent(
                    task_row         = task_row,
                    audit            = audit,
                    agent_user_id    = AGENT_USER_ID,
                    gpt_token        = GPT_TOKEN,
                    gpt_model        = GPT_MODEL,
                    local_llm_url    = LOCAL_LLM_URL,
                    local_llm_api_key = LOCAL_LLM_API_KEY,
                    max_loop_turns   = MAX_LOOP_TURNS,
                    max_tool_fetches = MAX_TOOL_FETCHES,
                    blacklist_icon   = BLACKLIST_ICON,
                    read_lock_icon   = READ_LOCK_ICON,
                    log_fn           = _log,
                )
                mark_task_raw(conn, task_id, "completed", summary=summary,
                              operations=audit.writes)
                audit.save("completed", summary, AUDIT_DIR, GPT_MODEL, _log)
                _log(f"✅ {summary}")

        except Exception as e:
            _log(f"✗ Task failed: {e}")
            mark_task_raw(conn, task_id, "failed", summary=str(e),
                          operations=audit.writes)
            audit.save("failed", str(e), AUDIT_DIR, GPT_MODEL, _log)


# ---------------------------------------------------------------------------
# POLLING LOOP
# ---------------------------------------------------------------------------

def run_loop():
    _log("=" * 60)
    _log("Nexidion Task Runner")
    with flask_app.app_context():
        agent = User.query.get(AGENT_USER_ID)
        _log(f"Agent user ID : {AGENT_USER_ID} ({agent.username})")
    _log(f"Poll interval : {POLL_INTERVAL}s")
    _log("Vault ID      : read from each task")
    _log("=" * 60)

    conn = db_connect()
    _log("DB connection established.")

    while True:
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

        _execute_task(task_row, conn)

        time.sleep(POLL_INTERVAL)
