"""Agent-native retrieval: search snippets, node-scoped assets, context bundles."""
import io

import pytest
from PIL import Image
from flask_jwt_extended import create_access_token


def _headers(app, user_id, actor_type=None):
    claims = {"actor_type": actor_type} if actor_type else None
    with app.app_context():
        token = create_access_token(identity=str(user_id), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _png(size=(1600, 1200), color='blue'):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, format='PNG')
    return stream.getvalue()


@pytest.fixture()
def env(app, client, test_user_1_obj, auth_headers_1, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    vault = client.post('/api/vaults/', headers=auth_headers_1, json={"name": "Retrieval vault"})
    assert vault.status_code == 201
    vault_id = vault.get_json()["id"]

    def create(title, content="", parent_id=None):
        response = client.post(f'/api/vaults/{vault_id}/nodes/', headers=auth_headers_1,
                               json={"title": title, "content": content, "parent_id": parent_id})
        assert response.status_code == 201, response.text
        return response.get_json()

    def update(node_id, content):
        response = client.put(f'/api/vaults/{vault_id}/nodes/{node_id}', headers=auth_headers_1,
                              json={"content": content})
        assert response.status_code == 200, response.text

    def policy(node_id, **values):
        response = client.patch(f'/api/vaults/{vault_id}/nodes/{node_id}/access-policy',
                                headers=auth_headers_1, json={"note": "test", **values})
        assert response.status_code == 200, response.text

    def upload(payload):
        response = client.post(f'/api/vaults/{vault_id}/assets', headers=auth_headers_1,
                               data={'file': (io.BytesIO(payload), 'figure.png')},
                               content_type='multipart/form-data')
        assert response.status_code == 201, response.text
        return response.get_json()

    return {"vault_id": vault_id, "create": create, "update": update, "policy": policy,
            "upload": upload, "human": auth_headers_1,
            "mcp": _headers(app, test_user_1_obj.id, "mcp")}


# ------------------------------------------------------------------ search

def _search(client, env, headers, q, **params):
    query = {"q": q, "snippets": "true", **params}
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/full-search',
                          headers=headers, query_string=query)
    assert response.status_code == 200, response.text
    return response.get_json()["results"]


def test_search_snippets_are_verbatim_with_offsets_and_heading_path(client, env):
    filler = "Unrelated preamble sentence. " * 60
    content = (f"# Handbook\n\n{filler}\n\n## Maintenance\n\n### Pumps\n\n"
               "Replace the impeller seal every 400 operating hours.\n\n" + filler)
    node = env["create"]("Plant handbook", content)

    [hit] = _search(client, env, env["mcp"], "impeller seal", include_content="false")

    assert hit["id"] == node["id"]
    assert "content" not in hit
    assert hit["match_sources"] == ["content"]
    assert hit["summary_only"] is False
    assert hit["version"] == 1
    [match] = hit["matches"]
    assert "impeller seal" in match["text"]
    assert content[match["start_char"]:match["end_char"]] == match["text"]
    assert match["heading_path"] == ["Handbook", "Maintenance", "Pumps"]
    assert match["version"] == 1
    assert len(match["text"]) <= 600 + 2 * 60


def test_search_reports_summary_only_hits(client, env):
    node = env["create"]("Quarterly note", "Nothing relevant in the body.")
    response = client.patch(f'/api/vaults/{env["vault_id"]}/nodes/{node["id"]}/summary',
                            headers=env["human"], json={"ai_summary": "Discusses turbines at length."})
    assert response.status_code == 200, response.text

    [hit] = _search(client, env, env["mcp"], "turbines")

    assert hit["summary_only"] is True
    assert hit["match_sources"] == ["summary"]
    assert hit["matches"] == []


def test_search_snippets_never_come_from_hidden_nodes(client, env):
    visible = env["create"]("Visible", "The zephyr protocol is documented here.")
    hidden = env["create"]("Hidden", "The zephyr protocol secret details.")
    env["policy"](hidden["id"], ai_read="deny", ai_write_locked=True, human_write_locked=False)

    ai_hits = _search(client, env, env["mcp"], "zephyr")
    human_hits = _search(client, env, env["human"], "zephyr")

    assert [hit["id"] for hit in ai_hits] == [visible["id"]]
    assert all("secret" not in m["text"] for hit in ai_hits for m in hit["matches"])
    assert {hit["id"] for hit in human_hits} == {visible["id"], hidden["id"]}


def test_search_can_be_limited_to_a_subtree(client, env):
    root = env["create"]("Project A")
    inside = env["create"]("Inside", "gearbox ratio", root["id"])
    env["create"]("Outside", "gearbox ratio")

    hits = _search(client, env, env["mcp"], "gearbox", subtree_root_id=root["id"])

    assert [hit["id"] for hit in hits] == [inside["id"]]


def test_plain_search_response_is_unchanged_by_default(client, env):
    env["create"]("Legacy", "legacy search body")
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/full-search',
                          headers=env["human"], query_string={"q": "legacy"})
    [hit] = response.get_json()["results"]
    assert hit["content"] == "legacy search body"
    assert "matches" not in hit


# ------------------------------------------------------------------ assets

def test_node_assets_are_listed_and_served_through_the_node(client, env):
    asset = env["upload"](_png())
    node = env["create"]("Diagram node",
                         f'Intro\n\n![Pump cross-section]({asset["url"]} "Figure 1")\n')

    listing = client.get(f'/api/vaults/{env["vault_id"]}/nodes/{node["id"]}/assets', headers=env["mcp"])
    assert listing.status_code == 200, listing.text
    [item] = listing.get_json()["assets"]
    assert item["asset_id"] == asset["id"]
    assert item["alt_text"] == "Pump cross-section"
    assert item["caption"] == "Figure 1"
    assert item["mime_type"] == "image/png"
    assert (item["width"], item["height"]) == (1600, 1200)
    assert item["embedded_in_current_content"] is True
    assert item["available"] is True and item["byte_size"] > 0

    base = f'/api/vaults/{env["vault_id"]}/nodes/{node["id"]}/assets/{asset["id"]}'
    original = client.get(base, headers=env["mcp"])
    assert original.status_code == 200 and original.mimetype == 'image/png'
    preview = client.get(base, headers=env["mcp"], query_string={"representation": "preview", "max_px": 400})
    assert preview.status_code == 200
    assert Image.open(io.BytesIO(preview.data)).size == (400, 300)


def test_node_asset_requires_the_node_to_embed_it(client, env):
    asset = env["upload"](_png(color='red'))
    node = env["create"]("No images here", "plain text")
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/{node["id"]}/assets/{asset["id"]}',
                          headers=env["mcp"])
    assert response.status_code == 404


def test_hidden_node_assets_are_not_reachable_by_ai_even_by_direct_url(client, env):
    asset = env["upload"](_png(color='green'))
    node = env["create"]("Private scan", f'![secret]({asset["url"]})')
    env["policy"](node["id"], ai_read="deny", ai_write_locked=True, human_write_locked=False)

    via_node = client.get(f'/api/vaults/{env["vault_id"]}/nodes/{node["id"]}/assets', headers=env["mcp"])
    assert via_node.status_code == 403
    direct = client.get(asset["url"], headers=env["mcp"])
    assert direct.status_code == 404
    assert client.get(asset["url"], headers=env["human"]).status_code == 200

    # Once a readable node also embeds it, the direct URL works for AI again.
    env["create"]("Public copy", f'![public]({asset["url"]})')
    assert client.get(asset["url"], headers=env["mcp"]).status_code == 200


# ------------------------------------------------------------------ context bundles

def _bundle(client, env, node_id, headers=None, **params):
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/{node_id}/context',
                          headers=headers or env["mcp"], query_string=params)
    assert response.status_code == 200, response.text
    return response.get_json()


def test_context_bundle_collects_graph_neighbourhood_with_provenance(client, env):
    parent = env["create"]("Parent topic", "parent body")
    detail = env["create"]("Detail", "detail body")
    by_title = env["create"]("Glossary", "glossary body")
    root = env["create"]("Lead node",
                         f"See [[Detail|{detail['id']}]] and the [[Glossary]] for terms.",
                         parent["id"])
    child = env["create"]("Child evidence", "child body", root["id"])
    source = env["create"]("Primary source", f"This supports [[Lead|{root['id']}]] directly.")

    bundle = _bundle(client, env, root["id"])

    assert bundle["root"]["id"] == root["id"]
    assert bundle["root"]["content_source"] == "original"
    relations = [(item["relation"], item["id"]) for item in bundle["items"]]
    assert relations == [("parent", parent["id"]), ("child", child["id"]),
                         ("outlink", detail["id"]), ("outlink", by_title["id"]),
                         ("backlink", source["id"])]
    assert all(item["distance"] == 1 and item["relation_from"] == root["id"] for item in bundle["items"])
    backlink = bundle["items"][-1]
    assert "This supports" in backlink["link_context"]
    assert backlink["link_context_source"] == source["id"]
    assert bundle["truncated"] is False


def test_context_bundle_does_not_leak_hidden_backlinks(client, env):
    root = env["create"]("Open node", "open")
    hidden = env["create"]("Diary", f"mentions [[Open node|{root['id']}]]")
    env["policy"](hidden["id"], ai_read="deny", ai_write_locked=True, human_write_locked=False)

    bundle = _bundle(client, env, root["id"])
    assert bundle["items"] == []
    assert bundle["omitted_count"] == 0
    assert "Diary" not in str(bundle)

    human = _bundle(client, env, root["id"], headers=env["human"])
    assert [item["id"] for item in human["items"]] == [hidden["id"]]


def test_context_bundle_is_bounded_and_says_so(client, env):
    root = env["create"]("Hub", "hub")
    for index in range(5):
        env["create"](f"Spoke {index}", "x" * 500, root["id"])

    limited = _bundle(client, env, root["id"], max_items=2)
    assert len(limited["items"]) == 2
    assert limited["truncated"] is True
    assert limited["omitted_count"] == 3

    budget = _bundle(client, env, root["id"], max_chars=700)
    assert sum(len(item.get("content", "")) for item in budget["items"]) + len(budget["root"]["content"]) <= 700
    assert budget["content_budget_exhausted"] is True
    assert budget["truncated"] is True


def test_context_bundle_depth_two_reaches_second_ring_once(client, env):
    root = env["create"]("A", "")
    b = env["create"]("B", f"back to [[A|{root['id']}]]", root["id"])
    c = env["create"]("C", "", b["id"])

    bundle = _bundle(client, env, root["id"], depth=2)
    ids = [(item["id"], item["distance"]) for item in bundle["items"]]
    assert ids == [(b["id"], 1), (c["id"], 2)]
    # B is A's child *and* links back to A; both edges are reported.
    [other] = bundle["items"][0]["other_relations"]
    assert other["relation"] == "backlink"
    assert "back to" in other["link_context"]


def test_context_bundle_refuses_hidden_root(client, env):
    root = env["create"]("Sealed", "")
    env["policy"](root["id"], ai_read="deny", ai_write_locked=True, human_write_locked=False)
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/{root["id"]}/context', headers=env["mcp"])
    assert response.status_code == 403


def test_search_context_bundle_seeds_from_search_and_expands_once(client, env):
    shared = env["create"]("Shared source", "primary data")
    first = env["create"]("Flood model 2024", f"The flood model uses [[Shared source|{shared['id']}]].")
    second = env["create"]("Flood correction", f"Correction to the flood estimate, see [[Shared source|{shared['id']}]].")
    env["create"]("Unrelated", "nothing to see")

    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/context-search', headers=env["mcp"],
                          query_string={"q": "flood", "seed_limit": 5})
    assert response.status_code == 200, response.text
    bundle = response.get_json()

    seeds = [item for item in bundle["items"] if item["relation"] == "seed"]
    assert {seed["id"] for seed in seeds} == {first["id"], second["id"]}
    assert all(seed["matches"] and seed["distance"] == 0 for seed in seeds)
    neighbours = [item for item in bundle["items"] if item["relation"] != "seed"]
    assert [item["id"] for item in neighbours] == [shared["id"]]  # reached twice, listed once
    assert neighbours[0]["relation"] == "outlink"
    assert bundle["seed_count"] == 2


def test_search_context_bundle_requires_a_query(client, env):
    response = client.get(f'/api/vaults/{env["vault_id"]}/nodes/context-search', headers=env["mcp"])
    assert response.status_code == 400
