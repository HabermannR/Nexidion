from __future__ import annotations

import re
import math
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

import pymupdf

from backend.models import Node
from backend.services import node_service
from backend.services.image_asset_service import create_asset


LEGACY_RE = re.compile(r'!\[([^\]]*)\]\(/api/image/([^\s)]+)(?:\s+["\'][^"\']*["\'])?\)', re.I)
MAX_LEGACY_BYTES = 25 * 1024 * 1024
MAX_RASTER_EDGE = 4096
MAX_RASTER_PIXELS = 16_000_000
SVG_BLOCKED_ELEMENTS = {'a', 'animate', 'animateMotion', 'animateTransform', 'discard',
                        'foreignObject', 'image', 'script', 'set', 'use'}


def _index_files(root: Path):
    return {str(path.relative_to(root)).replace('\\', '/').casefold(): path
            for path in root.rglob('*') if path.is_file()}


def _asset_payload(path: Path) -> tuple[bytes, str]:
    """Return inert raster data for a legacy image; SVG is never stored directly."""
    data = path.read_bytes()
    if path.suffix.casefold() != '.svg':
        return data, path.name
    if not data or len(data) > MAX_LEGACY_BYTES:
        raise ValueError('Legacy SVG must be between 1 byte and 25 MiB.')
    try:
        root = ElementTree.fromstring(data)
        svg = root if root.tag.rsplit('}', 1)[-1] == 'svg' else next(
            (element for element in root.iter() if element.tag.rsplit('}', 1)[-1] == 'svg'), None
        )
        if svg is None:
            raise ValueError('Legacy SVG does not contain an SVG element.')
        for parent in list(svg.iter()):
            for child in list(parent):
                if child.tag.rsplit('}', 1)[-1] in SVG_BLOCKED_ELEMENTS:
                    parent.remove(child)
            for attribute, value in list(parent.attrib.items()):
                local_name = attribute.rsplit('}', 1)[-1].casefold()
                lowered_value = value.strip().casefold()
                if (local_name.startswith('on') or local_name in {'href', 'src'}
                        or ('url(' in lowered_value and 'url(#' not in lowered_value)):
                    del parent.attrib[attribute]
        sanitized = ElementTree.tostring(svg, encoding='utf-8', xml_declaration=True)
        with pymupdf.open(stream=sanitized, filetype='svg') as document:
            page = document[0]
            width, height = page.rect.width, page.rect.height
            if width <= 0 or height <= 0:
                raise ValueError('Legacy SVG has invalid dimensions.')
            scale = min(
                2.0,
                MAX_RASTER_EDGE / max(width, height),
                math.sqrt(MAX_RASTER_PIXELS / (width * height)),
            )
            if scale <= 0:
                raise ValueError('Legacy SVG has invalid dimensions.')
            png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True).tobytes('png')
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f'Legacy SVG could not be rasterized: {exc}') from exc
    return png, f'{path.stem}.png'


def convert_legacy_images(legacy_root: str | Path, apply: bool = False) -> dict:
    root = Path(legacy_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f'Legacy image directory does not exist: {root}')
    files = _index_files(root)
    report = {"mode": "apply" if apply else "dry-run", "references": 0, "converted": 0,
              "missing": [], "remote_skipped": [], "nodes_changed": 0, "summaries_changed": 0,
              "unreferenced": [], "assets": []}
    referenced_paths = set()

    for node in Node.query.order_by(Node.vault_id, Node.id).all():
        version = node.current_version_object
        if not version:
            continue
        owner_id = node.vault.owner_id

        def rewrite(text, location):
            changed = False
            def replace(match):
                nonlocal changed
                report["references"] += 1
                raw_name = unquote(match.group(2)).replace('\\', '/').lstrip('/')
                path = files.get(raw_name.casefold())
                if not path:
                    report["missing"].append({"node_id": node.id, "location": location, "path": raw_name})
                    return match.group(0)
                referenced_paths.add(path)
                try:
                    payload, filename = _asset_payload(path)
                except ValueError as exc:
                    report["missing"].append({"node_id": node.id, "location": location,
                                              "path": raw_name, "error": str(exc)})
                    return match.group(0)
                if not apply:
                    report["converted"] += 1
                    changed = True
                    return match.group(0)
                try:
                    asset = create_asset(node.vault_id, owner_id, payload, filename)
                except ValueError as exc:
                    report["missing"].append({"node_id": node.id, "location": location,
                                              "path": raw_name, "error": str(exc)})
                    return match.group(0)
                report["converted"] += 1
                report["assets"].append(asset.id)
                changed = True
                return f'![{match.group(1)}](/api/vaults/{node.vault_id}/assets/{asset.id})'
            return LEGACY_RE.sub(replace, text or ''), changed

        content, content_changed = rewrite(version.content, 'content')
        summary, summary_changed = rewrite(node.ai_summary, 'summary')
        if apply and content_changed:
            node_service.update_node(node.id, node.vault_id, owner_id, content=content,
                                     allow_managed_source=True)
        if apply and summary_changed:
            node_service.update_node_ai_summary(node.id, node.vault_id, owner_id, summary)
        report["nodes_changed"] += int(content_changed)
        report["summaries_changed"] += int(summary_changed)

    report["assets"] = sorted(set(report["assets"]))
    report["unreferenced"] = [str(path.relative_to(root)).replace('\\', '/')
                              for path in files.values() if path not in referenced_paths]
    return report
