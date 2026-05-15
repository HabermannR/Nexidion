"""
task_runner.py
==============
Nexidion autonomous task runner.

Runs as a standalone daemon on the Raspberry Pi. Polls the database every 5 s
for pending tasks and executes them using the agentic loop.

Calls the service layer directly — no HTTP, no JWT required.

Environment variables — all read from ~/KnowledgeBase/.env:
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME  — Postgres credentials
    OPENAI_API_KEY
    OPENAI_MODEL        — defaults to gpt-5.4
    NEXIDION_AUDIT_DIR  — defaults to ./audit_logs
    NEXIDION_POLL_INTERVAL — seconds between polls, defaults to 5

Vault ID comes from each task row in the database — not from config.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx
from openai import OpenAI

# ---------------------------------------------------------------------------
# Bootstrap Flask app context — gives SQLAlchemy its session.
# No web server is started; we just borrow the setup.
# ---------------------------------------------------------------------------
from backend.app import create_app
from backend.services import node_service, task_service
from backend.models import db

flask_app = create_app()

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

GPT_TOKEN = os.environ.get("OPENAI_API_KEY")
GPT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")

POLL_INTERVAL = int(os.environ.get("NEXIDION_POLL_INTERVAL", "5"))
AUDIT_DIR     = os.environ.get("NEXIDION_AUDIT_DIR", "./audit_logs")

# The agent user — user ID 2 (default-llm), type llm_assistant.
# All service calls are made on behalf of this user.
AGENT_USER_ID = 2

MAX_LOOP_TURNS   = 25
MAX_TOOL_FETCHES = 20

# Nodes with this icon are write-protected — agent may MOVE but never edit content.
BLACKLIST_ICON = "bxs-lock-alt"

# Nodes with this icon are fully private — agent cannot read OR write content.
READ_LOCK_ICON = "bxs-no-entry"

# Store the ETag in memory
_agent_tree_etags = {}
_cached_agent_trees = {}
if not GPT_TOKEN:
    print("ERROR: OPENAI_API_KEY is missing from .env", flush=True)
    sys.exit(1)


# ==========================================
# LOGGING
# ==========================================

def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ==========================================
# AUDIT
# ==========================================

class Audit:
    def __init__(self, task):
        self.task        = task
        self.started_at  = datetime.now(timezone.utc)
        self.turns: list = []
        self.writes: list =[]
        self._current_turn: dict | None = None

    def begin_turn(self, turn_num: int):
        self._current_turn = {
            "turn":       turn_num,
            "timestamp":  _iso(),
            "elapsed_s":  None,
            "tool_calls":[],
        }

    def end_turn(self, elapsed: float):
        if self._current_turn:
            self._current_turn["elapsed_s"] = round(elapsed, 2)
            self.turns.append(self._current_turn)
            self._current_turn = None

    def record_tool(self, name: str, args: dict, result: str, detail: str):
        entry = {"name": name, "args": args, "result": result, "detail": detail}
        if self._current_turn is not None:
            self._current_turn["tool_calls"].append(entry)

    def record_write(self, operation: str, node_id: str, detail: dict):
        self.writes.append({
            "timestamp": _iso(),
            "operation": operation,
            "node_id":   node_id,
            "detail":    detail,
        })

    def save(self, outcome: str, finish_summary: str | None):
        ended_at = datetime.now(timezone.utc)
        task = self.task

        doc = {
            "task": {
                "id":               str(task.id),
                "vault_id":         task.vault_id,
                "instruction":      task.instruction,
                "context_node_ids": task.context_node_ids,
                "created_at":       task.created_at.isoformat(),
            },
            "started_at":     self.started_at.isoformat(),
            "ended_at":       ended_at.isoformat(),
            "duration_s":     round((ended_at - self.started_at).total_seconds(), 2),
            "outcome":        outcome,
            "finish_summary": finish_summary,
            "model":          GPT_MODEL,
            "turns":          self.turns,
            "writes":         self.writes,
        }

        date_dir = os.path.join(AUDIT_DIR, self.started_at.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)
        ts  = self.started_at.strftime("%H%M%S")
        tid = str(task.id)[:8]
        path = os.path.join(date_dir, f"{tid}_{ts}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        _log(f"Audit saved → {path}")
        return path


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==========================================
# TASK CLAIMING (raw SQL — outside ORM,
# needs FOR UPDATE SKIP LOCKED which
# SQLAlchemy doesn't expose cleanly)
# ==========================================

import psycopg2
import psycopg2.extras

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
                WHERE  status = 'pending'
                ORDER  BY created_at ASC
                LIMIT  1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, vault_id, instruction, context_node_ids, created_at
        """)
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def mark_task_raw(conn, task_id: str, status: str, summary: str = None, operations: list = None):
    """Update task status via raw connection (used for the claimed task)."""
    with conn.cursor() as cur:
        if status in ('completed', 'failed'):
            now = datetime.now(timezone.utc)
            # Dump JSON manually because psycopg2 raw queries need it formatted as a string
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
            cur.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))

        conn.commit()
    _log(f"Task {task_id} → {status}")


# ==========================================
# SERVICE LAYER WRAPPERS
# All calls go through the service layer.
# AGENT_USER_ID is passed where a user is required.
# ==========================================

def svc_get_tree(vault_id: int) -> list:
    global _agent_tree_etags, _cached_agent_trees

    # Get the ETag we have in memory for this specific vault
    client_etag = _agent_tree_etags.get(vault_id)

    # Call the newly updated service function!
    tree_data, etag, is_not_modified = node_service.get_nodes_as_tree(
        vault_id=vault_id,
        user_id=AGENT_USER_ID,
        format_type='agent_tree',
        client_etag=client_etag
    )

    if is_not_modified:
        _log(f"[Cache Hit] Using in-memory tree for vault {vault_id}")
        return _cached_agent_trees[vault_id]

    # If it was modified (or first run), save the new data to memory
    _agent_tree_etags[vault_id] = etag
    _cached_agent_trees[vault_id] = tree_data

    return tree_data


def svc_get_node(vault_id: int, node_id: str) -> dict | None:
    return node_service.get_node_by_id(node_id, vault_id, AGENT_USER_ID)


def svc_get_node_summary(vault_id: int, node_id: str) -> dict | None:
    node = svc_get_node(vault_id, node_id)
    if node is None:
        return {"error": f"Node {node_id} not found."}
    return {
        "id":         node.get("id"),
        "title":      node.get("title"),
        "parent_id":  node.get("parent_id"),
        "icon":       node.get("icon"),
        "ai_summary": node.get("ai_summary"),
    }


def svc_search(vault_id: int, query: str, limit: int = 15) -> dict:
    results = node_service.search_nodes_fulltext(query, vault_id, AGENT_USER_ID, limit=limit)
    return {
        "count":   len(results),
        "results":[{"id": n.get("id"), "title": n.get("title"),
                     "ai_summary": n.get("ai_summary")} for n in results],
    }


def svc_update_node(vault_id: int, node_id: str, content: str | None = None,
                    title: str | None = None) -> dict:
    try:
        node_service.update_node(node_id, vault_id, AGENT_USER_ID,
                                 title=title, content=content)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_update_summary(vault_id: int, node_id: str, ai_summary: str) -> dict:
    try:
        node_service.update_node_ai_summary(node_id, vault_id, AGENT_USER_ID, ai_summary)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_move_node(vault_id: int, node_id: str, new_parent_id: str) -> dict:
    try:
        node_service.move_node(node_id, new_parent_id, vault_id, AGENT_USER_ID)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def svc_create_node(vault_id: int, title: str, parent_id: str,
                    content: str = "", ai_summary: str = "") -> dict:
    try:
        new_node = node_service.create_node(
            title=title, content=content, parent_id=parent_id,
            vault_id=vault_id, author_id=AGENT_USER_ID,
        )
        # ai_summary is set separately
        if ai_summary:
            node_service.update_node_ai_summary(new_node.id, vault_id, AGENT_USER_ID, ai_summary)
        return {"ok": True, "node": {"id": new_node.id}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==========================================
# TREE HELPERS
# ==========================================

def get_children_from_tree(parent_id: str, tree: list) -> list:
    def find(nodes, pid):
        for node in nodes:
            if node["id"] == pid:
                return node.get("children", [])
            found = find(node.get("children",[]), pid)
            if found is not None:
                return found
        return None
    return find(tree, parent_id) or[]


def _redact_if_private(vault_id: int, node_summary: dict) -> dict:
    """Replace summary content with a privacy notice for bxs-no-entry nodes."""
    if node_summary and node_summary.get("icon") == READ_LOCK_ICON:
        return {
            "id":        node_summary["id"],
            "title":     node_summary["title"],
            "parent_id": node_summary.get("parent_id"),
            "icon":      READ_LOCK_ICON,
            "ai_summary": "[private — content not accessible to agent]",
        }
    return node_summary


def get_subtree_summary(vault_id: int, node_id: str) -> dict:
    node = svc_get_node_summary(vault_id, node_id)
    if "error" in node:
        return node

    node = _redact_if_private(vault_id, node)

    # Fetch updated tree securely with caching enabled directly here
    tree = svc_get_tree(vault_id)

    children_stubs = get_children_from_tree(node_id, tree)
    children = [
        _redact_if_private(vault_id, svc_get_node_summary(vault_id, stub["id"]))
        for stub in children_stubs
    ]
    return {**node, "children": children}


def find_root_for_node(node_id: str, tree: list) -> dict | None:
    def find_path(nodes, target, path):
        for node in nodes:
            new_path = path + [node]
            if node["id"] == target:
                return new_path
            result = find_path(node.get("children",[]), target, new_path)
            if result:
                return result
        return None
    path = find_path(tree, node_id, [])
    return path[0] if path else None


def is_read_locked(vault_id: int, node_id: str) -> bool:
    """Returns True for bxs-no-entry nodes — agent cannot read or write content."""
    node = svc_get_node(vault_id, node_id)
    return node.get("icon") == READ_LOCK_ICON if node else False


def is_blacklisted(vault_id: int, node_id: str) -> bool:
    """Returns True for bxs-lock-alt (write-lock) OR bxs-no-entry (full lock)."""
    node = svc_get_node(vault_id, node_id)
    if not node:
        return False
    return node.get("icon") in (BLACKLIST_ICON, READ_LOCK_ICON)


# ==========================================
# TOOL DEFINITIONS (unchanged)
# ==========================================

TOOLS =[
    {
        "type": "function",
        "name": "get_subtree",
        "description": (
            "Fetch a node plus its direct children (titles + AI summaries, no full content). "
            "Use this as your first move when exploring any node. "
            "Does NOT count against the fetch budget."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID of the node."},
            },
            "required": ["node_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_node_summary",
        "description": (
            "Fetch title, parent_id, and AI summary of a single node. "
            "Cheap — prefer this over get_node_content unless you need the full text. "
            "Counts against fetch budget."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID of the node."},
            },
            "required": ["node_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_node_content",
        "description": (
            "Fetch the FULL content + summary of a node. "
            "Use only when the summary is insufficient. Counts against fetch budget."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID of the node."},
            },
            "required":["node_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_nodes",
        "description": (
            "Full-text search across all nodes. Use to discover UUIDs. "
            "Does NOT count against the fetch budget. Keep queries short (1-3 words)."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword or short phrase."},
                "limit": {"type": "integer", "description": "Max results (default 10, max 20)."},
            },
            "required": ["query", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_node",
        "description": (
            "Overwrite a node's content and summary completely. "
            "Use for: full rewrites, bubble-up synthesis, updating with new information. "
            "ai_summary MUST be exactly 3 bullet points starting with '- '."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id":    {"type": "string", "description": "UUID of the node to update."},
                "content":    {"type": "string", "description": "Full Markdown content. At least 2 paragraphs."},
                "ai_summary": {"type": "string", "description": "Exactly 3 bullet points starting with '- '."},
            },
            "required": ["node_id", "content", "ai_summary"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "patch_node",
        "description": (
            "Apply targeted find-and-replace edits to a node's existing content. "
            "Prefer this over write_node when only changing specific parts. "
            "The 'find' string must be an EXACT verbatim match (including whitespace/line breaks). "
            "Include enough surrounding text to be unique."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID of the node to patch."},
                "patches": {
                    "type": "array",
                    "description": "List of find/replace pairs, applied in order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "find":    {"type": "string", "description": "Exact text to find."},
                            "replace": {"type": "string", "description": "Text to replace it with."},
                        },
                        "required": ["find", "replace"],
                        "additionalProperties": False,
                    },
                },
                "ai_summary": {
                    "type":["string", "null"],
                    "description": "Updated summary (3 bullets). Pass null to leave unchanged.",
                },
            },
            "required": ["node_id", "patches", "ai_summary"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "move_node",
        "description": (
            "Move a node to a different parent. "
            "Use for sorting, reorganizing, or reparenting nodes. "
            "Always verify the target parent exists before calling."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id":       {"type": "string", "description": "UUID of the node to move."},
                "new_parent_id": {"type": "string", "description": "UUID of the new parent node."},
            },
            "required": ["node_id", "new_parent_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "create_node",
        "description": (
            "Create a new child node under a given parent. "
            "Use when reorganizing requires a new grouping node. "
            "Always populate content and ai_summary — never leave them empty."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "title":      {"type": "string", "description": "Title of the new node."},
                "parent_id":  {"type": "string", "description": "UUID of the parent node."},
                "content":    {"type": "string", "description": "Initial Markdown content."},
                "ai_summary": {"type": "string", "description": "Exactly 3 bullet points starting with '- '."},
            },
            "required":["title", "parent_id", "content", "ai_summary"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "finish",
        "description": (
            "Signal that all work for this task is complete. "
            "Call this only after every required change has been applied. "
            "Provide a short summary of what was done."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Brief description of all changes made."},
            },
            "required":["summary"],
            "additionalProperties": False,
        },
    },
]


# ==========================================
# SYSTEM PROMPT
# ==========================================

def build_system_prompt(instruction: str, context_nodes_block: str,
                        overview_node: dict | None) -> str:
    overview_block = ""
    if overview_node and "error" not in overview_node:
        overview_block = (
            "\n=== VAULT OVERVIEW (global context) ===\n"
            f"Title: {overview_node.get('title')}\n"
            f"Summary: {overview_node.get('ai_summary')}\n"
            "========================================\n"
        )

    return f"""You are an autonomous knowledge base editor for a personal wiki called Nexidion.
You have been given a task by the vault owner. Execute it fully and independently.
{overview_block}
=== YOUR TASK ===
{instruction}
=================

=== CONTEXT NODES (nodes the user pointed you at) ===
{context_nodes_block}
=====================================================

TOOLS AT YOUR DISPOSAL:
  READ  : get_subtree (free), get_node_summary, get_node_content, search_nodes (free)
  WRITE : write_node, patch_node, move_node, create_node
  DONE  : finish

HOW TO WORK:
- Start by reading the context nodes to understand the current state.
- Use get_subtree first on any node — it is free and immediately shows you the children.
- Prefer get_node_summary over get_node_content; only escalate when you need the full text.
- search_nodes is free — use it liberally to discover UUIDs of related nodes.
- Never invent or guess a UUID. Only use UUIDs returned by tools or provided in context.
- Apply changes as you go using the write tools — do not batch everything to the end.
- For bubble-up synthesis: read children summaries → write_node on the parent.
- For sorting/reorganizing: get_subtree → move_node each child to its correct parent.
- For content updates with new info: get_node_content → patch_node for small changes, write_node for full rewrites.
- patch_node is preferred when only a specific section needs changing.
- When patching, your 'find' text must match EXACTLY (spaces, newlines, punctuation).
- ai_summary must ALWAYS be exactly 3 bullet points starting with '- '.
- Internal links use the format: [[Display Text|UUID]]
- Only link to UUIDs you have confirmed. Never guess a UUID.
- PROTECTED NODES (bxs-lock-alt): write-protected. You MAY move them and read their content.
  You MAY use write_node or patch_node to update their AI summary (content changes will be safely ignored).
- PRIVATE NODES (bxs-no-entry): fully private. You cannot read OR write their content.
  get_node_summary and get_node_content will be blocked. You MAY still move them.
- When all changes are applied, call finish() with a clear summary of what was done.

FETCH BUDGET: {MAX_TOOL_FETCHES} total calls for get_node_summary + get_node_content.
get_subtree and search_nodes are free and unlimited.
"""


# ==========================================
# AGENTIC LOOP
# ==========================================

def run_agent(task_row: dict, audit: Audit) -> str:
    instruction      = task_row["instruction"]
    vault_id         = task_row["vault_id"]
    context_node_ids = task_row["context_node_ids"]
    if isinstance(context_node_ids, str):
        context_node_ids = json.loads(context_node_ids)

    _log("Fetching vault tree...")
    tree = svc_get_tree(vault_id)
    if not tree:
        raise RuntimeError("Could not fetch vault tree.")

    overview_node = None
    if context_node_ids:
        root_stub = find_root_for_node(context_node_ids[0], tree)
        if root_stub:
            _log(f"Overview: '{root_stub.get('title')}' ({root_stub['id']})")
            overview_node = svc_get_node(vault_id, root_stub["id"])

    context_lines =[]
    for node_id in context_node_ids:
        node = svc_get_node_summary(vault_id, node_id)
        if node and "error" in node:
            context_lines.append(f"- {node_id} [ERROR: {node['error']}]")
        elif node:
            context_lines.append(
                f"- UUID: {node_id}\n"
                f"  Title: {node.get('title')}\n"
                f"  Summary: {node.get('ai_summary') or '(none)'}"
            )
    context_nodes_block = "\n".join(context_lines) or "(none provided)"

    system_prompt = build_system_prompt(instruction, context_nodes_block, overview_node)

    client = OpenAI(
        api_key=GPT_TOKEN,
        http_client=httpx.Client(verify=False),
    )

    input_list =[
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Please carry out the task now."},
    ]

    loop_count       = 0
    fetch_call_count = 0
    no_tool_streak   = 0
    seen_uuids       = set()
    finish_summary   = None

    while True:
        loop_count += 1
        if loop_count > MAX_LOOP_TURNS:
            raise RuntimeError(f"Agent exceeded {MAX_LOOP_TURNS} turns without finishing.")

        _log(f"\n---[Turn {loop_count}/{MAX_LOOP_TURNS}]---")
        audit.begin_turn(loop_count)
        t0 = time.time()

        try:
            response = client.responses.create(
                model=GPT_MODEL,
                tools=TOOLS,
                input=input_list,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e

        _log(f"  ✓ {time.time() - t0:.1f}s | {len(response.output)} output item(s)")
        input_list += response.output
        tool_executed = False

        for item in response.output:
            if getattr(item, "type", None) != "function_call":
                continue

            tool_executed = True
            name = item.name

            try:
                args = json.loads(item.arguments)
            except json.JSONDecodeError as e:
                msg = f"Error: malformed JSON — {e}"
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, {"raw_args": item.arguments}, "error", msg)
                continue

            _log(f"  🔧 {name}({str(args)[:160]})")

            # ── get_subtree ───────────────────────────────────────────
            if name == "get_subtree":
                result = get_subtree_summary(vault_id, args["node_id"])
                _append(input_list, item.call_id, _fmt(result))
                audit.record_tool(name, args, "error" if "error" in result else "ok",
                                  result.get("error", "Fetched subtree"))

            # ── get_node_summary ──────────────────────────────────────
            elif name == "get_node_summary":
                node_id = args["node_id"]
                if is_read_locked(vault_id, node_id):
                    msg = "Node is private (bxs-no-entry) — content is not accessible to the agent."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue
                err = _check_budget(node_id, seen_uuids, fetch_call_count)
                if err:
                    _append(input_list, item.call_id, err)
                    audit.record_tool(name, args, "budget", err)
                else:
                    seen_uuids.add(node_id)
                    fetch_call_count += 1
                    node = svc_get_node_summary(vault_id, node_id)
                    is_err = node and "error" in node
                    _append(input_list, item.call_id,
                            _fmt(node) if not is_err else f"Error: {node['error']}")
                    audit.record_tool(name, args, "error" if is_err else "ok",
                                      (node or {}).get("error", "Fetched summary"))

            # ── get_node_content ──────────────────────────────────────
            elif name == "get_node_content":
                node_id = args["node_id"]
                if is_read_locked(vault_id, node_id):
                    msg = "Node is private (bxs-no-entry) — content is not accessible to the agent."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue
                err = _check_budget(node_id, seen_uuids, fetch_call_count)
                if err:
                    _append(input_list, item.call_id, err)
                    audit.record_tool(name, args, "budget", err)
                else:
                    seen_uuids.add(node_id)
                    fetch_call_count += 1
                    node = svc_get_node(vault_id, node_id)
                    _append(input_list, item.call_id,
                            _fmt(node) if node else f"Error: node {node_id} not found")
                    audit.record_tool(name, args, "ok" if node else "error",
                                      "Fetched content" if node else "Not found")

            # ── search_nodes ──────────────────────────────────────────
            elif name == "search_nodes":
                limit  = min(int(args.get("limit", 10)), 20)
                result = svc_search(vault_id, args.get("query", ""), limit)
                _append(input_list, item.call_id, _fmt(result))
                audit.record_tool(name, args, "ok",
                                  f"Found {result.get('count', 0)} results")

            # ── write_node ────────────────────────────────────────────
            elif name == "write_node":
                node_id    = args["node_id"]
                content    = args["content"].strip()
                ai_summary = args["ai_summary"].strip()

                err = _validate_summary(ai_summary)
                if err:
                    _append(input_list, item.call_id, f"Validation error: {err}")
                    audit.record_tool(name, args, "error", err)
                    continue

                if is_blacklisted(vault_id, node_id):
                    res2 = svc_update_summary(vault_id, node_id, ai_summary)
                    if not res2["ok"]:
                        _append(input_list, item.call_id, f"Error writing summary to protected node: {res2['error']}")
                        audit.record_tool(name, args, "error", res2["error"])
                        continue
                    
                    msg = "Node is protected (bxs-lock-alt) — content modification ignored, but AI summary was updated."
                    _log(f"  ✅ write_node (summary only): {node_id}")
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", msg)
                    audit.record_write("write_node_summary_only", node_id, {"summary": ai_summary})
                    continue

                res = svc_update_node(vault_id, node_id, content=content)
                if not res["ok"]:
                    _append(input_list, item.call_id, f"Error writing content: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])
                    continue

                res2 = svc_update_summary(vault_id, node_id, ai_summary)
                if not res2["ok"]:
                    _append(input_list, item.call_id,
                            f"Content written but summary failed: {res2['error']}")
                    audit.record_tool(name, args, "error", res2["error"])
                    continue

                _log(f"  ✅ write_node: {node_id}")
                msg = f"Node {node_id} written successfully."
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, args, "ok", msg)
                audit.record_write("write_node", node_id,
                                   {"content_length": len(content), "summary": ai_summary})

            # ── patch_node ────────────────────────────────────────────
            elif name == "patch_node":
                node_id    = args["node_id"]
                patches    = args["patches"]
                ai_summary = args.get("ai_summary")

                if is_blacklisted(vault_id, node_id):
                    msg = "Node is protected (bxs-lock-alt) — content cannot be modified."
                    if ai_summary:
                        err = _validate_summary(ai_summary)
                        if err:
                            _append(input_list, item.call_id, f"Content protected, and summary validation error: {err}")
                            audit.record_tool(name, args, "error", err)
                            continue
                        
                        res2 = svc_update_summary(vault_id, node_id, ai_summary)
                        if not res2["ok"]:
                            _append(input_list, item.call_id, f"Error writing summary to protected node: {res2['error']}")
                            audit.record_tool(name, args, "error", res2["error"])
                            continue
                        
                        msg += " However, AI summary was updated."
                        _log(f"  ✅ patch_node (summary only): {node_id}")
                        _append(input_list, item.call_id, msg)
                        audit.record_tool(name, args, "ok", msg)
                        audit.record_write("patch_node_summary_only", node_id, {"summary": ai_summary})
                        continue

                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue

                node = svc_get_node(vault_id, node_id)
                if not node:
                    msg = f"Cannot fetch node to patch: {node_id} not found"
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "error", msg)
                    continue

                current     = node.get("content") or ""
                patch_failed = False
                for i, patch in enumerate(patches):
                    if patch["find"] not in current:
                        msg = f"Patch {i} failed: find text not found verbatim."
                        _append(input_list, item.call_id, msg)
                        audit.record_tool(name, args, "error", msg)
                        patch_failed = True
                        break
                    current = current.replace(patch["find"], patch["replace"], 1)

                if patch_failed:
                    continue

                res = svc_update_node(vault_id, node_id, content=current)
                if not res["ok"]:
                    _append(input_list, item.call_id,
                            f"Error writing patched content: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])
                    continue

                if ai_summary:
                    err = _validate_summary(ai_summary)
                    if err:
                        _append(input_list, item.call_id,
                                f"Content patched but summary invalid: {err}")
                        audit.record_tool(name, args, "error", err)
                        continue
                    svc_update_summary(vault_id, node_id, ai_summary)

                _log(f"  ✅ patch_node: {node_id} ({len(patches)} patch(es))")
                msg = f"Node {node_id} patched ({len(patches)} patch(es))."
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, args, "ok", msg)
                audit.record_write("patch_node", node_id,
                                   {"num_patches": len(patches),
                                    "summary_updated": bool(ai_summary)})

            # ── move_node ─────────────────────────────────────────────
            elif name == "move_node":
                node_id       = args["node_id"]
                new_parent_id = args["new_parent_id"]
                res = svc_move_node(vault_id, node_id, new_parent_id)
                if res["ok"]:
                    _log(f"  ✅ move_node: {node_id} → {new_parent_id}")
                    msg = f"Node {node_id} moved to parent {new_parent_id}."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", "Moved successfully.")
                    audit.record_write("move_node", node_id,
                                       {"new_parent_id": new_parent_id})
                else:
                    _append(input_list, item.call_id, f"Move failed: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])

            # ── create_node ───────────────────────────────────────────
            elif name == "create_node":
                title      = args["title"]
                parent_id  = args["parent_id"]
                content    = args.get("content", "")
                ai_summary = args.get("ai_summary", "")

                if is_blacklisted(vault_id, parent_id):
                    msg = f"Parent {parent_id} is protected — cannot create children."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue

                err = _validate_summary(ai_summary)
                if err:
                    _append(input_list, item.call_id, f"Validation error: {err}")
                    audit.record_tool(name, args, "error", err)
                    continue

                res = svc_create_node(vault_id, title, parent_id, content, ai_summary)
                if res["ok"]:
                    new_id = res["node"].get("id", "unknown")
                    _log(f"  ✅ create_node: '{title}' ({new_id})")
                    msg = f"Created '{title}' with UUID {new_id} under {parent_id}."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", msg)
                    audit.record_write("create_node", new_id,
                                       {"parent_id": parent_id, "title": title})
                else:
                    _append(input_list, item.call_id, f"Create failed: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])

            # ── finish ────────────────────────────────────────────────
            elif name == "finish":
                finish_summary = args.get("summary", "Task completed.")
                _log(f"  ✅ finish: {finish_summary}")
                _append(input_list, item.call_id, "Acknowledged.")
                audit.record_tool(name, args, "ok", finish_summary)
                break

            else:
                msg = f"Unknown tool '{name}'."
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, args, "error", msg)

        if finish_summary is not None:
            audit.end_turn(time.time() - t0)
            break

        if not tool_executed:
            no_tool_streak += 1
            _log(f"  ⚠ No tool called (streak: {no_tool_streak})")
            if no_tool_streak >= 3:
                raise RuntimeError("Agent stuck: 3 consecutive turns with no tool calls.")
            input_list.append({"role": "user", "content": (
                "You must call a tool. Continue working or call finish() if all changes are done. "
                f"Remaining fetch budget: {MAX_TOOL_FETCHES - fetch_call_count}."
            )})
        else:
            no_tool_streak = 0

        audit.end_turn(time.time() - t0)

    _log(f"\nAgent done: {loop_count} turn(s), {fetch_call_count} fetch(es).")
    return finish_summary or "Completed."


# ==========================================
# HELPERS
# ==========================================

def _append(input_list: list, call_id: str, output: str):
    input_list.append({
        "type":    "function_call_output",
        "call_id": call_id,
        "output":  output,
    })


def _fmt(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) \
        if isinstance(data, (dict, list)) else str(data)


def _check_budget(node_id: str, seen: set, count: int) -> str | None:
    if node_id in seen:
        return f"Already fetched {node_id} — use your prior context."
    if count >= MAX_TOOL_FETCHES:
        return f"Fetch budget exhausted ({MAX_TOOL_FETCHES} calls). Finish with what you have."
    return None


def _validate_summary(ai_summary: str) -> str | None:
    if not ai_summary:
        return "ai_summary is empty."
    bullets = [ln for ln in ai_summary.splitlines() if ln.startswith("- ")]
    if len(bullets) != 3:
        return f"ai_summary has {len(bullets)} bullet(s); must be exactly 3 lines starting with '- '."
    return None


# ==========================================
# POLLING LOOP
# ==========================================

def run_loop():
    _log("=" * 60)
    _log("Nexidion Task Runner")
    _log(f"Agent user ID : {AGENT_USER_ID} (default-llm)")
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

        task_id = task_row["id"]
        _log(f"Claimed task : {task_id}")
        _log(f"Instruction  : {task_row['instruction']}")

        # Run the agent inside the Flask app context so SQLAlchemy sessions work.
        with flask_app.app_context():
            # Build a minimal task-like object for Audit
            class _TaskObj:
                id               = task_row["id"]
                vault_id         = task_row["vault_id"]
                instruction      = task_row["instruction"]
                context_node_ids = task_row["context_node_ids"]
                created_at       = task_row["created_at"]

            audit = Audit(_TaskObj())
            try:
                summary = run_agent(task_row, audit)
                # Save success summary and the atomic writes to the DB
                mark_task_raw(conn, task_id, "completed", summary=summary, operations=audit.writes)
                audit.save("completed", summary)
                _log(f"✅ {summary}")
            except Exception as e:
                _log(f"✗ Task failed: {e}")
                # Save failure summary and any operations completed before the crash
                mark_task_raw(conn, task_id, "failed", summary=str(e), operations=audit.writes)
                audit.save("failed", str(e))

        time.sleep(POLL_INTERVAL)


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    run_loop()