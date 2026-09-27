"""Agent-native retrieval: verbatim search snippets, node-scoped assets and
deterministic context bundles.

Everything here assembles original material with provenance; nothing here
interprets it. Every node that contributes text, a title or an edge has passed
the same read-policy check as a direct read, so hidden nodes never appear as
snippets, neighbours or "ghost" edges.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from backend.models import db, Node, Version, ImageAsset
from backend.services import node_policy_service
from backend.services.vault_service import _verify_vault_access


# ========================================================================
# SEARCH SNIPPETS
# ========================================================================

WORD_RE = re.compile(r"\w+", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _query_terms(query: str) -> list[str]:
    """Lower-cased query words. Stemmed FTS matches "Übungen" for "Übung", so each
    term is also matched as a prefix of at least four characters."""
    seen: list[str] = []
    for word in WORD_RE.findall(query.lower()):
        if len(word) >= 2 and word not in seen:
            seen.append(word)
    return seen


def _term_pattern(terms: list[str]) -> re.Pattern | None:
    if not terms:
        return None
    stems = sorted({t if len(t) <= 5 else t[:max(4, len(t) - 2)] for t in terms}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(s) for s in stems) + r")\w*", re.IGNORECASE)


def _hit_term(hit: str, terms: list[str]) -> str:
    hit = hit.lower()
    for term in terms:
        if hit.startswith(term if len(term) <= 5 else term[:max(4, len(term) - 2)]):
            return term
    return hit


def heading_path(content: str, offset: int) -> list[str]:
    """Markdown heading trail in effect at `offset`, ignoring fenced code."""
    path: list[tuple[int, str]] = []
    in_fence = False
    position = 0
    for line in content.splitlines(keepends=True):
        if position > offset:
            break
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            match = HEADING_RE.match(line.rstrip("\n"))
            if match:
                level = len(match.group(1))
                path = [item for item in path if item[0] < level]
                path.append((level, match.group(2).strip()))
        position += len(line)
    return [title for _, title in path]


def _snap_window(content: str, start: int, end: int, slack: int = 60) -> tuple[int, int]:
    """Widen [start, end) outward to the nearest whitespace so words are not cut.
    Gives up after `slack` characters (e.g. a long URL) and keeps the hard cut."""
    snapped = start
    while snapped > 0 and not content[snapped - 1].isspace() and start - snapped < slack:
        snapped -= 1
    if snapped == 0 or content[snapped - 1].isspace():
        start = snapped
    snapped = end
    while snapped < len(content) and not content[snapped].isspace() and snapped - end < slack:
        snapped += 1
    if snapped == len(content) or content[snapped].isspace():
        end = snapped
    return start, end


def find_matches(content: str, query: str, *, snippet_length: int = 600,
                 max_snippets: int = 3) -> list[dict]:
    """Verbatim excerpts of `content` around the densest query-term hits.

    Returned text is an exact slice: content[start_char:end_char] == text.
    """
    if not content or max_snippets <= 0:
        return []
    terms = _query_terms(query)
    pattern = _term_pattern(terms)
    if pattern is None:
        return []
    hits = [(m.start(), m.end(), _hit_term(m.group(0), terms)) for m in pattern.finditer(content)]
    if not hits:
        return []

    # Score a window centred on every hit by the distinct terms it covers, then
    # greedily take the best non-overlapping windows. Deterministic: ties go to
    # the earlier position.
    half = snippet_length // 2
    candidates = []
    for index, (hit_start, hit_end, _) in enumerate(hits):
        start = max(0, (hit_start + hit_end) // 2 - half)
        end = min(len(content), start + snippet_length)
        start = max(0, end - snippet_length)
        covered = {term for s, e, term in hits if s >= start and e <= end}
        count = sum(1 for s, e, _ in hits if s >= start and e <= end)
        candidates.append((-len(covered), -count, start, end, index))
    candidates.sort()

    chosen: list[tuple[int, int]] = []
    for _, _, start, end, _ in candidates:
        if len(chosen) >= max_snippets:
            break
        if any(start < c_end and end > c_start for c_start, c_end in chosen):
            continue
        chosen.append((start, end))

    matches = []
    for start, end in sorted(chosen):
        start, end = _snap_window(content, start, end)
        first_hit = next(s for s, e, _ in hits if s >= start and e <= end)
        matches.append({
            "text": content[start:end],
            "start_char": start,
            "end_char": end,
            "truncated_before": start > 0,
            "truncated_after": end < len(content),
            # The section of the hit itself; the window may begin in the section before.
            "heading_path": heading_path(content, first_hit),
            "terms": sorted({term for s, e, term in hits if s >= start and e <= end}),
        })
    return matches


def match_sources(query: str, title: str, content: str, summary: str | None) -> list[str]:
    pattern = _term_pattern(_query_terms(query))
    if pattern is None:
        return []
    return [name for name, text in (("title", title), ("content", content), ("summary", summary))
            if text and pattern.search(text)]


def enrich_search_result(result: dict, node: Node, query: str, *, snippet_length: int,
                         max_snippets: int, include_content: bool, include_summary: bool) -> dict:
    """Attach verbatim matches from the current version. `summary_only` is true when
    the node was found through its AI summary alone — the summary is then the only
    evidence, and it may be stale or interpretive."""
    version = node.current_version_object
    content = version.content if version and version.content else ""
    sources = match_sources(query, result.get("title") or "", content, node.ai_summary)
    result["version"] = node.current_version
    result["timestamp"] = version.timestamp.isoformat() if version and version.timestamp else None
    result["content_chars"] = len(content)
    result["match_sources"] = sources
    result["summary_only"] = sources == ["summary"]
    result["matches"] = find_matches(content, query, snippet_length=snippet_length,
                                     max_snippets=max_snippets)
    for match in result["matches"]:
        match["version"] = node.current_version
    if not include_content:
        result.pop("content", None)
    if not include_summary:
        result.pop("ai_summary", None)
    return result


def is_in_subtree(node: Node, root_id: str) -> bool:
    current, seen = node, set()
    while current is not None and current.id not in seen:
        if current.id == root_id:
            return True
        seen.add(current.id)
        current = current.parent
    return False


# ========================================================================
# NODE-SCOPED ASSETS
# ========================================================================

def _asset_ref_re(vault_id: int) -> re.Pattern:
    return re.compile(rf"/api/vaults/{int(vault_id)}/assets/([0-9a-f]{{8}}-(?:[0-9a-f]{{4}}-){{3}}[0-9a-f]{{12}})",
                      re.IGNORECASE)


MD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"([^"]*)")?\s*\)')


def asset_references(vault_id: int, content: str | None) -> list[dict]:
    """Managed-asset references in document order, with markdown alt text/title."""
    if not content:
        return []
    ref_re = _asset_ref_re(vault_id)
    described = {}
    for match in MD_IMAGE_RE.finditer(content):
        ref = ref_re.search(match.group(2))
        if ref:
            described.setdefault(ref.group(1).lower(), (match.group(1) or None, match.group(3) or None))
    references, seen = [], set()
    for ref in ref_re.finditer(content):
        asset_id = ref.group(1).lower()
        if asset_id in seen:
            continue
        seen.add(asset_id)
        alt, caption = described.get(asset_id, (None, None))
        references.append({"asset_id": asset_id, "alt_text": alt, "caption": caption,
                           "offset": ref.start()})
    return references


def _readable_node(node_id: str, vault_id: int, user_id: int, actor_type: str | None,
                   include_quarantined: bool) -> Node:
    _verify_vault_access(vault_id, user_id)
    node = (Node.query.options(joinedload(Node.current_version_object))
            .filter_by(id=node_id, vault_id=vault_id).first())
    if not node:
        raise LookupError("Node not found")
    node_policy_service.assert_readable(node, user_id, actor_type=actor_type,
                                        include_quarantined=include_quarantined)
    return node


def list_node_assets(node_id: str, vault_id: int, user_id: int, *, actor_type: str | None = None,
                     include_quarantined: bool = False) -> dict:
    from backend.services.image_asset_service import asset_path

    node = _readable_node(node_id, vault_id, user_id, actor_type, include_quarantined)
    content = node.current_version_object.content if node.current_version_object else ""
    in_content = asset_references(vault_id, content)
    in_summary = asset_references(vault_id, node.ai_summary)
    content_ids = {ref["asset_id"] for ref in in_content}
    ordered = in_content + [ref for ref in in_summary if ref["asset_id"] not in content_ids]
    rows = {row.id.lower(): row for row in ImageAsset.query.filter(
        ImageAsset.vault_id == vault_id,
        func.lower(ImageAsset.id).in_([ref["asset_id"] for ref in ordered])).all()} if ordered else {}

    assets = []
    for ordinal, ref in enumerate(ordered, 1):
        row = rows.get(ref["asset_id"])
        item = {
            "ordinal": ordinal,
            "asset_id": row.id if row else ref["asset_id"],
            "alt_text": ref["alt_text"],
            "caption": ref["caption"],
            "embedded_in_current_content": ref["asset_id"] in content_ids,
            "embedded_in_summary": any(s["asset_id"] == ref["asset_id"] for s in in_summary),
            "available": False,
        }
        if row:
            path = asset_path(row)
            item.update({
                "kind": "image" if row.media_type.startswith("image/") else "file",
                "mime_type": row.media_type,
                "filename": row.original_filename,
                "width": row.width,
                "height": row.height,
                "byte_size": path.stat().st_size if path.is_file() else None,
                "content_hash": row.content_hash,
                "page_number": row.page_number,
                "source_artifact_id": row.source_artifact_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "available": path.is_file(),
            })
        assets.append(item)
    return {"node_id": node.id, "vault_id": vault_id, "version": node.current_version,
            "effective_access_policy": node_policy_service.effective_policy(node).to_dict(),
            "assets": assets}


def get_node_asset(node_id: str, asset_id: str, vault_id: int, user_id: int, *,
                   actor_type: str | None = None, include_quarantined: bool = False) -> ImageAsset:
    """An asset, reachable only through a readable node that currently embeds it."""
    node = _readable_node(node_id, vault_id, user_id, actor_type, include_quarantined)
    content = node.current_version_object.content if node.current_version_object else ""
    embedded = {ref["asset_id"] for ref in asset_references(vault_id, content)}
    embedded |= {ref["asset_id"] for ref in asset_references(vault_id, node.ai_summary)}
    if asset_id.lower() not in embedded:
        raise LookupError("This node does not embed that asset.")
    asset = ImageAsset.query.filter(ImageAsset.vault_id == vault_id,
                                    func.lower(ImageAsset.id) == asset_id.lower()).first()
    if not asset:
        raise LookupError("Image asset not found.")
    return asset


def asset_readable_by_ai(asset: ImageAsset, user_id: int, actor_type: str | None,
                         include_quarantined: bool) -> bool:
    """For direct asset URLs: an AI actor may fetch an asset only if some node it
    may read currently embeds it. Knowing the URL is not permission."""
    if not node_policy_service.is_ai_actor(user_id, actor_type):
        return True
    reference = f"/api/vaults/{asset.vault_id}/assets/{asset.id}"
    nodes = (db.session.query(Node)
             .outerjoin(Node.current_version_object)
             .filter(Node.vault_id == asset.vault_id,
                     or_(Version.content.contains(reference), Node.ai_summary.contains(reference)))
             .all())
    for node in nodes:
        try:
            node_policy_service.assert_readable(node, user_id, actor_type=actor_type,
                                                include_quarantined=include_quarantined)
            return True
        except PermissionError:
            continue
    return False


PREVIEW_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "PNG", "image/gif": "PNG"}


def render_preview(path, media_type: str, max_px: int) -> tuple[bytes, str]:
    """Downscaled copy so agents get a model-sized image instead of the original."""
    from PIL import Image

    with Image.open(path) as image:
        image.seek(0)
        image = image.copy()
    image.thumbnail((max_px, max_px))
    target = PREVIEW_FORMATS.get(media_type, "PNG")
    if target == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format=target, optimize=True)
    return buffer.getvalue(), "image/png" if target == "PNG" else "image/jpeg"


# ========================================================================
# CONTEXT BUNDLES
# ========================================================================

STRONG_LINK_RE = re.compile(
    r"\[\[(?:([^\]|]*)\|)?([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})\]\]", re.IGNORECASE)
WEAK_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
UUID_RE = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$", re.IGNORECASE)

RELATION_ORDER = {"parent": 0, "child": 1, "outlink": 2, "backlink": 3}
CONTENT_MODES = {"none", "snippets", "full"}
MAX_DEPTH = 3
MAX_ITEMS = 100
MAX_CHARS = 200_000


@dataclass
class _Edge:
    node: Node
    relation: str
    via: Node
    link_offset: int | None = None   # where the link sits inside the linking node
    linking_node: Node | None = None


def _content(node: Node) -> str:
    version = node.current_version_object
    return version.content if version and version.content else ""


def _link_context(content: str, offset: int, radius: int = 160) -> str:
    start, end = max(0, offset - radius), min(len(content), offset + radius)
    start, end = _snap_window(content, start, end)
    return content[start:end].strip()


def outlinks(node: Node) -> list[tuple[str, int, str]]:
    """(target, offset, kind) for [[title|uuid]] strong links and [[Title]] weak links."""
    content = _content(node)
    found: list[tuple[str, int, str]] = []
    strong_spans = []
    for match in STRONG_LINK_RE.finditer(content):
        found.append((match.group(2).lower(), match.start(), "uuid"))
        strong_spans.append((match.start(), match.end()))
    for match in WEAK_LINK_RE.finditer(content):
        if any(s <= match.start() < e for s, e in strong_spans):
            continue
        target = match.group(1).strip()
        if target and not UUID_RE.match(target):
            found.append((target, match.start(), "title"))
    return found


class _Assembler:
    def __init__(self, vault_id, user_id, actor_type, include_quarantined):
        self.vault_id = vault_id
        self.user_id = user_id
        self.actor_type = actor_type
        self.include_quarantined = include_quarantined

    def readable(self, node: Node | None) -> bool:
        if node is None or node.vault_id != self.vault_id:
            return False
        try:
            node_policy_service.assert_readable(node, self.user_id, actor_type=self.actor_type,
                                                include_quarantined=self.include_quarantined)
            return True
        except PermissionError:
            return False

    def _load(self, query):
        return query.options(joinedload(Node.current_version_object)).all()

    def neighbours(self, node: Node, *, parent: bool, children: bool, out: bool, back: bool) -> list[_Edge]:
        edges: list[_Edge] = []
        if parent and node.parent_id:
            if self.readable(node.parent):
                edges.append(_Edge(node.parent, "parent", node))
        if children:
            kids = self._load(Node.query.filter_by(parent_id=node.id, vault_id=self.vault_id))
            kids.sort(key=lambda child: ((child.title or "").lower(), child.id))
            edges.extend(_Edge(child, "child", node) for child in kids if self.readable(child))
        if out:
            links = outlinks(node)
            ids = [target for target, _, kind in links if kind == "uuid"]
            titles = [target for target, _, kind in links if kind == "title"]
            by_id = {n.id.lower(): n for n in self._load(
                Node.query.filter(Node.vault_id == self.vault_id, func.lower(Node.id).in_(ids)))} if ids else {}
            by_title: dict[str, list[Node]] = {}
            if titles:
                for candidate in self._load(Node.query.join(Node.current_version_object).filter(
                        Node.vault_id == self.vault_id,
                        func.lower(Version.title).in_([t.lower() for t in titles]))):
                    if self.readable(candidate):
                        by_title.setdefault(candidate.title.lower(), []).append(candidate)
            for target, offset, kind in links:
                if kind == "uuid":
                    linked = by_id.get(target)
                else:
                    matches = by_title.get(target.lower(), [])
                    linked = matches[0] if len(matches) == 1 else None  # ambiguous titles are not edges
                if linked is not None and linked.id != node.id and self.readable(linked):
                    edges.append(_Edge(linked, "outlink", node, offset, node))
        if back:
            title = node.title or ""
            patterns = [Version.content.contains(node.id)]
            if title:
                patterns += [Version.content.contains(f"[[{title}]]"), Version.content.contains(f"[[{title}|")]
            sources = self._load(Node.query.join(Node.current_version_object).filter(
                Node.vault_id == self.vault_id, Node.id != node.id, or_(*patterns)))
            sources.sort(key=lambda source: ((source.title or "").lower(), source.id))
            for source in sources:
                if not self.readable(source):
                    continue
                offset = next((o for target, o, kind in outlinks(source)
                               if (kind == "uuid" and target == node.id.lower())
                               or (kind == "title" and title and target.lower() == title.lower())), None)
                if offset is not None:  # a bare UUID in prose is not a link
                    edges.append(_Edge(source, "backlink", node, offset, source))
        return edges


class _BundleBuilder:
    """Shared breadth-first expansion for node- and query-seeded bundles.

    Items are ordered by distance, then relation (parent, child, outlink, backlink),
    then discovery order. Nodes the caller may not read are skipped silently and are
    neither counted nor traversed, so a bundle cannot reveal that they exist.
    """

    def __init__(self, vault_id: int, user_id: int, *, actor_type, include_quarantined,
                 include_parent, include_children, include_outlinks, include_backlinks,
                 include_content, snippet_chars, include_summaries, max_items, max_chars):
        if include_content not in CONTENT_MODES:
            raise ValueError("include_content must be none, snippets, or full")
        self.assembler = _Assembler(vault_id, user_id, actor_type, include_quarantined)
        self.edges = dict(parent=include_parent, children=include_children,
                          out=include_outlinks, back=include_backlinks)
        self.include_content = include_content
        self.snippet_chars = max(100, min(int(snippet_chars), 20_000))
        self.include_summaries = include_summaries
        self.max_items = max(1, min(int(max_items), MAX_ITEMS))
        self.max_chars = max(0, min(int(max_chars), MAX_CHARS))
        self.chars_left = self.max_chars
        self.budget_exhausted = False
        self.items: list[dict] = []
        self.included: dict[str, dict] = {}
        self.seen: set[str] = set()
        self.omitted = 0

    def text_for(self, node: Node) -> dict:
        content = _content(node)
        if self.include_content == "none":
            return {"content_chars": len(content)}
        wanted = content if self.include_content == "full" else content[:self.snippet_chars]
        if self.include_content == "snippets" and len(wanted) < len(content):
            wanted = content[:_snap_window(content, 0, len(wanted))[1]]
        allowed = wanted[:self.chars_left]
        self.chars_left -= len(allowed)
        if len(allowed) < len(wanted):
            self.budget_exhausted = True
        return {"content": allowed, "content_source": "original", "content_chars": len(content),
                "content_truncated": len(allowed) < len(content)}

    def describe(self, node: Node) -> dict:
        version = node.current_version_object
        item = {
            "id": node.id,
            "title": node.title,
            "parent_id": node.parent_id,
            "content_kind": node.content_kind,
            "authority": node.authority,
            "language": node.language,
            "tags": node.tags or [],
            "version": node.current_version,
            "timestamp": version.timestamp.isoformat() if version and version.timestamp else None,
            "summary_is_current": node.summary_is_current,
            "effective_access_policy": node_policy_service.effective_policy(node).to_dict(),
        }
        if self.include_summaries:
            item["ai_summary"] = node.ai_summary
        return item

    def add(self, item: dict, node: Node) -> None:
        self.items.append(item)
        self.included[node.id] = item

    def expand(self, seeds: list[Node], depth: int) -> None:
        self.seen.update(node.id for node in seeds)
        frontier = list(seeds)
        for distance in range(1, depth + 1):
            edges: list[_Edge] = []
            for node in frontier:
                edges.extend(self.assembler.neighbours(node, **self.edges))
            edges.sort(key=lambda edge: RELATION_ORDER[edge.relation])  # stable: keeps discovery order
            next_frontier = []
            for edge in edges:
                if edge.node.id in self.seen:
                    # Keep every edge to an included node: a child that also links
                    # back is both, and the link text is part of the provenance.
                    existing = self.included.get(edge.node.id)
                    if existing is not None and existing.get("relation_from") == edge.via.id:
                        other = {"relation": edge.relation, "relation_from": edge.via.id, "distance": distance}
                        if edge.linking_node is not None and edge.link_offset is not None:
                            other["link_context"] = _link_context(_content(edge.linking_node), edge.link_offset)
                        if other not in existing.setdefault("other_relations", []):
                            existing["other_relations"].append(other)
                    continue
                self.seen.add(edge.node.id)
                if len(self.items) >= self.max_items:
                    self.omitted += 1
                    continue
                item = self.describe(edge.node)
                item.update({"relation": edge.relation, "distance": distance, "relation_from": edge.via.id})
                if edge.linking_node is not None and edge.link_offset is not None:
                    item["link_context"] = _link_context(_content(edge.linking_node), edge.link_offset)
                    item["link_context_source"] = edge.linking_node.id
                item.update(self.text_for(edge.node))
                self.add(item, edge.node)
                next_frontier.append(edge.node)
            frontier = next_frontier
            if not frontier:
                break

    def envelope(self, depth: int) -> dict:
        return {
            "items": self.items,
            "depth": depth,
            "truncated": self.omitted > 0 or self.budget_exhausted,
            "omitted_count": self.omitted,
            "content_budget_exhausted": self.budget_exhausted,
            "limits": {"max_items": self.max_items, "max_chars": self.max_chars,
                       "snippet_chars": self.snippet_chars, "include_content": self.include_content},
            "note": ("Nodes hidden by access policy are omitted without trace and are not "
                     "counted in omitted_count."),
        }


def build_context_bundle(node_id: str, vault_id: int, user_id: int, *, actor_type: str | None = None,
                         include_quarantined: bool = False, depth: int = 1,
                         include_parent: bool = True, include_children: bool = True,
                         include_outlinks: bool = True, include_backlinks: bool = True,
                         include_content: str = "snippets", snippet_chars: int = 1200,
                         include_summaries: bool = True, include_assets_metadata: bool = True,
                         max_items: int = 30, max_chars: int = 30_000) -> dict:
    """Bounded, policy-filtered neighbourhood of one node, breadth-first."""
    depth = max(0, min(int(depth), MAX_DEPTH))
    builder = _BundleBuilder(
        vault_id, user_id, actor_type=actor_type, include_quarantined=include_quarantined,
        include_parent=include_parent, include_children=include_children,
        include_outlinks=include_outlinks, include_backlinks=include_backlinks,
        include_content=include_content, snippet_chars=snippet_chars,
        include_summaries=include_summaries, max_items=max_items, max_chars=max_chars)
    root = _readable_node(node_id, vault_id, user_id, actor_type, include_quarantined)
    root_item = {**builder.describe(root), **builder.text_for(root)}
    if include_assets_metadata:
        root_item["assets"] = list_node_assets(root.id, vault_id, user_id, actor_type=actor_type,
                                               include_quarantined=include_quarantined)["assets"]
    builder.expand([root], depth)
    return {"root": root_item, **builder.envelope(depth)}


def build_search_context_bundle(query: str, vault_id: int, user_id: int, *,
                                actor_type: str | None = None, include_quarantined: bool = False,
                                seed_limit: int = 5, depth: int = 1, max_snippets: int = 2,
                                snippet_length: int = 400, subtree_root_id: str | None = None,
                                include_parent: bool = True, include_children: bool = True,
                                include_outlinks: bool = True, include_backlinks: bool = True,
                                include_content: str = "snippets", snippet_chars: int = 1200,
                                include_summaries: bool = True, max_items: int = 30,
                                max_chars: int = 30_000) -> dict:
    """Search for seed nodes, then expand each seed's neighbourhood once.

    Seeds are ranked hits (relation "seed", distance 0) carrying their verbatim
    search matches; neighbours shared between seeds appear once, attributed to the
    first seed that reached them. Seeds count against max_items.
    """
    from backend.services import node_service

    if not query or not query.strip():
        raise ValueError("A search query is required.")
    depth = max(0, min(int(depth), MAX_DEPTH))
    seed_limit = max(1, min(int(seed_limit), 20))
    builder = _BundleBuilder(
        vault_id, user_id, actor_type=actor_type, include_quarantined=include_quarantined,
        include_parent=include_parent, include_children=include_children,
        include_outlinks=include_outlinks, include_backlinks=include_backlinks,
        include_content=include_content, snippet_chars=snippet_chars,
        include_summaries=include_summaries, max_items=max_items, max_chars=max_chars)
    hits = node_service.search_nodes_fulltext(
        query, vault_id, user_id, seed_limit, actor_type=actor_type,
        include_quarantined=include_quarantined, snippets=True, snippet_length=snippet_length,
        max_snippets=max_snippets, include_content=False, subtree_root_id=subtree_root_id)
    nodes = {node.id: node for node in Node.query.options(joinedload(Node.current_version_object))
             .filter(Node.id.in_([hit["id"] for hit in hits])).all()} if hits else {}
    seeds = []
    for rank, hit in enumerate(hits, 1):
        node = nodes.get(hit["id"])
        if node is None:
            continue
        if len(builder.items) >= builder.max_items:
            builder.omitted += 1
            continue
        item = builder.describe(node)
        item.update({"relation": "seed", "distance": 0, "relation_from": None, "search_rank": rank,
                     "relevance_score": hit["relevance_score"], "matches": hit["matches"],
                     "match_sources": hit["match_sources"], "summary_only": hit["summary_only"]})
        item.update(builder.text_for(node))
        builder.add(item, node)
        seeds.append(node)
    builder.expand(seeds, depth)
    return {"query": query, "seed_count": len(seeds), **builder.envelope(depth)}
