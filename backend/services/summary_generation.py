from __future__ import annotations

import os
from openai import OpenAI

from backend.models import SummaryArtifact, Node
from backend.services.summary_service import complete_summary, fail_summary

SYSTEM_PROMPT = """Create a concise, factual summary of the supplied Nexidion node.
Preserve important terminology, names, constraints, and conclusions. Do not invent
facts. Return only the summary in Markdown, normally 3-7 bullets."""


def generate_summary(artifact: SummaryArtifact, node: Node) -> str:
    if artifact.provider == "local":
        base_url = os.environ.get("LOCAL_LLM_URL")
        if not base_url:
            raise ValueError("LOCAL_LLM_URL is not configured.")
        client = OpenAI(base_url=base_url, api_key=os.environ.get("LOCAL_LLM_API_KEY", "not-needed"))
        model = artifact.model or os.environ.get("LOCAL_LLM_MODEL") or os.environ.get("OPENAI_MODEL", "local")
    elif artifact.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        client = OpenAI(api_key=api_key)
        model = artifact.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        raise ValueError(f"Provider {artifact.provider!r} cannot generate summaries.")

    version = node.current_version_object
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": f"# {version.title}\n\n{version.content or ''}"}],
        temperature=0.2,
    )
    artifact.model = model
    summary = response.choices[0].message.content
    if not summary or not summary.strip():
        raise ValueError("The model returned an empty summary.")
    return summary.strip()


def process_summary_artifact(artifact: SummaryArtifact) -> None:
    node = Node.query.filter_by(id=artifact.node_id).first()
    if not node:
        fail_summary(artifact, "Target node no longer exists.")
        return
    try:
        complete_summary(artifact, generate_summary(artifact, node), used_vision=False)
    except Exception as exc:
        fail_summary(artifact, str(exc))
