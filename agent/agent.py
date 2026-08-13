"""
agent/agent.py
=======================
Agentic loop: builds the system prompt, drives the OpenAI Responses API,
dispatches tool calls, and returns a finish summary.

Constants (MAX_LOOP_TURNS, MAX_TOOL_FETCHES, BLACKLIST_ICON, READ_LOCK_ICON,
GPT_TOKEN, GPT_MODEL, LOCAL_LLM_URL, LOCAL_LLM_API_KEY) are imported from
loop.py so there is exactly one definition of each.
"""

import json
import os
import signal
import time
from contextlib import contextmanager
from functools import partial

import httpx
from openai import OpenAI

from agent.helpers import (
    _append,
    _check_budget,
    _fmt,
    _validate_summary,
    find_root_for_node,
    get_children_from_tree,
    get_subtree_summary,
    is_blacklisted,
    is_read_locked,
)
from agent.svc import (
    svc_create_node,
    svc_get_node,
    svc_get_node_summary,
    svc_get_tree,
    svc_move_node,
    svc_search,
    svc_update_node,
    svc_update_summary,
)


class TurnDeadlineExceeded(TimeoutError):
    pass


@contextmanager
def _wall_clock_deadline(seconds):
    """Interrupt a turn even when an HTTP stream keeps its read timeout alive."""
    if not seconds or not hasattr(signal, "setitimer"):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TurnDeadlineExceeded(f"LLM turn exceeded hard deadline of {seconds}s")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _stream_response(client, request, task_id, turn, debug_dir,
                     capture_payloads, hard_timeout_s, log_fn):
    """Consume Responses events observably and return the completed response."""
    trace = None
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        trace = open(os.path.join(debug_dir, f"{task_id}.jsonl"), "a", encoding="utf-8")
    started = time.monotonic()
    event_count = 0
    last_progress = started
    completed = None
    try:
        with _wall_clock_deadline(hard_timeout_s):
            stream = client.responses.create(**request, stream=True)
            # Lightweight test doubles may return an already-complete Response.
            if hasattr(stream, "output"):
                return stream, 0
            for event in stream:
                event_count += 1
                event_type = getattr(event, "type", "unknown")
                now = time.monotonic()
                if trace:
                    record = {
                        "elapsed_s": round(now - started, 3),
                        "turn": turn,
                        "event": event_type,
                    }
                    if capture_payloads:
                        record["payload"] = event.model_dump(mode="json")
                    trace.write(json.dumps(record, ensure_ascii=False) + "\n")
                    trace.flush()
                if now - last_progress >= 15:
                    log_fn(f"  … stream alive {now - started:.0f}s | {event_count} events | {event_type}")
                    last_progress = now
                if event_type == "response.completed":
                    completed = event.response
                elif event_type in ("response.failed", "response.incomplete"):
                    detail = getattr(event, "response", None)
                    raise RuntimeError(f"LLM stream ended with {event_type}: {detail}")
    finally:
        if trace:
            trace.close()
    if completed is None:
        raise RuntimeError("LLM stream closed without a completed response")
    return completed, event_count


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

TOOLS = [
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
            "required": ["node_id"],
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
                    "type": ["string", "null"],
                    "description": "Updated summary (3 bullets). Pass null to leave unchanged.",
                },
            },
            "required": ["node_id", "patches", "ai_summary"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "rename_node",
        "description": (
            "Change the title of an existing node without modifying its content. "
            "Use this when a node's title is inaccurate or needs to be more descriptive."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID of the node to rename."},
                "title":   {"type": "string", "description": "The new title for the node."},
            },
            "required": ["node_id", "title"],
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
            "required": ["title", "parent_id", "content", "ai_summary"],
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
            "required": ["summary"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def build_system_prompt(instruction: str, context_nodes_block: str,
                        overview_node: dict | None,
                        max_tool_fetches: int) -> str:
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
  WRITE : write_node, patch_node, rename_node, move_node, create_node
  DONE  : finish

HOW TO WORK:
- Start by reading the context nodes to understand the current state.
- Use get_subtree first on any node — it is free and immediately shows you the children.
- Prefer get_node_summary over get_node_content; only escalate when you need the full text.
- search_nodes is free — use it liberally to discover UUIDs of related nodes.
- Never invent or guess a UUID. Only use UUIDs returned by tools or provided in context.
- Apply changes as you go using the write tools — do not batch everything to the end.
- For bottom-up roll-up synthesis: leaves are read-only sources. Process only non-leaf nodes,
  deepest parent first and the selected root last. Use write_node on each parent to update both
  its coherent Markdown synthesis and its 3-bullet AI summary. Never write to a leaf.
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

FETCH BUDGET: {max_tool_fetches} total calls for get_node_summary + get_node_content.
get_subtree and search_nodes are free and unlimited.
"""


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agent(task_row: dict, audit,
              agent_user_id: int,
              gpt_token: str, gpt_model: str,
              local_llm_url: str | None, local_llm_api_key: str,
              max_loop_turns: int, max_tool_fetches: int,
              blacklist_icon: str, read_lock_icon: str,
              log_fn,
              record_full_text: bool = False,
              default_headers: dict | None = None,
              request_timeout_s: float = 1800,
              hard_turn_timeout_s: float = 1800,
              reasoning_effort: str | None = None,
              max_output_tokens: int | None = None,
              stream_debug_dir: str | None = None,
              capture_stream_payloads: bool = False) -> str:

    instruction      = task_row["instruction"]
    vault_id         = task_row["vault_id"]
    context_node_ids = task_row["context_node_ids"]
    if isinstance(context_node_ids, str):
        context_node_ids = json.loads(context_node_ids)

    # ------------------------------------------------------------------
    # Convenience partials — bind agent_user_id so call sites are clean
    # ------------------------------------------------------------------
    _svc_get_tree         = partial(svc_get_tree,         agent_user_id=agent_user_id, log_fn=log_fn)
    _svc_get_node         = partial(svc_get_node,         agent_user_id=agent_user_id)
    _svc_get_node_summary = partial(svc_get_node_summary, agent_user_id=agent_user_id)
    _svc_search           = partial(svc_search,           agent_user_id=agent_user_id)
    _svc_update_node      = partial(svc_update_node,      agent_user_id=agent_user_id)
    _svc_update_summary   = partial(svc_update_summary,   agent_user_id=agent_user_id)
    _svc_move_node        = partial(svc_move_node,        agent_user_id=agent_user_id)
    _svc_create_node      = partial(svc_create_node,      agent_user_id=agent_user_id)

    _is_read_locked     = partial(is_read_locked,     _svc_get_node, read_lock_icon)
    _is_blacklisted     = partial(is_blacklisted,     _svc_get_node, blacklist_icon, read_lock_icon)
    _get_subtree_summary = partial(get_subtree_summary, _svc_get_node_summary, _svc_get_tree, read_lock_icon)

    # ------------------------------------------------------------------
    # Build context for system prompt
    # ------------------------------------------------------------------
    log_fn("Fetching vault tree...")
    tree = _svc_get_tree(vault_id)
    if not tree:
        raise RuntimeError("Could not fetch vault tree.")

    overview_node = None
    if context_node_ids:
        root_stub = find_root_for_node(context_node_ids[0], tree)
        if root_stub:
            log_fn(f"Overview: '{root_stub.get('title')}' ({root_stub['id']})")
            try:
                overview_node = _svc_get_node(vault_id, root_stub["id"])
            except PermissionError:
                log_fn("Overview node is private; continuing without its content.")

    context_lines = []
    for node_id in context_node_ids:
        node = _svc_get_node_summary(vault_id, node_id)
        if node and "error" in node:
            context_lines.append(f"- {node_id} [ERROR: {node['error']}]")
        elif node:
            context_lines.append(
                f"- UUID: {node_id}\n"
                f"  Title: {node.get('title')}\n"
                f"  Summary: {node.get('ai_summary') or '(none)'}"
            )
    context_nodes_block = "\n".join(context_lines) or "(none provided)"

    system_prompt = build_system_prompt(
        instruction, context_nodes_block, overview_node, max_tool_fetches
    )

    # ------------------------------------------------------------------
    # OpenAI client
    # ------------------------------------------------------------------
    tls_verify = not bool(local_llm_url)
    client_kwargs = {
        "api_key": gpt_token if gpt_token else local_llm_api_key,
        "http_client": httpx.Client(verify=tls_verify),
        "timeout": request_timeout_s,
    }
    if local_llm_url:
        client_kwargs["base_url"] = local_llm_url
    if default_headers:
        client_kwargs["default_headers"] = default_headers

    client = OpenAI(**client_kwargs)

    # ------------------------------------------------------------------
    # Pre-flight: verify LLM is reachable before starting the loop
    # ------------------------------------------------------------------
    try:
        client.models.list()
    except Exception as e:
        raise RuntimeError(
            f"LLM access check failed — cannot reach the model endpoint: {e}"
        ) from e

    # Make the active endpoint explicit in the log. If LOCAL_LLM_URL is set the agent
    # talks to the local box and NEVER to OpenAI, even when OPENAI_API_KEY is present —
    # this line ensures that routing choice can never be silently misread again.
    log_fn(f"LLM endpoint  : {local_llm_url or 'https://api.openai.com/v1 (OpenAI)'}")
    log_fn(f"Model         : {gpt_model}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    input_list       = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Please carry out the task now."},
    ]
    loop_count       = 0
    fetch_call_count = 0
    no_tool_streak   = 0
    seen_uuids       = set()
    full_content_uuids = set()
    allowed_write_nodes = (set(task_row.get("allowed_write_node_ids") or [])
                           if task_row.get("allowed_write_node_ids") is not None else None)
    allowed_write_operations = (set(task_row.get("allowed_write_operations") or [])
                                if task_row.get("allowed_write_operations") is not None else None)
    finish_summary   = None

    while True:
        loop_count += 1
        if loop_count > max_loop_turns:
            raise RuntimeError(f"Agent exceeded {max_loop_turns} turns without finishing.")

        log_fn(f"\n---[Turn {loop_count}/{max_loop_turns}]---")
        audit.begin_turn(loop_count)
        t0 = time.time()

        request = dict(
                model=gpt_model,
                tools=TOOLS,
                input=input_list,
            )
        if reasoning_effort:
            request["reasoning"] = {"effort": reasoning_effort}
        if max_output_tokens:
            request["max_output_tokens"] = max_output_tokens
        try:
            response, stream_events = _stream_response(
                client, request, task_row.get("id", "unknown"), loop_count,
                stream_debug_dir, capture_stream_payloads,
                hard_turn_timeout_s, log_fn,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e

        log_fn(f"  ✓ {time.time() - t0:.1f}s | {stream_events} stream events | {len(response.output)} output item(s)")
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

            log_fn(f"  🔧 {name}({str(args)[:160]})")

            mutation_names = {"write_node", "patch_node", "rename_node", "move_node", "create_node"}
            if allowed_write_nodes is not None and name in mutation_names:
                target_id = args.get("node_id")
                if name not in allowed_write_operations or target_id not in allowed_write_nodes:
                    msg = (f"Write-scope policy rejected {name} for {target_id or '(no node_id)'}. "
                           f"Allowed operations: {sorted(allowed_write_operations)}; "
                           f"allowed node UUIDs: {sorted(allowed_write_nodes)}.")
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    log_fn(f"  ⛔ {msg}")
                    continue
                if name == "write_node":
                    child_ids = {child["id"] for child in get_children_from_tree(target_id, tree)}
                    required_full_content = child_ids | {target_id}
                    missing = sorted(required_full_content - full_content_uuids)
                    if missing:
                        msg = ("Evidence policy rejected write_node. Fetch full content with "
                               f"get_node_content for the active parent and every immediate child first. Missing: {missing}")
                        _append(input_list, item.call_id, msg)
                        audit.record_tool(name, args, "blocked", msg)
                        log_fn(f"  ⛔ {msg}")
                        continue

            # ── get_subtree ──────────────────────────────────────────────
            if name == "get_subtree":
                result = _get_subtree_summary(vault_id, args["node_id"])
                _append(input_list, item.call_id, _fmt(result))
                audit.record_tool(name, args, "error" if "error" in result else "ok",
                                  result.get("error", "Fetched subtree"))

            # ── get_node_summary ─────────────────────────────────────────
            elif name == "get_node_summary":
                node_id = args["node_id"]
                if _is_read_locked(vault_id, node_id):
                    msg = "Node is private (bxs-no-entry) — content is not accessible to the agent."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue
                err = _check_budget(node_id, seen_uuids, fetch_call_count, max_tool_fetches)
                if err:
                    _append(input_list, item.call_id, err)
                    audit.record_tool(name, args, "budget", err)
                else:
                    seen_uuids.add(node_id)
                    fetch_call_count += 1
                    node = _svc_get_node_summary(vault_id, node_id)
                    is_err = node and "error" in node
                    _append(input_list, item.call_id,
                            _fmt(node) if not is_err else f"Error: {node['error']}")
                    audit.record_tool(name, args, "error" if is_err else "ok",
                                      (node or {}).get("error", "Fetched summary"))

            # ── get_node_content ─────────────────────────────────────────
            elif name == "get_node_content":
                node_id = args["node_id"]
                if _is_read_locked(vault_id, node_id):
                    msg = "Node is private (bxs-no-entry) — content is not accessible to the agent."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue
                err = _check_budget(node_id, full_content_uuids, fetch_call_count, max_tool_fetches)
                if err:
                    _append(input_list, item.call_id, err)
                    audit.record_tool(name, args, "budget", err)
                else:
                    seen_uuids.add(node_id)
                    fetch_call_count += 1
                    node = _svc_get_node(vault_id, node_id)
                    if node:
                        full_content_uuids.add(node_id)
                    _append(input_list, item.call_id,
                            _fmt(node) if node else f"Error: node {node_id} not found")
                    audit.record_tool(name, args, "ok" if node else "error",
                                      "Fetched content" if node else "Not found")

            # ── search_nodes ─────────────────────────────────────────────
            elif name == "search_nodes":
                limit  = min(int(args.get("limit", 10)), 20)
                result = _svc_search(vault_id, args.get("query", ""), limit=limit)
                _append(input_list, item.call_id, _fmt(result))
                audit.record_tool(name, args, "ok",
                                  f"Found {result.get('count', 0)} results")

            # ── rename_node ──────────────────────────────────────────────
            elif name == "rename_node":
                node_id = args["node_id"]
                title   = args["title"].strip()
                if _is_blacklisted(vault_id, node_id):
                    msg = "Node is protected (bxs-lock-alt) — title cannot be modified."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue
                res = _svc_update_node(vault_id, node_id, title=title)
                if res["ok"]:
                    log_fn(f"  ✅ rename_node: {node_id} -> '{title}'")
                    msg = f"Node {node_id} renamed to '{title}'."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", msg)
                    audit.record_write("rename_node", node_id, {"title": title})
                else:
                    _append(input_list, item.call_id, f"Rename failed: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])

            # ── write_node ───────────────────────────────────────────────
            elif name == "write_node":
                node_id    = args["node_id"]
                content    = args["content"].strip()
                ai_summary = args["ai_summary"].strip()

                err = _validate_summary(ai_summary)
                if err:
                    _append(input_list, item.call_id, f"Validation error: {err}")
                    audit.record_tool(name, args, "error", err)
                    continue

                if _is_blacklisted(vault_id, node_id):
                    res2 = _svc_update_summary(vault_id, node_id, ai_summary=ai_summary)
                    if not res2["ok"]:
                        _append(input_list, item.call_id,
                                f"Error writing summary to protected node: {res2['error']}")
                        audit.record_tool(name, args, "error", res2["error"])
                        continue
                    msg = "Node is protected (bxs-lock-alt) — content modification ignored, but AI summary was updated."
                    log_fn(f"  ✅ write_node (summary only): {node_id}")
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", msg)
                    audit.record_write("write_node", node_id, {"ai_summary": ai_summary})
                    continue

                res = _svc_update_node(vault_id, node_id, content=content)
                if not res["ok"]:
                    _append(input_list, item.call_id, f"Error writing content: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])
                    continue

                res2 = _svc_update_summary(vault_id, node_id, ai_summary=ai_summary)
                if not res2["ok"]:
                    _append(input_list, item.call_id,
                            f"Content written but summary failed: {res2['error']}")
                    audit.record_tool(name, args, "error", res2["error"])
                    continue

                log_fn(f"  ✅ write_node: {node_id}")
                msg = f"Node {node_id} written successfully."
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, args, "ok", msg)
                detail = {"ai_summary": ai_summary}
                if record_full_text:
                    detail["content"] = content
                else:
                    detail["content_length"] = len(content)
                audit.record_write("write_node", node_id, detail)

            # ── patch_node ───────────────────────────────────────────────
            elif name == "patch_node":
                node_id    = args["node_id"]
                patches    = args["patches"]
                ai_summary = args.get("ai_summary")

                if _is_blacklisted(vault_id, node_id):
                    msg = "Node is protected (bxs-lock-alt) — content cannot be modified."
                    if ai_summary:
                        err = _validate_summary(ai_summary)
                        if err:
                            _append(input_list, item.call_id,
                                    f"Content protected, and summary validation error: {err}")
                            audit.record_tool(name, args, "error", err)
                            continue
                        res2 = _svc_update_summary(vault_id, node_id, ai_summary=ai_summary)
                        if not res2["ok"]:
                            _append(input_list, item.call_id,
                                    f"Error writing summary to protected node: {res2['error']}")
                            audit.record_tool(name, args, "error", res2["error"])
                            continue
                        msg += " However, AI summary was updated."
                        log_fn(f"  ✅ patch_node (summary only): {node_id}")
                        _append(input_list, item.call_id, msg)
                        audit.record_tool(name, args, "ok", msg)
                        audit.record_write("patch_node", node_id, {"ai_summary": ai_summary})
                        continue
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue

                node = _svc_get_node(vault_id, node_id)
                if not node:
                    msg = f"Cannot fetch node to patch: {node_id} not found"
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "error", msg)
                    continue

                current      = node.get("content") or ""
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

                res = _svc_update_node(vault_id, node_id, content=current)
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
                    _svc_update_summary(vault_id, node_id, ai_summary=ai_summary)

                log_fn(f"  ✅ patch_node: {node_id} ({len(patches)} patch(es))")
                msg = f"Node {node_id} patched ({len(patches)} patch(es))."
                _append(input_list, item.call_id, msg)
                audit.record_tool(name, args, "ok", msg)
                detail = {"ai_summary": ai_summary} if ai_summary else {}
                if record_full_text:
                    detail["content"] = current
                else:
                    detail["num_patches"] = len(patches)
                audit.record_write("patch_node", node_id, detail)

            # ── move_node ────────────────────────────────────────────────
            elif name == "move_node":
                node_id       = args["node_id"]
                new_parent_id = args["new_parent_id"]
                res = _svc_move_node(vault_id, node_id, new_parent_id)
                if res["ok"]:
                    log_fn(f"  ✅ move_node: {node_id} → {new_parent_id}")
                    msg = f"Node {node_id} moved to parent {new_parent_id}."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", "Moved successfully.")
                    audit.record_write("move_node", node_id,
                                       {"new_parent_id": new_parent_id})
                else:
                    _append(input_list, item.call_id, f"Move failed: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])

            # ── create_node ──────────────────────────────────────────────
            elif name == "create_node":
                title      = args["title"]
                parent_id  = args["parent_id"]
                content    = args.get("content", "")
                ai_summary = args.get("ai_summary", "")

                if _is_blacklisted(vault_id, parent_id):
                    msg = f"Parent {parent_id} is protected — cannot create children."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "blocked", msg)
                    continue

                err = _validate_summary(ai_summary)
                if err:
                    _append(input_list, item.call_id, f"Validation error: {err}")
                    audit.record_tool(name, args, "error", err)
                    continue

                res = _svc_create_node(vault_id, title, parent_id, content=content, ai_summary=ai_summary)
                if res["ok"]:
                    new_id = res["node"].get("id", "unknown")
                    log_fn(f"  ✅ create_node: '{title}' ({new_id})")
                    msg = f"Created '{title}' with UUID {new_id} under {parent_id}."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "ok", msg)
                    detail = {"parent_id": parent_id, "title": title}
                    if record_full_text:
                        detail["content"] = content
                        detail["ai_summary"] = ai_summary
                    audit.record_write("create_node", new_id, detail)
                else:
                    _append(input_list, item.call_id, f"Create failed: {res['error']}")
                    audit.record_tool(name, args, "error", res["error"])

            # ── finish ───────────────────────────────────────────────────
            elif name == "finish":
                raw_summary = args.get("summary", "").strip()
                if not raw_summary:
                    msg = "Validation error: finish() requires a non-empty 'summary'."
                    _append(input_list, item.call_id, msg)
                    audit.record_tool(name, args, "error", msg)
                    continue
                finish_summary = raw_summary
                log_fn(f"  ✅ finish: {finish_summary}")
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
            log_fn(f"  ⚠ No tool called (streak: {no_tool_streak})")
            if no_tool_streak >= 3:
                raise RuntimeError("Agent stuck: 3 consecutive turns with no tool calls.")
            input_list.append({"role": "user", "content": (
                "You must call a tool. Continue working or call finish() if all changes are done. "
                f"Remaining fetch budget: {max_tool_fetches - fetch_call_count}."
            )})
        else:
            no_tool_streak = 0

        audit.end_turn(time.time() - t0)

    log_fn(f"\nAgent done: {loop_count} turn(s), {fetch_call_count} fetch(es).")
    return finish_summary or "Completed."
