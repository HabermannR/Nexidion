import hashlib

import pytest
import pymupdf

from backend.ingestion.base import ConnectorContext
from backend.ingestion.pdf import PDF_EXTRACTOR_VERSION, PdfConnector, extract_pdf
from backend.ingestion.registry import ConnectorRegistry


class ExampleConnector:
    name = "example"
    capabilities = frozenset({"read"})


def test_registry_rejects_duplicate_names():
    registry = ConnectorRegistry()
    registry.register(ExampleConnector())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ExampleConnector())


def test_pdf_connector_emits_stable_source_document(tmp_path, monkeypatch):
    path = tmp_path / "manual.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Manual")
    payload = pdf.tobytes()
    pdf.close()
    path.write_bytes(payload)
    monkeypatch.setattr("backend.ingestion.pdf.pymupdf4llm.to_markdown",
                        lambda _, **kwargs: [{"text": "# Manual"}])

    documents = list(PdfConnector().discover(ConnectorContext(config={"path": str(path)})))

    assert len(documents) == 2
    assert documents[0].external_id == "manual.pdf#container"
    assert documents[0].metadata["source_container"] is True
    assert documents[1].external_id == "manual.pdf#page=1"
    assert documents[1].parent_external_id == "manual.pdf#container"
    assert documents[1].markdown == "# Manual"
    source_hash = hashlib.sha256(payload).hexdigest()
    expected = f"{source_hash}:{PDF_EXTRACTOR_VERSION}:page:1"
    assert documents[1].content_hash == hashlib.sha256(expected.encode()).hexdigest()
    assert documents[1].metadata["page_count"] == 1
    assert documents[1].metadata["granularity"] == "page"


def test_pdf_images_are_rendered_with_transparency_composited(tmp_path, monkeypatch):
    path = tmp_path / "transparent.pdf"
    image_path = tmp_path / "transparent.png"
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), True)
    pixmap.clear_with(0)
    pixmap.set_rect(pymupdf.IRect(8, 8, 32, 32), (255, 0, 0, 255))
    pixmap.save(image_path)
    pdf = pymupdf.open()
    page = pdf.new_page(width=200, height=200)
    page.insert_image(pymupdf.Rect(20, 20, 100, 100), filename=str(image_path))
    pdf.save(path)
    pdf.close()
    extraction = extract_pdf(path)

    assert len(extraction.images) == 1
    rendered = pymupdf.Pixmap(extraction.images[0]["data"])
    samples = bytes(rendered.samples)
    assert min(samples) == 0
    assert max(samples) == 255
    assert extraction.images[0]["extension"] == "png"


def test_repeated_pdf_image_is_emitted_for_each_page(tmp_path, monkeypatch):
    path = tmp_path / "repeated.pdf"
    image_path = tmp_path / "image.png"
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pixmap.clear_with(128)
    pixmap.save(image_path)
    pdf = pymupdf.open()
    for _ in range(2):
        pdf.new_page().insert_image(pymupdf.Rect(20, 20, 80, 80), filename=str(image_path))
    pdf.save(path)
    pdf.close()
    extraction = extract_pdf(path)

    assert [image["page"] for image in extraction.images] == [1, 2]
