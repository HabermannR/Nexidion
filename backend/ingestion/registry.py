from __future__ import annotations

from importlib.metadata import entry_points


class ConnectorRegistry:
    def __init__(self):
        self._connectors = {}

    def register(self, connector) -> None:
        name = connector.name.strip().lower()
        if not name or name in self._connectors:
            raise ValueError(f"Connector name is empty or already registered: {name!r}")
        invalid = set(connector.capabilities) - {"read", "ingest", "sync", "write_back"}
        if invalid:
            raise ValueError(f"Unsupported connector capabilities: {sorted(invalid)}")
        self._connectors[name] = connector

    def load(self) -> None:
        if self._connectors:
            return
        from .pdf import PdfConnector
        self.register(PdfConnector())
        for item in entry_points(group="nexidion.connectors"):
            self.register(item.load()())

    def get(self, name: str):
        self.load()
        try:
            return self._connectors[name.lower()]
        except KeyError as exc:
            raise ValueError(f"Unknown connector {name!r}. Installed: {', '.join(self.names())}") from exc

    def names(self) -> list[str]:
        self.load()
        return sorted(self._connectors)


connector_registry = ConnectorRegistry()
