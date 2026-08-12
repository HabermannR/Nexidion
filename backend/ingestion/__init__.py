"""Stable connector API. Third-party packages register `nexidion.connectors` entry points."""

from .base import Connector, ConnectorContext, SourceDocument
from .registry import connector_registry

__all__ = ["Connector", "ConnectorContext", "SourceDocument", "connector_registry"]
