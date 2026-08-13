from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone

import pymupdf
from backend.models import db, CurationJob, SourceArtifact, NodeSourceLink
from backend.services import node_service
from backend.services.llm_provider import client_and_model


PROMPT_VERSION = "pdf-curation-v4"
SYSTEM_PROMPT = """You curate a PDF into durable knowledge nodes. Return strict JSON:
{"nodes":[{"title":"...","content":"Markdown","page_from":1,"page_to":2,"parent_index":null}]}
Create a useful, non-redundant hierarchy of standalone synthesis nodes. Use broad,
meaningful topic nodes as parents and focused knowledge nodes as their children. The
first node must be the single document-level root and contain a useful overview of the
whole source. It has parent_index null. Every other node must be a descendant of that
root and therefore have a parent_index. Aim for 3-7 direct children per organizational
parent when the source has enough material. Emit every parent before its children.
parent_index is a zero-based reference to an earlier node in the array. Parent nodes
must contain useful standalone content, not merely headings.

Preserve technical facts and terminology. Cite page ranges in each node. Do not add
facts that are absent from the supplied source.

Write titles and content in the predominant language of the source. Every non-empty
source page must be represented by at least one node's inclusive page_from/page_to
range. Do not omit appendices, forms, or closing pages: summarize their purpose when
they contain little narrative text. Return JSON only."""


def serialize_curation_job(job: CurationJob) -> dict:
    return {"id": job.id, "artifact_id": job.artifact_id, "vault_id": job.vault_id,
            "parent_id": job.parent_id, "mode": job.mode, "provider": job.provider,
            "model": job.model, "visual_mode": job.visual_mode, "status": job.status,
            "error": job.error, "result": job.result_json or {},
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None}


def _client(job):
    return client_and_model(job.provider, job.model)


def _user_content(job, artifact):
    pages = artifact.extracted_json.get('pages', [])
    text = "\n\n".join(f"--- PAGE {p['page']} ---\n{p['markdown'][:8000]}" for p in pages)[:120000]
    content = [{"type": "text", "text": text}]
    if job.visual_mode != 'off' and artifact.payload:
        with pymupdf.open(stream=artifact.payload, filetype='pdf') as pdf:
            if job.visual_mode == 'all':
                page_numbers = range(pdf.page_count)
            else:
                visual_pages = [i for i, page in enumerate(pdf) if page.get_images(full=True)]
                page_numbers = visual_pages or ([0] if pdf.page_count else [])
            for page_number in page_numbers:
                pix = pdf[page_number].get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
                encoded = base64.b64encode(pix.tobytes('jpeg')).decode()
                content.append({"type": "text", "text": f"Rendered source page {page_number + 1}:"})
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
    return content


def _required_pages(artifact) -> set[int]:
    return {int(page['page']) for page in artifact.extracted_json.get('pages', [])
            if str(page.get('markdown', '')).strip()}


def _validate_nodes(nodes, required_pages: set[int]) -> list[str]:
    if not isinstance(nodes, list) or not nodes:
        return ['The response must contain a non-empty nodes array.']
    errors = []
    covered = set()
    child_counts = {}
    root_indexes = []
    last_page = max(required_pages, default=1)
    for index, entry in enumerate(nodes):
        if not isinstance(entry, dict):
            errors.append(f'Node {index} is not an object.')
            continue
        if not str(entry.get('title', '')).strip() or not str(entry.get('content', '')).strip():
            errors.append(f'Node {index} requires a non-empty title and content.')
        try:
            page_from = int(entry.get('page_from'))
            page_to = int(entry.get('page_to'))
        except (TypeError, ValueError):
            errors.append(f'Node {index} has invalid page_from/page_to values.')
            continue
        if page_from < 1 or page_to < page_from or page_to > last_page:
            errors.append(f'Node {index} has an out-of-range page range {page_from}-{page_to}.')
            continue
        covered.update(range(page_from, page_to + 1))
        parent_index = entry.get('parent_index')
        if parent_index is None:
            root_indexes.append(index)
        if parent_index is not None and (not isinstance(parent_index, int) or parent_index < 0 or parent_index >= index):
            errors.append(f'Node {index} parent_index must reference an earlier node or be null.')
        elif parent_index is not None:
            child_counts[parent_index] = child_counts.get(parent_index, 0) + 1
    if root_indexes != [0]:
        errors.append('Exactly node 0 must be the single document-level root; every other node needs a parent_index.')
    if len(nodes) >= 4 and not child_counts:
        errors.append('The response is entirely flat; organize focused nodes under the document root.')
    oversized = sorted(index for index, count in child_counts.items() if count > 7)
    if oversized:
        errors.append('Parent nodes exceed the target of 7 direct children: ' +
                      ', '.join(map(str, oversized)) + '.')
    missing = sorted(required_pages - covered)
    if missing:
        errors.append(f'No node covers source pages: {", ".join(map(str, missing))}.')
    return errors


def _request_nodes(client, model, job, artifact):
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_content(job, artifact)}]
    required_pages = _required_pages(artifact)
    for attempt in range(2):
        response = client.chat.completions.create(model=model, temperature=0.2,
            messages=messages, response_format={"type": "json_object"})
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
            nodes = data.get('nodes')
            errors = _validate_nodes(nodes, required_pages)
        except (json.JSONDecodeError, AttributeError) as exc:
            nodes, errors = None, [f'Invalid JSON response: {exc}.']
        if not errors:
            return nodes
        if attempt == 0:
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Repair the JSON response. " + " ".join(errors) +
                 " Preserve the predominant source language and return the complete JSON object only."},
            ])
            continue
        raise ValueError('The model returned invalid curation nodes after one repair attempt: ' + ' '.join(errors))


def process_curation_job(job: CurationJob):
    artifact = db.session.get(SourceArtifact, job.artifact_id)
    if not artifact:
        raise ValueError('Source artifact no longer exists.')
    client, model = _client(job)
    nodes = _request_nodes(client, model, job, artifact)
    created = []
    created_node_ids = []
    for entry in nodes:
        title = str(entry.get('title', '')).strip()
        content = str(entry.get('content', '')).strip()
        if not title or not content:
            continue
        parent_index = entry.get('parent_index')
        generated_parent_id = job.parent_id
        if isinstance(parent_index, int) and 0 <= parent_index < len(created_node_ids):
            generated_parent_id = created_node_ids[parent_index]
        node = node_service.create_node(title, content, generated_parent_id, job.vault_id, job.executed_by_id)
        created_node_ids.append(node.id)
        node.content_kind = 'ai_synthesis'
        node.authority = 'derived'
        node.metadata_json = {"curation_job_id": job.id, "source_artifact_id": artifact.id,
                              "source_content_hash": artifact.content_hash,
                              "provider": job.provider, "model": model,
                              "prompt_version": job.prompt_version, "visual_mode": job.visual_mode}
        page_from = max(1, int(entry.get('page_from') or 1))
        page_to = max(page_from, int(entry.get('page_to') or page_from))
        db.session.add(NodeSourceLink(node_id=node.id, artifact_id=artifact.id,
            curation_job_id=job.id, page_from=page_from, page_to=page_to,
            source_content_hash=artifact.content_hash, is_stale=False))
        created.append({"node_id": node.id, "title": title, "page_from": page_from, "page_to": page_to})
    if not created:
        raise ValueError('The model returned no valid curation nodes.')
    job.model = model
    job.prompt_version = PROMPT_VERSION
    job.status = 'completed'
    job.result_json = {"nodes": created, "count": len(created)}
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()


def fail_curation_job(job, error):
    job.status = 'failed'
    job.error = str(error)
    job.completed_at = datetime.now(timezone.utc)
    db.session.commit()
