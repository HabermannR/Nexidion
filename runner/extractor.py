"""
core/extractor.py — Single source of truth for all file text extraction.

Both the upload endpoint (services/file_service.py) and the LLM attachment
tool (tools/pdf_reader_tool.py) call extract_file() and get back an
ExtractedDocument. Bug fixes and improvements made here automatically apply
to both paths.

Supported formats
-----------------
.pdf        — PyMuPDF / PyMuPDF4LLM, password-protected PDFs supported
"""

from __future__ import annotations

import base64
import gc
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field

import pymupdf
import pymupdf4llm


# Lazy import: logger comes from the app config when running inside the package,
# or falls back to stdlib logging when this module is tested in isolation.
try:
    from ..core.config import logger  # type: ignore
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class PasswordRequiredError(Exception):
    """PDF is encrypted but no password was supplied."""

class InvalidPasswordError(Exception):
    """A password was supplied but it is incorrect."""


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass
class ExtractedDocument:
    """
    Canonical result returned by every extraction path.
    """
    text: str
    filename: str
    extension: str
    page_count: int = 0
    char_count: int = 0
    was_truncated: bool = False
    metadata: dict = field(default_factory=dict)

    def truncate(self, max_chars: int) -> "ExtractedDocument":
        """Return a copy with text capped at max_chars."""
        if len(self.text) <= max_chars:
            return self
        return ExtractedDocument(
            text=self.text[:max_chars],
            filename=self.filename,
            extension=self.extension,
            page_count=self.page_count,
            char_count=max_chars,
            was_truncated=True,
            metadata=self.metadata,
        )


@dataclass
class ExtractedPage:
    """A single page from a visual PDF extraction."""
    page_num: int
    text: str
    image_base64: str   # PNG rendered at 150 DPI, base64-encoded
    width_px: int
    height_px: int


@dataclass
class ExtractedVisualDocument:
    """Result of a visual (image-aware) PDF extraction."""
    filename: str
    page_count: int
    pages: list  # List[ExtractedPage]
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".pdf"
}

def extract_file(
    file_path: Union[str, Path],
    password: Optional[str] = None,
) -> ExtractedDocument:
    """
    Extract text from *file_path* and return an ExtractedDocument.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    logger.debug(f"[extractor] Extracting '{path.name}' (ext={ext})")

    if ext == ".pdf":
        return _extract_pdf(path, password=password)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

# Thresholds for sending a rendered image of the page to Vision LLMs.
_VISUAL_AREA_THRESHOLD = 0.10
_TEXT_CHARS_THRESHOLD = 50


def _page_visual_fraction(page) -> float:
    """
    Return the fraction of *page* area covered by images and vector drawings.
    """
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return 0.0

    covered = 0.0

    # Raster images embedded in the page
    for img_info in page.get_image_info():
        r = pymupdf.Rect(img_info["bbox"])
        covered += r.width * r.height

    # Vector drawings (shapes, charts, logos)
    for drawing in page.get_drawings():
        r = pymupdf.Rect(drawing["rect"])
        covered += r.width * r.height

    # Cap at 1.0 (overlapping elements can sum > page area)
    return min(covered / page_area, 1.0)


def _extract_pdf(
    path: Path,
    password: Optional[str] = None,
) -> ExtractedDocument:
    """Compatibility shim — delegates to extract_pdf_smart."""
    result = extract_pdf_smart(path, password=password)

    any_visual = any(p.image_base64 for p in result.pages)
    force_visual = any_visual

    text_blocks = []
    for p in result.pages:
        page_text = str(p.text) if p.text else ""
        if page_text.strip():
            text_blocks.append(f"--- Page {p.page_num} ---\n{page_text.strip()}")

    full_text = "\n".join(text_blocks)

    pages_data = [
        {
            "page_num": p.page_num,
            "text": str(p.text) if p.text else "",
            "image_base64": str(p.image_base64) if p.image_base64 else "",
            "width_px": int(p.width_px) if p.width_px else 0,
            "height_px": int(p.height_px) if p.height_px else 0,
        }
        for p in result.pages
    ]

    return ExtractedDocument(
        text=full_text,
        filename=result.filename,
        extension=".pdf",
        page_count=result.page_count,
        char_count=len(full_text),
        metadata={
            **(result.metadata or {}),
            "visual_only": force_visual,
            "has_visual_pages": any_visual,
            "pages": pages_data,
        },
    )


def extract_pdf_smart(
    path: Union[str, Path],
    password: Optional[str] = None,
    dpi: int = 150,
) -> ExtractedVisualDocument:
    """
    Smart hybrid PDF extractor.

    Extracts text using layout-aware PyMuPDF4LLM into Markdown formats, providing
    structure (tables, multi-column mapping) for robust LLM understanding.
    Also renders heavily graphical pages into Base64 PNGs.
    """
    path = Path(path)
    logger.debug(f"[extractor] Smart PDF extraction: '{path.name}' @ {dpi} DPI")

    pages: list = []
    with pymupdf.open(str(path)) as doc:
        page_count = len(doc)
        logger.debug(f"[extractor] PDF pages={page_count}, encrypted={doc.is_encrypted}")

        if doc.is_encrypted:
            if not password:
                raise PasswordRequiredError(
                    "The PDF is encrypted. Please supply a password."
                )
            if doc.authenticate(password) == 0:
                raise InvalidPasswordError("The supplied password is incorrect.")
            logger.info("[extractor] Smart PDF: decrypted successfully.")

        metadata = dict(doc.metadata) if doc.metadata else {}
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)

        text_pages = 0
        visual_pages = 0

        # Batch extract LLM-ready markdown page-by-page chunks
        # This replaces generic 'page.get_text()' mapping table structure flawlessly. [Index: 1.1.2]
        md_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)

        for page_num_0_based, page in enumerate(doc):
            page_num = page_num_0_based + 1

            # Use structure-aware Markdown text, fallback to raw text if chunking fails
            if page_num_0_based < len(md_chunks):
                text = md_chunks[page_num_0_based].get("text", "").strip()
            else:
                text = page.get_text().strip()

            visual_fraction = _page_visual_fraction(page)
            is_visual = visual_fraction >= _VISUAL_AREA_THRESHOLD or not text

            if is_visual:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
                w, h = pix.width, pix.height
                pix = None
                visual_pages += 1
                logger.debug(
                    f"[extractor] Page {page_num}: visual ({visual_fraction:.0%} graphics) → rendered"
                )
            else:
                b64 = ""
                w = h = 0
                text_pages += 1
                logger.debug(
                    f"[extractor] Page {page_num}: text-only ({visual_fraction:.0%} graphics, "
                    f"{len(text)} chars) → skipped render"
                )

            pages.append(ExtractedPage(
                page_num=page_num,
                text=text,
                image_base64=b64,
                width_px=w,
                height_px=h,
            ))

        logger.info(
            f"[extractor] Smart PDF '{path.name}': "
            f"{text_pages} text-only, {visual_pages} visual page(s) rendered."
        )

    return ExtractedVisualDocument(
        filename=path.name,
        page_count=page_count,
        pages=pages,
        metadata=metadata,
    )


def extract_pdf_visual(
    file_path: Union[str, Path],
    password: Optional[str] = None,
    dpi: int = 150,
) -> ExtractedVisualDocument:
    """
    Extract both text and rendered page images from a PDF.
    """
    path = Path(file_path)
    logger.debug(f"[extractor] Visual PDF extraction: '{path.name}' @ {dpi} DPI")

    pages: list = []
    with pymupdf.open(str(path)) as doc:
        page_count = len(doc)

        if doc.is_encrypted:
            if not password:
                raise PasswordRequiredError(
                    "The PDF is encrypted. Please supply a password."
                )
            if doc.authenticate(password) == 0:
                raise InvalidPasswordError("The supplied password is incorrect.")
            logger.info("[extractor] Visual PDF: decrypted successfully.")

        metadata = dict(doc.metadata) if doc.metadata else {}
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)

        md_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)

        for page_num_0_based, page in enumerate(doc):
            page_num = page_num_0_based + 1

            # Fetch Markdown equivalent for best LLM understanding
            if page_num_0_based < len(md_chunks):
                text = md_chunks[page_num_0_based].get("text", "").strip()
            else:
                text = page.get_text().strip()

            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode("ascii")

            pages.append(ExtractedPage(
                page_num=page_num,
                text=text,
                image_base64=b64,
                width_px=pix.width,
                height_px=pix.height,
            ))
            pix = None  # free memory early

        logger.info(f"[extractor] Visual PDF: {page_count} pages rendered.")

    return ExtractedVisualDocument(
        filename=path.name,
        page_count=page_count,
        pages=pages,
        metadata=metadata,
    )