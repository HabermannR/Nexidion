import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.models import db, Node, Version, VaultAccess, VaultRole, ConnectorInstallation, SourceItem
from backend.services import node_service
from backend.exceptions import NodePatchConflictError


@pytest.fixture
def patch_target(client, auth_headers_1, test_vault_1_obj):
    content = "# Calendar\r\n\r\nAlpha and Beta.\r\nAlpha again.\r\nÄÖÜ unchanged."
    base = f'/api/vaults/{test_vault_1_obj.id}/nodes'
    response = client.post(base + '/', headers=auth_headers_1,
                           json={"title": "Calendar", "content": content})
    assert response.status_code == 201
    node_id = response.get_json()["id"]
    return base + '/' + node_id, content, node_id, test_vault_1_obj.id


def replacement(old="Alpha", new="[[Alpha]]", count=2):
    return {"old_text": old, "new_text": new, "expected_matches": count}


def patch(client, headers, target, replacements=None, **options):
    return client.patch(target[0] + '/patch', headers=headers, json={
        "expected_version": 1, "replacements": replacements or [replacement()], **options,
    })


def test_dry_run_then_apply_preserves_history_and_exact_text(client, auth_headers_1, patch_target):
    target = patch_target
    node_service.update_node_ai_summary(target[2], target[3],
                                       db.session.get(Node, target[2]).vault.owner_id, "Summary")
    preview = patch(client, auth_headers_1, target, dry_run=True)
    assert preview.status_code == 200
    data = preview.get_json()
    assert data["version"] == 1 and data["dry_run"] is True
    assert data["matches"][0]["actual_matches"] == 2
    assert "+[[Alpha]] and Beta.\r\n" in data["diff"]
    assert client.get(target[0], headers=auth_headers_1).get_json()["content"] == target[1]
    assert db.session.get(Node, target[2]).summary_is_current is True
    saved = patch(client, auth_headers_1, target)
    assert saved.status_code == 200
    assert saved.get_json()["version"] == 2
    assert "content" not in saved.get_json() and "diff" not in saved.get_json()
    current = client.get(target[0], headers=auth_headers_1).get_json()
    assert current["content"] == target[1].replace("Alpha", "[[Alpha]]")
    assert current["title"] == "Calendar"
    assert db.session.get(Node, target[2]).summary_is_current is False
    versions = Version.query.filter_by(node_id=target[2]).order_by(Version.version).all()
    assert len(versions) == 2 and versions[0].content == target[1]
    assert versions[1].author_id == versions[0].author_id


@pytest.mark.parametrize("dry_run", [False, True])
def test_bad_match_aborts_every_replacement(client, auth_headers_1, patch_target, dry_run):
    response = patch(client, auth_headers_1, patch_target,
                     [replacement(), replacement("missing", "x", 1)], dry_run=dry_run)
    assert response.status_code == 409
    assert [m["actual_matches"] for m in response.get_json()["matches"]] == [2, 0]
    assert client.get(patch_target[0], headers=auth_headers_1).get_json()["content"] == patch_target[1]
    assert Version.query.filter_by(node_id=patch_target[2]).count() == 1


def test_stale_version_rejected_even_for_dry_run(client, auth_headers_1, patch_target):
    assert patch(client, auth_headers_1, patch_target).status_code == 200
    for dry_run in (False, True):
        response = patch(client, auth_headers_1, patch_target, dry_run=dry_run)
        assert response.status_code == 409
        assert response.get_json()["current_version"] == 2
    assert Version.query.filter_by(node_id=patch_target[2]).count() == 2


def test_original_snapshot_prevents_cascading_replacements(client, auth_headers_1, patch_target):
    response = patch(client, auth_headers_1, patch_target,
                     [replacement("Alpha", "Beta", 2), replacement("Beta", "Gamma", 1)])
    assert response.status_code == 200
    content = client.get(patch_target[0], headers=auth_headers_1).get_json()["content"]
    assert content == patch_target[1].replace("Beta", "Gamma").replace("Alpha", "Beta")


def test_overlapping_edits_are_rejected(client, auth_headers_1, patch_target):
    response = patch(client, auth_headers_1, patch_target,
                     [replacement(), replacement("Alpha and", "changed", 1)])
    assert response.status_code == 409
    assert "overlap" in response.get_json()["error"]
    assert Version.query.filter_by(node_id=patch_target[2]).count() == 1


def test_delete_and_noop(client, auth_headers_1, patch_target):
    response = patch(client, auth_headers_1, patch_target, [replacement(new="Alpha")])
    assert response.status_code == 200 and response.get_json()["changed"] is False
    assert response.get_json()["version"] == 1
    response = patch(client, auth_headers_1, patch_target, [replacement(new="")])
    assert response.status_code == 200 and response.get_json()["version"] == 2
    assert client.get(patch_target[0], headers=auth_headers_1).get_json()["content"] == patch_target[1].replace("Alpha", "")


def test_matching_is_literal_case_sensitive_and_unicode_safe(client, auth_headers_1, patch_target):
    content = "a.b A.B aXb ÄÖÜ äöü"
    assert client.put(patch_target[0], headers=auth_headers_1, json={"content": content}).status_code == 200
    response = patch(client, auth_headers_1, patch_target,
                     [replacement("a.b", "[[a.b]]", 1), replacement("ÄÖÜ", "[[ÄÖÜ]]", 1)],
                     expected_version=2)
    assert response.status_code == 200
    assert client.get(patch_target[0], headers=auth_headers_1).get_json()["content"] == "[[a.b]] A.B aXb [[ÄÖÜ]] äöü"


def test_commit_failure_rolls_back_version_and_summary(client, auth_headers_1, patch_target, monkeypatch):
    def failing_commit():
        db.session.flush()
        raise RuntimeError("Simulated commit failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(db.session, "commit", failing_commit)
        response = patch(client, auth_headers_1, patch_target)
    assert response.status_code == 500
    assert Version.query.filter_by(node_id=patch_target[2]).count() == 1
    assert db.session.get(Node, patch_target[2]).current_version == 1
    assert client.get(patch_target[0], headers=auth_headers_1).get_json()["content"] == patch_target[1]


@pytest.mark.parametrize("payload", [None, [], {},
    {"expected_version": True, "replacements": [replacement()]},
    {"expected_version": 0, "replacements": [replacement()]},
    {"expected_version": 1, "replacements": []},
    {"expected_version": 1, "replacements": [replacement(old="")]},
    {"expected_version": 1, "replacements": [replacement(new=None)]},
    {"expected_version": 1, "replacements": [replacement(count=True)]},
    {"expected_version": 1, "replacements": [replacement(count=0)]},
    {"expected_version": 1, "replacements": [replacement()], "dry_run": "false"},
    {"expected_version": 1, "replacements": [replacement()], "content": "accidental"},
])
def test_invalid_payload_is_rejected(client, auth_headers_1, patch_target, payload):
    response = client.patch(patch_target[0] + '/patch', headers=auth_headers_1, json=payload)
    assert response.status_code == 400
    assert Version.query.filter_by(node_id=patch_target[2]).count() == 1


@pytest.mark.parametrize("dry_run", [False, True])
def test_outsiders_and_viewers_cannot_patch(client, auth_headers_2, test_user_2_obj,
                                         patch_target, dry_run):
    assert patch(client, auth_headers_2, patch_target, dry_run=dry_run).status_code == 403
    db.session.add(VaultAccess(vault_id=patch_target[3], user_id=test_user_2_obj.id, role=VaultRole.VIEWER))
    db.session.commit()
    assert patch(client, auth_headers_2, patch_target, dry_run=dry_run).status_code == 403


@pytest.mark.parametrize("dry_run", [False, True])
def test_protected_source_cannot_be_patched(client, auth_headers_1, test_user_1_obj,
                                          patch_target, dry_run):
    connector = ConnectorInstallation(vault_id=patch_target[3], name="Test source",
                                     plugin_name="pdf", created_by_id=test_user_1_obj.id)
    db.session.add(connector)
    db.session.flush()
    db.session.add(SourceItem(connector_id=connector.id, external_id="source", node_id=patch_target[2],
                              content_hash="hash", policy="managed"))
    db.session.commit()
    assert patch(client, auth_headers_1, patch_target, dry_run=dry_run).status_code == 403


def test_simultaneous_patches_allow_exactly_one_writer(app, test_user_1_obj, patch_target):
    user_id = test_user_1_obj.id
    node_id, vault_id = patch_target[2:]
    barrier = threading.Barrier(2)
    db.session.remove()

    def write(new):
        with app.app_context():
            barrier.wait(timeout=5)
            try:
                return node_service.patch_node(node_id, vault_id, user_id, 1, [replacement(new=new)])["version"]
            except NodePatchConflictError as exc:
                return exc.details["current_version"], "conflict"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["First", "Second"]))
    assert results.count(2) == 1 and results.count((2, "conflict")) == 1
    assert Version.query.filter_by(node_id=node_id).count() == 2


def test_full_update_refreshes_stale_session_after_patch(app, test_user_1_obj, patch_target):
    user_id = test_user_1_obj.id
    node_id, vault_id = patch_target[2:]
    loaded = threading.Event()
    proceed = threading.Event()

    def stale_update():
        with app.app_context():
            cached = db.session.get(Node, node_id)
            assert cached.current_version_object.content == patch_target[1]
            loaded.set()
            assert proceed.wait(timeout=5)
            try:
                updated = node_service.update_node(node_id, vault_id, user_id, title="New title")
                return updated.current_version, updated.current_version_object.content
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(stale_update)
        assert loaded.wait(timeout=5)
        try:
            node_service.patch_node(node_id, vault_id, user_id, 1, [replacement()])
        finally:
            proceed.set()
        assert future.result(timeout=5) == (3, patch_target[1].replace("Alpha", "[[Alpha]]"))
