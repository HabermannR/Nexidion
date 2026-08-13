from __future__ import annotations

from backend.models import SummaryArtifact, Node
from backend.services.llm_provider import client_and_model
from backend.services.summary_service import complete_summary, fail_summary

SYSTEM_PROMPT = """Create a concise, factual summary of the supplied Nexidion node.
Preserve important terminology, names, constraints, and conclusions. Do not invent
facts. Return only the summary in Markdown, normally 3-7 bullets."""


def generate_summary(artifact: SummaryArtifact, node: Node) -> str:
    client, model = client_and_model(artifact.provider, artifact.model)

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
