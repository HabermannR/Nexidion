from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


@dataclass(frozen=True)
class ConnectorContext:
    config: dict
    credential: dict | None = None


@dataclass(frozen=True)
class SourceDocument:
    external_id: str
    title: str
    markdown: str
    content_hash: str
    source_uri: str | None = None
    source_version: str | None = None
    parent_external_id: str | None = None
    metadata: dict = field(default_factory=dict)
    mime_type: str | None = None
    external_modified_at: str | None = None
    language: str | None = None
    authority: str = "secondary_source"


class Connector(Protocol):
    name: str
    capabilities: frozenset[str]

    def discover(self, context: ConnectorContext) -> Iterable[SourceDocument]: ...
