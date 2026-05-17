import pytest
from backend.models import DemoState


@pytest.fixture
def demo_locked_setup(client, db_session, test_user_1_obj, test_vault_1_obj, test_node_obj):
    """
    Setzt den Vault-Besitzer auf READ_ONLY Demo-Modus und
    gibt die notwendigen Headers und IDs für die Tests zurück.
    """
    test_user_1_obj.is_guest = True
    test_user_1_obj.demo_state = DemoState.READ_ONLY
    db_session.session.commit()

    login_res = client.post('/api/auth/login', json={'username': test_user_1_obj.username, 'password': 'password123'})
    token = login_res.get_json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    return {
        'headers': headers,
        'vault_id': test_vault_1_obj.id,
        'node_id': test_node_obj.id
    }


class TestDemoModeLockedState:

    def test_node_operations_are_locked(self, client, demo_locked_setup):
        """Testet, dass im READ_ONLY Demo-State KEINE Node-Operationen erlaubt sind."""
        headers = demo_locked_setup['headers']
        vault_id = demo_locked_setup['vault_id']
        node_id = demo_locked_setup['node_id']

        # 1. Create Node (POST)
        res = client.post(f'/api/vaults/{vault_id}/nodes/', headers=headers, json={'title': 'Test'})
        assert res.status_code == 423

        # 2. Update Node (PUT)
        res = client.put(f'/api/vaults/{vault_id}/nodes/{node_id}', headers=headers, json={'title': 'Test'})
        assert res.status_code == 423

        # 3. Move Node (PATCH)
        res = client.patch(f'/api/vaults/{vault_id}/nodes/{node_id}/move', headers=headers, json={'parent_id': None})
        assert res.status_code == 423

        # 4. Icon (PATCH)
        res = client.patch(f'/api/vaults/{vault_id}/nodes/{node_id}/icon', headers=headers, json={'icon': 'bxs-folder'})
        assert res.status_code == 423

        # 5. AI Summary (PATCH)
        res = client.patch(f'/api/vaults/{vault_id}/nodes/{node_id}/summary', headers=headers,
                           json={'ai_summary': 'Test'})
        assert res.status_code == 423

        # 6. Delete Node (DELETE)
        res = client.delete(f'/api/vaults/{vault_id}/nodes/{node_id}', headers=headers)
        assert res.status_code == 423

    def test_vault_operations_are_locked(self, client, demo_locked_setup):
        """Testet, dass im READ_ONLY Demo-State KEINE Vault-Operationen erlaubt sind."""
        headers = demo_locked_setup['headers']
        vault_id = demo_locked_setup['vault_id']

        # 1. Create Vault (POST)
        res = client.post('/api/vaults/', headers=headers, json={'name': 'Hacked Vault'})
        assert res.status_code == 423

        # 2. Rename Vault (PUT)
        res = client.put(f'/api/vaults/{vault_id}', headers=headers, json={'name': 'Hacked Name'})
        assert res.status_code == 423

        # 3. Delete Vault (DELETE)
        res = client.delete(f'/api/vaults/{vault_id}', headers=headers)
        assert res.status_code == 423