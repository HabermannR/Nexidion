import io

import pymupdf

from backend.models import (ConnectorInstallation, Node, SourceItem, Version, ImageAsset,
                            SourceArtifact, CurationJob, NodeSourceLink, VaultAccess, VaultRole)
from backend.services import node_service
from backend.services.curation_service import process_curation_job


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def _pdf_with_image() -> bytes:
    image_stream = io.BytesIO()
    from PIL import Image
    Image.new('RGB', (120, 100), 'green').save(image_stream, format='PNG')
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), 'Diagram below')
    page.insert_image(pymupdf.Rect(72, 100, 312, 300), stream=image_stream.getvalue())
    payload = document.tobytes()
    document.close()
    return payload


def _upload(client, headers, vault_id, content, filename="manual.pdf", parent_id=None):
    payload = content if isinstance(content, bytes) else _pdf_bytes(content)
    data = {
        "vault_id": str(vault_id),
        "file": (io.BytesIO(payload), filename),
    }
    if parent_id:
        data["parent_id"] = parent_id
    return client.post('/api/connectors/pdf/ingest', headers=headers, data=data,
                       content_type='multipart/form-data')


def test_pdf_upload_is_idempotent_and_updates_as_new_version(
        client, auth_headers_1, test_vault_1_obj, test_user_1_obj, db_session):
    first_pdf = _pdf_bytes("First edition")
    first = _upload(client, auth_headers_1, test_vault_1_obj.id, first_pdf)
    assert first.status_code == 201
    first_data = first.get_json()
    assert first_data["stats"]["created"] == 2
    page_item = next(item for item in first_data["stats"]["items"] if "#page=" in item["external_id"])
    assert page_item["status"] == "created"
    node_id = page_item["node_id"]

    unchanged = _upload(client, auth_headers_1, test_vault_1_obj.id, first_pdf)
    assert unchanged.status_code == 201
    assert unchanged.get_json()["stats"]["unchanged"] == 2
    assert Version.query.filter_by(node_id=node_id).count() == 1

    changed = _upload(client, auth_headers_1, test_vault_1_obj.id, "Second edition")
    assert changed.status_code == 201
    assert changed.get_json()["stats"]["updated"] == 2
    changed_page = next(item for item in changed.get_json()["stats"]["items"] if "#page=" in item["external_id"])
    assert changed_page["node_id"] == node_id
    assert Version.query.filter_by(node_id=node_id).count() == 2

    node = db_session.session.get(Node, node_id)
    item = SourceItem.query.filter_by(node_id=node_id).one()
    assert node.content_kind == "canonical_source"
    assert item.mime_type == "application/pdf"
    assert item.metadata_json["page_count"] == 1
    assert item.source_uri == "upload://manual.pdf"

    try:
        node_service.update_node(node_id, test_vault_1_obj.id, test_user_1_obj.id, content="manual edit")
        assert False, "managed source should be frozen"
    except PermissionError as exc:
        assert "frozen canonical source" in str(exc)


def test_pdf_recreates_node_when_source_binding_survives_deletion(
        client, auth_headers_1, test_vault_1_obj, db_session):
    payload = _pdf_bytes("Recreate me")
    first = _upload(client, auth_headers_1, test_vault_1_obj.id, payload)
    page_item = next(item for item in first.get_json()["stats"]["items"] if "#page=" in item["external_id"])
    old_node_id = page_item["node_id"]
    db_session.session.delete(db_session.session.get(Node, old_node_id))
    db_session.session.commit()
    binding = SourceItem.query.filter(SourceItem.external_id.like('%#page=%')).one()
    assert binding.node_id is None

    second = _upload(client, auth_headers_1, test_vault_1_obj.id, payload)

    item = next(item for item in second.get_json()["stats"]["items"] if "#page=" in item["external_id"])
    assert item["status"] == "created"
    assert item["node_id"] != old_node_id
    assert SourceItem.query.count() == 2


def test_pdf_upload_exposes_runs_and_items(
        client, auth_headers_1, test_vault_1_obj, db_session):
    response = _upload(client, auth_headers_1, test_vault_1_obj.id, "Index me")
    connector_id = response.get_json()["connector"]["id"]
    run_id = response.get_json()["id"]

    runs = client.get(f'/api/connectors/{connector_id}/runs', headers=auth_headers_1)
    assert runs.status_code == 200
    assert runs.get_json()[0]["id"] == run_id

    run = client.get(f'/api/connectors/runs/{run_id}', headers=auth_headers_1)
    assert run.status_code == 200
    assert run.get_json()["status"] == "completed"

    items = client.get(f'/api/connectors/{connector_id}/items', headers=auth_headers_1)
    assert items.status_code == 200
    assert [item["external_id"] for item in items.get_json()] == [
        "manual.pdf#container", "manual.pdf#page=1"]


def test_pdf_upload_rejects_non_member(client, auth_headers_2, test_vault_1_obj):
    response = _upload(client, auth_headers_2, test_vault_1_obj.id, "Forbidden")
    assert response.status_code == 403


def test_pdf_upload_rejects_fake_pdf(client, auth_headers_1, test_vault_1_obj):
    response = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id),
        "file": (io.BytesIO(b"not really a pdf"), "fake.pdf"),
    }, content_type='multipart/form-data')
    assert response.status_code == 400
    assert "not a valid PDF" in response.get_json()["error"]


def test_pdf_extracts_images_as_managed_assets(
        app, client, auth_headers_1, test_vault_1_obj, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    response = _upload(client, auth_headers_1, test_vault_1_obj.id, _pdf_with_image(), 'visual.pdf')
    assert response.status_code == 201
    page_item = next(item for item in response.get_json()['stats']['items'] if '#page=' in item['external_id'])
    node_id = page_item['node_id']
    content = Node.query.filter_by(id=node_id).one().current_version_object.content
    container = Node.query.filter_by(vault_id=test_vault_1_obj.id, content_kind='source_container').one()
    assert Node.query.filter_by(id=node_id).one().parent_id == container.id
    asset = ImageAsset.query.filter_by(vault_id=test_vault_1_obj.id).one()
    assert f'/api/vaults/{test_vault_1_obj.id}/assets/{asset.id}' in content
    assert 'intentionally omitted' not in content
    assert asset.page_number == 1


def test_curate_only_stores_artifact_without_canonical_nodes(
        client, auth_headers_1, test_vault_1_obj, test_llm_agent_obj, db_session):
    db_session.session.add(VaultAccess(user_id=test_llm_agent_obj.id,
        vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR))
    db_session.session.commit()
    response = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "mode": "curate_only",
        "provider": "local", "visual_mode": "off",
        "file": (io.BytesIO(_pdf_bytes("Internal source")), "private-source.pdf"),
    }, content_type='multipart/form-data')
    assert response.status_code == 202
    data = response.get_json()
    assert data["curation_job"]["status"] == "pending"
    assert SourceArtifact.query.filter_by(id=data["artifact_id"]).one().payload
    assert CurationJob.query.filter_by(id=data["curation_job"]["id"]).one().mode == "curate_only"
    assert SourceItem.query.count() == 0
    assert Node.query.count() == 0


def test_extract_and_curate_places_job_under_pdf_container(
        client, auth_headers_1, test_vault_1_obj, test_llm_agent_obj, db_session):
    db_session.session.add(VaultAccess(user_id=test_llm_agent_obj.id,
        vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR))
    db_session.session.commit()

    response = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "mode": "extract_and_curate",
        "provider": "local", "visual_mode": "off",
        "file": (io.BytesIO(_pdf_bytes("Structured source")), "structured.pdf"),
    }, content_type='multipart/form-data')

    assert response.status_code == 202
    container = Node.query.filter_by(content_kind='source_container').one()
    job = db_session.session.get(CurationJob, response.get_json()['curation_job']['id'])
    assert job.parent_id == container.id
    page = Node.query.filter_by(content_kind='canonical_source').one()
    assert page.parent_id == container.id


def test_curation_creates_derived_nodes_with_page_provenance(
        client, auth_headers_1, test_vault_1_obj, test_llm_agent_obj, db_session, monkeypatch):
    db_session.session.add(VaultAccess(user_id=test_llm_agent_obj.id,
        vault_id=test_vault_1_obj.id, role=VaultRole.EDITOR))
    db_session.session.commit()
    response = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "mode": "curate_only",
        "provider": "local", "visual_mode": "off",
        "file": (io.BytesIO(_pdf_bytes("A technical fact")), "curate.pdf"),
    }, content_type='multipart/form-data')
    job = db_session.session.get(CurationJob, response.get_json()["curation_job"]["id"])

    class Message: content = '{"nodes":[{"title":"Synthesis","content":"Fact from source (pages 1-1).","page_from":1,"page_to":1}]}'
    class Choice: message = Message()
    class Response: choices = [Choice()]
    class Completions:
        @staticmethod
        def create(**kwargs): return Response()
    class Chat: completions = Completions()
    class Client: chat = Chat()
    monkeypatch.setattr('backend.services.curation_service._client', lambda _: (Client(), 'test-model'))

    process_curation_job(job)
    node = Node.query.filter_by(content_kind='ai_synthesis').one()
    link = NodeSourceLink.query.filter_by(node_id=node.id).one()
    assert job.status == 'completed'
    assert node.authority == 'derived'
    assert node.metadata_json['source_content_hash'] == link.source_content_hash
    assert (link.page_from, link.page_to) == (1, 1)

    changed = client.post('/api/connectors/pdf/ingest', headers=auth_headers_1, data={
        "vault_id": str(test_vault_1_obj.id), "mode": "curate_only",
        "provider": "local", "visual_mode": "off",
        "file": (io.BytesIO(_pdf_bytes("A changed technical fact")), "curate.pdf"),
    }, content_type='multipart/form-data')
    assert changed.status_code == 202
    db_session.session.refresh(link)
    assert link.is_stale is True

    provenance = client.get(f'/api/connectors/provenance/nodes/{node.id}', headers=auth_headers_1)
    assert provenance.status_code == 200
    assert provenance.get_json()[0]["is_stale"] is True
