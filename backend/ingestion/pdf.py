from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm

from .base import ConnectorContext, SourceDocument


@dataclass(frozen=True)
class PdfExtraction:
    payload: bytes
    content_hash: str
    pages: list[dict]
    outline: list[list]
    metadata: dict
    images: list[dict]


OMITTED_IMAGE_RE = re.compile(r'==>\s*picture\s*\[(\d+)\s*x\s*(\d+)\]\s*intentionally omitted\s*<==', re.I)
PDF_EXTRACTOR_VERSION = "pdf-composited-images-v2"
MARKDOWN_IMAGE_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def extract_pdf(path: str | Path) -> PdfExtraction:
    path = Path(path).expanduser().resolve()
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    with pymupdf.open(path) as pdf:
        outline = pdf.get_toc(simple=True)
        page_count = pdf.page_count
    images = []
    pages = []
    with tempfile.TemporaryDirectory(prefix="nexidion-pdf-images-") as image_dir:
        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True,
                                         write_images=True, image_path=image_dir)
        image_root = Path(image_dir).resolve()
        for index, chunk in enumerate(chunks, 1):
            def collect_image(match):
                candidate = Path(match.group(1)).resolve()
                if image_root not in candidate.parents or not candidate.is_file():
                    return match.group(0)
                data = candidate.read_bytes()
                pixmap = pymupdf.Pixmap(data)
                images.append({"page": index, "xref": None, "data": data,
                               "extension": candidate.suffix.lstrip(".") or "png",
                               "width": pixmap.width, "height": pixmap.height})
                return f"==> picture [{pixmap.width} x {pixmap.height}] intentionally omitted <=="
            markdown = MARKDOWN_IMAGE_RE.sub(collect_image, chunk.get("text", ""))
            pages.append({"page": index, "markdown": markdown})
    return PdfExtraction(payload, digest, pages, outline, {
        "filename": path.name, "size": len(payload), "page_count": page_count,
        "extractor_version": PDF_EXTRACTOR_VERSION,
    }, images)


def _replace_image_markers(markdown: str, page_number: int, config: dict) -> str:
    urls = list((config.get('image_urls_by_page') or {}).get(str(page_number), []))
    index = 0
    def replacement(match):
        nonlocal index
        if index < len(urls):
            item = urls[index]
            index += 1
            return f"![Extracted PDF image, page {page_number}]({item})"
        return (f"*[PDF image omitted: {match.group(1)} × {match.group(2)} px, "
                f"page {page_number}; no extractable raster image was available]*")
    return OMITTED_IMAGE_RE.sub(replacement, markdown)


FRONT_MATTER_TITLE = "Front matter"


def _chapter_starts(outline: list[list], page_count: int) -> list[tuple[str, int]]:
    """Top-level outline entries as (title, start page), usable as page ranges.

    Outlines are author-supplied and often messy: entries may point outside the
    document (-1 or past the end), share a page, or be out of order. Chapters must
    tile the whole document, so pages before the first entry become a front-matter
    chapter instead of being dropped.
    """
    if page_count <= 0 or not outline:
        return []
    top_level = min(level for level, _, _ in outline)
    starts: list[tuple[str, int]] = []
    for level, name, page in outline:
        if level != top_level:
            continue
        page = int(page)
        if page < 1 or page > page_count:
            continue
        if starts and page <= starts[-1][1]:
            continue  # same page as, or before, the previous chapter
        starts.append(((name or "").strip() or f"Pages from {page}", page))
    if starts and starts[0][1] > 1:
        starts.insert(0, (FRONT_MATTER_TITLE, 1))
    return starts


def documents_from_extraction(extraction: PdfExtraction, config: dict) -> list[SourceDocument]:
    external_id = config.get("external_id") or extraction.metadata["filename"]
    title = config.get("title") or Path(extraction.metadata["filename"]).stem
    source_uri = config.get("source_uri")
    granularity = config.get("granularity", "auto")
    if granularity == "auto":
        granularity = "chapter" if extraction.outline else "page"
    common = dict(source_uri=source_uri, mime_type="application/pdf",
                  authority=config.get("authority", "secondary_source"))
    container_id = f"{external_id}#container"
    container = SourceDocument(external_id=container_id, title=title,
        markdown=(f"# {title}\n\nManaged PDF source containing "
                  f"{extraction.metadata['page_count']} pages."),
        content_hash=hashlib.sha256((extraction.content_hash +
                                    f":{PDF_EXTRACTOR_VERSION}:container").encode()).hexdigest(),
        metadata={**extraction.metadata, "source_document_id": external_id,
                  "granularity": "container", "source_container": True}, **common)

    if granularity == "document":
        markdown = "\n\n".join(_replace_image_markers(page["markdown"], page["page"], config)
                                  for page in extraction.pages)
        return [container, SourceDocument(external_id=external_id, title=title, markdown=markdown,
            content_hash=hashlib.sha256((extraction.content_hash + f":{PDF_EXTRACTOR_VERSION}:document").encode()).hexdigest(),
            parent_external_id=container_id,
            metadata={**extraction.metadata, "page_from": 1, "page_to": len(extraction.pages), "granularity": "document"}, **common)]

    if granularity == "chapter" and extraction.outline:
        top = _chapter_starts(extraction.outline, len(extraction.pages))
        if not top:
            granularity = "page"
    if granularity == "chapter" and extraction.outline:
        documents = [container]
        for index, (name, start) in enumerate(top):
            end = (top[index + 1][1] - 1) if index + 1 < len(top) else len(extraction.pages)
            markdown = "\n\n".join(_replace_image_markers(p["markdown"], p["page"], config)
                                      for p in extraction.pages[start - 1:end])
            section_id = f"{external_id}#pages={start}-{end}"
            documents.append(SourceDocument(external_id=section_id, title=name, markdown=markdown,
                content_hash=hashlib.sha256((extraction.content_hash + f":{PDF_EXTRACTOR_VERSION}:{start}:{end}").encode()).hexdigest(),
                parent_external_id=container_id,
                metadata={**extraction.metadata, "source_document_id": external_id, "page_from": start,
                          "page_to": end, "granularity": "chapter"}, **common))
        return documents

    if granularity not in {"page", "auto", "chapter"}:
        raise ValueError("granularity must be auto, document, chapter, or page")
    return [container, *[SourceDocument(external_id=f"{external_id}#page={page['page']}",
        title=f"{title} — Page {page['page']}",
        markdown=_replace_image_markers(page["markdown"], page["page"], config),
        content_hash=hashlib.sha256((extraction.content_hash + f":{PDF_EXTRACTOR_VERSION}:page:{page['page']}").encode()).hexdigest(),
        parent_external_id=container_id,
        metadata={**extraction.metadata, "source_document_id": external_id, "page_from": page["page"],
                  "page_to": page["page"], "granularity": "page"}, **common) for page in extraction.pages]]


class PdfConnector:
    name = "pdf"
    capabilities = frozenset({"ingest", "sync"})

    def discover(self, context: ConnectorContext):
        # The upload path has already extracted the PDF to create image assets;
        # extraction is the slow part, so reuse it instead of doing it twice.
        extraction = context.config.get("extraction")
        if extraction is None:
            path = Path(context.config["path"]).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() != ".pdf":
                raise ValueError(f"Not a readable PDF: {path}")
            extraction = extract_pdf(path)
        yield from documents_from_extraction(extraction, context.config)
