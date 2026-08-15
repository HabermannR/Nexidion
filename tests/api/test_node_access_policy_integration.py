"""End-to-end API coverage for human, LLM and delegated MCP actors."""
import pytest
from flask_jwt_extended import create_access_token
from backend.models import Task

def _headers(app, user_id, actor_type=None):
    claims = {"actor_type": actor_type} if actor_type else None
    with app.app_context():
        token = create_access_token(identity=str(user_id), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def policy_vault(app, client, test_user_1_obj, test_llm_agent_obj, auth_headers_1):
    create_vault = client.post('/api/vaults/', headers=auth_headers_1,
                               json={"name": "Policy integration vault"})
    assert create_vault.status_code == 201
    vault_id = create_vault.get_json()["id"]
    def create(title, parent_id=None):
        response = client.post(
            f'/api/vaults/{vault_id}/nodes/', headers=auth_headers_1,
            json={"title": title, "content": f"content:{title}", "parent_id": parent_id},
        )
        assert response.status_code == 201
        return response.get_json()

    root = create("Policy root")
    child = create("Policy child", root["id"])
    return {
        "vault_id": vault_id,
        "root": root,
        "child": child,
        "human": auth_headers_1,
        "mcp": _headers(app, test_user_1_obj.id, "mcp"),
        "llm": _headers(app, test_llm_agent_obj.id),
    }


def _set_policy(client, env, **policy):
    response = client.patch(
        f'/api/vaults/{env["vault_id"]}/nodes/{env["root"]["id"]}/access-policy',
        headers=env["human"], json={"note": "integration test", **policy},
    )
    assert response.status_code == 200, response.text
    return response.get_json()


def _get(client, env, headers, include=False):
    suffix = '?include_quarantined=true' if include else ''
    return client.get(
        f'/api/vaults/{env["vault_id"]}/nodes/{env["child"]["id"]}{suffix}',
        headers=headers,
    )


def _write(client, env, headers):
    return client.put(
        f'/api/vaults/{env["vault_id"]}/nodes/{env["child"]["id"]}',
        headers=headers, json={"content": "attempted update"},
    )


def _tree_ids(items):
    result = set()
    for item in items:
        result.add(item["id"])
        result.update(_tree_ids(item.get("children", [])))
    return result


def test_quarantine_human_reads_but_ai_requires_explicit_opt_in(client, policy_vault):
    env = policy_vault
    _set_policy(client, env, ai_read="explicit_only", ai_write_locked=True,
                human_write_locked=False)

    assert _get(client, env, env["human"]).status_code == 200
    assert _get(client, env, env["mcp"]).status_code == 403
    assert _get(client, env, env["llm"]).status_code == 403
    assert _get(client, env, env["mcp"], include=True).status_code == 200
    assert _get(client, env, env["llm"], include=True).status_code == 200
    assert _write(client, env, env["mcp"]).status_code == 403
    assert _write(client, env, env["llm"]).status_code == 403

    default_tree = client.get(
        f'/api/vaults/{env["vault_id"]}/nodes/?format=tree', headers=env["mcp"]
    ).get_json()
    explicit_tree = client.get(
        f'/api/vaults/{env["vault_id"]}/nodes/?format=tree&include_quarantined=true',
        headers=env["mcp"],
    ).get_json()
    assert env["root"]["id"] not in _tree_ids(default_tree)
    assert env["child"]["id"] in _tree_ids(explicit_tree)

    # Clearing the parent never clears the quarantine stamped onto descendants.
    _set_policy(client, env, ai_read="allow", ai_write_locked=False,
                human_write_locked=False)
    assert _get(client, env, env["mcp"]).status_code == 403
    assert _get(client, env, env["mcp"], include=True).status_code == 200


def test_ai_invisible_has_no_override_but_human_can_read(client, policy_vault):
    env = policy_vault
    _set_policy(client, env, ai_read="deny", ai_write_locked=True,
                human_write_locked=False)

    assert _get(client, env, env["human"]).status_code == 200
    assert _get(client, env, env["mcp"], include=True).status_code == 403
    assert _get(client, env, env["llm"], include=True).status_code == 403

    autocomplete_url = (
        f'/api/vaults/{env["vault_id"]}/nodes/search?q=Policy%20child'
    )
    assert client.get(autocomplete_url, headers=env["human"]).get_json()
    assert client.get(autocomplete_url, headers=env["mcp"]).get_json() == []

    resolve_url = f'/api/vaults/{env["vault_id"]}/nodes/resolve-links'
    targets = [env["child"]["id"], env["child"]["title"]]
    human_results = client.post(
        resolve_url, headers=env["human"], json={"targets": targets}
    ).get_json()["results"]
    mcp_results = client.post(
        resolve_url, headers=env["mcp"],
        json={"targets": targets, "include_quarantined": True},
    ).get_json()["results"]
    assert all(item["status"] == "resolved" for item in human_results.values())
    assert all(item["status"] == "unresolved" for item in mcp_results.values())


def test_quarantine_link_discovery_requires_explicit_opt_in(client, policy_vault):
    env = policy_vault
    _set_policy(client, env, ai_read="explicit_only", ai_write_locked=True,
                human_write_locked=False)

    search_url = f'/api/vaults/{env["vault_id"]}/nodes/search?q=Policy%20child'
    assert client.get(search_url, headers=env["mcp"]).get_json() == []
    assert client.get(
        f'{search_url}&include_quarantined=true', headers=env["mcp"]
    ).get_json()[0]["id"] == env["child"]["id"]

    resolve_url = f'/api/vaults/{env["vault_id"]}/nodes/resolve-links'
    target = env["child"]["id"]
    hidden = client.post(
        resolve_url, headers=env["mcp"], json={"targets": [target]}
    ).get_json()["results"]
    visible = client.post(
        resolve_url, headers=env["mcp"],
        json={"targets": [target], "include_quarantined": True},
    ).get_json()["results"]
    assert hidden[target]["status"] == "unresolved"
    assert visible[target]["status"] == "resolved"


def test_ai_write_lock_allows_human_update_only(client, policy_vault):
    env = policy_vault
    _set_policy(client, env, ai_read="allow", ai_write_locked=True,
                human_write_locked=False)

    assert _write(client, env, env["human"]).status_code == 200
    assert _write(client, env, env["mcp"]).status_code == 403
    assert _write(client, env, env["llm"]).status_code == 403


def test_inherited_human_write_lock_blocks_every_actor(client, policy_vault):
    env = policy_vault
    payload = _set_policy(client, env, ai_read="allow", ai_write_locked=False,
                          human_write_locked=True)
    assert payload["access_policy"]["ai_write_locked"] is True

    assert _get(client, env, env["human"]).status_code == 200
    assert _get(client, env, env["mcp"]).status_code == 200
    assert _get(client, env, env["llm"]).status_code == 200
    assert _write(client, env, env["human"]).status_code == 403
    assert _write(client, env, env["mcp"]).status_code == 403
    assert _write(client, env, env["llm"]).status_code == 403


def test_ai_invisible_is_hidden_from_task_history_and_provenance(
        client, policy_vault, db_session):
    env = policy_vault
    _set_policy(client, env, ai_read="deny", ai_write_locked=True,
                human_write_locked=False)
    task = Task(
        vault_id=env["vault_id"], instruction="Inspect the protected node",
        context_node_ids=[env["child"]["id"]], status="completed",
    )
    db_session.session.add(task)
    db_session.session.commit()

    assert client.get(f'/api/tasks/{task.id}', headers=env["human"]).status_code == 200
    assert client.get(f'/api/tasks/{task.id}', headers=env["mcp"]).status_code == 403
    mcp_tasks = client.get(
        f'/api/tasks?vault_id={env["vault_id"]}', headers=env["mcp"]
    ).get_json()
    assert task.id not in {item["id"] for item in mcp_tasks}

    provenance_url = f'/api/connectors/provenance/nodes/{env["child"]["id"]}'
    assert client.get(provenance_url, headers=env["human"]).status_code == 200
    assert client.get(provenance_url, headers=env["mcp"]).status_code == 403


def test_filtered_mcp_tree_supports_conditional_requests(client, policy_vault):
    env = policy_vault
    _set_policy(client, env, ai_read="deny", ai_write_locked=True,
                human_write_locked=False)
    url = f'/api/vaults/{env["vault_id"]}/nodes/?format=tree'
    first = client.get(url, headers=env["mcp"])
    assert first.status_code == 200
    etag = first.headers["ETag"]
    second = client.get(url, headers={**env["mcp"], "If-None-Match": etag})
    assert second.status_code == 304
