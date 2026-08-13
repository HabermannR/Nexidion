from backend.models import db, Node, VaultAccess, VaultRole, Version


def _source(vault, user):
    node = Node(vault_id=vault.id, current_version=1)
    db.session.add(node)
    db.session.flush()
    db.session.add(Version(node_id=node.id, version=1, title='Copy me',
                           content='content', author_id=user.id))
    db.session.commit()
    return node


def test_copy_node_api_contract(client, auth_headers_1, test_user_1_obj,
                                test_vault_1_obj, test_vault_2_obj):
    db.session.add(VaultAccess(user_id=test_user_1_obj.id,
                              vault_id=test_vault_2_obj.id, role=VaultRole.EDITOR))
    db.session.commit()
    source = _source(test_vault_1_obj, test_user_1_obj)
    response = client.post(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{source.id}/copy',
        headers=auth_headers_1, json={'destination_vault_id': test_vault_2_obj.id})
    assert response.status_code == 201
    body = response.get_json()
    assert body['source_node_id'] == source.id
    assert body['recursive'] is True
    assert body['copied_count'] == 1
    assert body['uuid_map'][source.id] == body['root_node_id']
    assert body['managed_images'] == 'rejected_if_present'


def test_copy_node_api_rejects_unreadable_source_vault(
        client, auth_headers_1, test_user_1_obj, test_user_2_obj,
        test_vault_1_obj, test_vault_2_obj):
    source = _source(test_vault_2_obj, test_user_2_obj)
    response = client.post(
        f'/api/vaults/{test_vault_2_obj.id}/nodes/{source.id}/copy',
        headers=auth_headers_1, json={'destination_vault_id': test_vault_1_obj.id})
    assert response.status_code == 403


def test_copy_node_api_validates_body(client, auth_headers_1, test_node_obj,
                                      test_vault_1_obj):
    url = f'/api/vaults/{test_vault_1_obj.id}/nodes/{test_node_obj.id}/copy'
    assert client.post(url, headers=auth_headers_1, json={}).status_code == 400
    assert client.post(url, headers=auth_headers_1,
                       json={'destination_vault_id': test_vault_1_obj.id,
                             'recursive': 'yes'}).status_code == 400
