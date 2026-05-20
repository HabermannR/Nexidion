import os
import sys
import time
import argparse
import json

from openai import OpenAI
import httpx

# Nexidion specific imports
from backend.app import create_app
from backend.models import User, UserType
from agent.extractor import extract_pdf_smart
from agent.svc import svc_create_node


# --- LOGGING HELPER ---
def _ts(): return time.strftime("%H:%M:%S")


def _inf(msg): print(f"[{_ts()}] ℹ️  {msg}", flush=True)


def _ok(msg):  print(f"[{_ts()}] ✅  {msg}", flush=True)


def _err(msg): print(f"[{_ts()}] ❌  {msg}", flush=True)


def _banner(msg): print(f"\n{'=' * 60}\n{msg}\n{'=' * 60}", flush=True)


# ---------------------------------------------------------------------------
# CONFIGURATION & LLM CLIENT SETUP (Matching loop.py)
# ---------------------------------------------------------------------------
GPT_TOKEN = os.environ.get("OPENAI_API_KEY")
GPT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL")
LOCAL_LLM_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "not-needed")


def get_llm_client() -> OpenAI:
    if not GPT_TOKEN and not LOCAL_LLM_URL:
        _err("Neither OPENAI_API_KEY nor LOCAL_LLM_URL is set in .env")
        sys.exit(1)

    tls_verify = not bool(LOCAL_LLM_URL)
    client_kwargs = {
        "api_key": GPT_TOKEN if GPT_TOKEN else LOCAL_LLM_API_KEY,
        "http_client": httpx.Client(verify=tls_verify),
        "timeout": 600.0,
    }
    if LOCAL_LLM_URL:
        client_kwargs["base_url"] = LOCAL_LLM_URL

    return OpenAI(**client_kwargs)


def call_llm(client: OpenAI, messages: list, response_schema: dict) -> dict:
    """Execute LLM call using Nexidion's configuration and enforce JSON Schema."""
    try:
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=messages,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": response_schema
            }
        )
        raw_content = response.choices[0].message.content
        return json.loads(raw_content)
    except Exception as e:
        _err(f"LLM API Error: {e}")
        raise


# ---------------------------------------------------------------------------
# PASS 1: PAGE-BY-PAGE EXTRACTION
# ---------------------------------------------------------------------------
PASS_1_SYSTEM = """\
You are a technical writer producing a single, unified description of a presentation slide.
Your output must not repeat the same information twice.
Synthesise the visual layout, any diagrams or flows, and the text into one coherent paragraph or structured summary.
Do not transcribe bullet points verbatim — paraphrase and integrate them into your description."""

PASS_1_USER = """\
Analyze this presentation slide. Provide a unified description paragraph and a concise summary list.

OCR text extracted from the slide (use as reference, not as copy-paste source):
{ocr_text}"""

PASS_1_SCHEMA = {
    "name": "page_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Unified descriptive paragraph of this page's contents (text and visuals)."
            },
            "summary_bullets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of strings, each a concise takeaway from the page."
            }
        },
        "required": ["description", "summary_bullets"],
        "additionalProperties": False
    }
}


def pass_1_describe_pages(client: OpenAI, visual_doc) -> list:
    _banner("PASS 1: PAGE EXTRACTION (VISION HEURISTIC APPLIED)")
    descriptions = []

    for page in visual_doc.pages:
        _inf(f"Processing Page {page.page_num} / {visual_doc.page_count}...")

        has_img = bool(page.image_base64)
        _inf(f"  > Modality: {'🖼️ Vision + Text' if has_img else '📝 Text Only'}")

        content_array = [
            {
                "type": "text",
                "text": PASS_1_USER.format(ocr_text=page.text or "<none>")
            }
        ]

        if has_img:
            content_array.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{page.image_base64}"}
            })

        messages = [
            {"role": "system", "content": PASS_1_SYSTEM},
            {"role": "user", "content": content_array}
        ]

        data = call_llm(client, messages, PASS_1_SCHEMA)

        descriptions.append({
            "page_num": page.page_num,
            "description": data.get("description", ""),
            "summary": data.get("summary_bullets", []),
        })
        _ok(f"  > Summary captured ({len(data.get('summary_bullets', []))} bullets).")

    return descriptions


# ---------------------------------------------------------------------------
# PASS 2: CHAPTER CLUSTERING
# ---------------------------------------------------------------------------
PASS_2_SYSTEM = """\
You are a structural editor. Analyze the provided slide summaries.
Your job is to drop useless slides (Title pages, Agenda, Q&A) and group the rest into logical chapters."""

PASS_2_USER = """\
Here are the slide summaries. Process them and group the valid content slides into chapters:

{combined_text}"""

PASS_2_SCHEMA = {
    "name": "chapter_clustering",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "chapters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Descriptive title for the chapter"},
                        "ai_summary_bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3 to 5 key bullet points summarizing this chapter"
                        },
                        "included_pages": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Page numbers belonging to this chapter"
                        }
                    },
                    "required": ["title", "ai_summary_bullets", "included_pages"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["chapters"],
        "additionalProperties": False
    }
}


def pass_2_cluster_chapters(client: OpenAI, descriptions: list) -> list:
    _banner("PASS 2: STRUCTURAL CLUSTERING")

    combined_text = "\n\n".join(
        f"--- PAGE {d['page_num']} ---\n" +
        "\n".join(f"- {s}" for s in d["summary"])
        for d in descriptions
    )

    messages = [
        {"role": "system", "content": PASS_2_SYSTEM},
        {"role": "user", "content": PASS_2_USER.format(combined_text=combined_text)}
    ]

    _inf("Asking LLM to cluster chapters...")
    data = call_llm(client, messages, PASS_2_SCHEMA)
    return data.get("chapters", [])


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------
def ingest_pdf(pdf_path: str, vault_id: int, parent_node_id: str):
    app = create_app()
    with app.app_context():
        # 1. Resolve Agent User
        agent = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
        if not agent:
            _err("No LLM agent user found. Run 'flask create-llm-agent' first.")
            sys.exit(1)
        agent_id = agent.id

        client = get_llm_client()
        filename = os.path.basename(pdf_path)

        # 2. Extract Document
        _banner(f"EXTRACTING: {filename}")
        visual_doc = extract_pdf_smart(pdf_path, dpi=100)
        _ok(f"Smart Extraction complete — {visual_doc.page_count} pages.")

        # 3. Process LLM Pipeline
        page_descriptions = pass_1_describe_pages(client, visual_doc)
        chapters = pass_2_cluster_chapters(client, page_descriptions)

        # Lookup map for writing the final markdown content
        desc_map = {d["page_num"]: d["description"] for d in page_descriptions}

        # 4. Create Nodes in Nexidion
        _banner("PASS 3: KNOWLEDGE GRAPH CREATION")

        # Determine actual parent_id (root is empty string in node_service)
        actual_parent_id = parent_node_id if parent_node_id else ""

        # Create Parent Node
        _inf(f"Creating Parent Node: '{filename}'")
        parent_res = svc_create_node(
            vault_id=vault_id,
            title=filename,
            parent_id=actual_parent_id,
            agent_user_id=agent_id,
            content=f"Automatically ingested document: **{filename}**.\n\nContains {len(chapters)} chapters extracted over {visual_doc.page_count} pages.",
            ai_summary="- Document ingested automatically\n- Contains clustered chapters\n- See child nodes for details"
        )

        if not parent_res["ok"]:
            _err(f"Failed to create parent node: {parent_res['error']}")
            sys.exit(1)

        doc_node_id = parent_res["node"]["id"]
        _ok(f"Parent Node created: {doc_node_id}")

        # Create Child Nodes
        for idx, chapter in enumerate(chapters, 1):
            title = chapter.get("title", f"Chapter {idx}")
            pages = chapter.get("included_pages", [])
            bullets = chapter.get("ai_summary_bullets", [])

            # Formatting ai_summary (list to markdown bullet string)
            ai_summary = "\n".join(f"- {b}" for b in bullets)
            if not ai_summary.strip():
                ai_summary = "- No summary provided"

            _inf(f"Creating Child Node: '{title}' (Pages: {pages})")

            # Building rich Markdown content for the node
            content_md = f"# {title}\n\n## Chapter Summary\n{ai_summary}\n\n## Page Details\n"
            for p_num in pages:
                if p_num in desc_map:
                    content_md += f"\n### Page {p_num}\n{desc_map[p_num]}\n"

            child_res = svc_create_node(
                vault_id=vault_id,
                title=title,
                parent_id=doc_node_id,
                agent_user_id=agent_id,
                content=content_md.strip(),
                ai_summary=ai_summary
            )

            if child_res["ok"]:
                _ok(f"  -> Created: {child_res['node']['id']}")
            else:
                _err(f"  -> Failed: {child_res['error']}")

        _banner("INGESTION COMPLETE!")
        _inf(f"Document available in Vault {vault_id} under node {doc_node_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF into Nexidion as a node tree.")
    parser.add_argument("pdf_path", help="Path to the PDF file on disk.")
    parser.add_argument("--vault", type=int, required=True, help="Vault ID to ingest into.")
    parser.add_argument("--parent", type=str, default="",
                        help="Optional UUID of the parent node to attach this document to. If omitted, attaches to root.")

    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"File not found: {args.pdf_path}")
        sys.exit(1)

    ingest_pdf(args.pdf_path, args.vault, args.parent)