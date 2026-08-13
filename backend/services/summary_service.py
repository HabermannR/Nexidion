from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from backend.models import db, Node, SummaryArtifact

VALID_PROVIDERS = {"manual", "local", "openai", "openrouter"}
VALID_VISUAL_MODES = {"off", "auto", "all"}


def content_hash(node: Node) -> str:
    version = node.current_version_object
    material = f"{version.title if version else ''}\0{version.content if version else ''}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def start_summary(node: Node, provider: str, model: str | None,
                  requested_by_id: int | None, executed_by_id: int | None,
                  visual_mode: str = "off", prompt_version: str = "summary-v1") -> SummaryArtifact:
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unsupported summary provider: {provider}")
    if visual_mode not in VALID_VISUAL_MODES:
        raise ValueError(f"Unsupported visual mode: {visual_mode}")
    artifact = SummaryArtifact(
        node_id=node.id, source_content_hash=content_hash(node), provider=provider,
        model=model, requested_by_id=requested_by_id, executed_by_id=executed_by_id,
        visual_mode=visual_mode, prompt_version=prompt_version, status="pending",
    )
    db.session.add(artifact)
    return artifact


def request_summary(node: Node, provider: str, model: str | None,
                    requested_by_id: int, executed_by_id: int | None = None,
                    visual_mode: str = "off") -> SummaryArtifact:
    if provider == "manual":
        raise ValueError("Manual summaries must include their summary text.")
    existing = SummaryArtifact.query.filter_by(
        node_id=node.id, source_content_hash=content_hash(node), provider=provider,
        model=model, visual_mode=visual_mode, status="pending",
    ).first()
    if existing:
        return existing
    artifact = start_summary(node, provider, model, requested_by_id, executed_by_id, visual_mode)
    db.session.commit()
    return artifact


def complete_summary(artifact: SummaryArtifact, summary: str, used_vision: bool = False) -> None:
    node = db.session.get(Node, artifact.node_id)
    if not node:
        raise ValueError("Summary target node no longer exists.")
    artifact.summary = summary
    artifact.used_vision = used_vision
    artifact.status = "completed"
    artifact.completed_at = datetime.now(timezone.utc)
    node.ai_summary = summary
    node.summary_is_current = artifact.source_content_hash == content_hash(node)


def fail_summary(artifact: SummaryArtifact, error: str) -> None:
    artifact.status = "failed"
    artifact.error = error
    artifact.completed_at = datetime.now(timezone.utc)
