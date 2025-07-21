# tests/test_workflow.py

import json
import pytest


def parse_sse_response(response_bytes):
    """
    Neue Hilfsfunktion zum Parsen von standardkonformen Server-Sent Events (SSE).
    Sammelt Inhalte und extrahiert Daten aus JSON-Payloads.
    """
    decoded_lines = response_bytes.decode('utf-8').strip().split('\n')

    events = []
    full_content = ""

    current_event = {}
    for line in decoded_lines:
        if not line:  # Leere Zeile beendet ein Event
            if current_event:
                events.append(current_event)
                # Extrahiere den Inhalt für den einfachen Zugriff
                if 'data' in current_event and isinstance(current_event['data'], dict) and 'content' in current_event[
                    'data']:
                    full_content += current_event['data']['content']
            current_event = {}
            continue

        key, value = line.split(':', 1)
        value = value.strip()

        if key == 'event':
            current_event['event'] = value
        elif key == 'data':
            try:
                current_event['data'] = json.loads(value)
            except json.JSONDecodeError:
                current_event['data'] = value  # Falls es kein JSON ist

    if current_event:  # Füge das letzte Event hinzu, falls die Antwort nicht mit \n\n endet
        events.append(current_event)
        if 'data' in current_event and isinstance(current_event['data'], dict) and 'content' in current_event['data']:
            full_content += current_event['data']['content']

    return {'events': events, 'full_content': full_content}


def test_full_workflow_v2_apis(client, test_user_1_obj, test_user_2_obj, mocker):
    """
    Simuliert einen kompletten Benutzer-Workflow mit den neuen V2-APIs für
    Auth, Vaults, Nodes und Chat, inklusive der neuen Versions-API.
    """
    # === PART 0: USER LOGIN (V2 API) ===
    # ... (unverändert) ...
    login_res_1 = client.post('/api/auth/login',
                              json={'username': test_user_1_obj.username, 'password': 'password123'})
    auth_headers_1 = {'Authorization': f"Bearer {login_res_1.json['access_token']}"}
    login_res_2 = client.post('/api/auth/login',
                              json={'username': test_user_2_obj.username, 'password': 'password456'})
    auth_headers_2 = {'Authorization': f"Bearer {login_res_2.json['access_token']}"}

    # === PART 1: USER 1 - VAULT & NODE CREATION (V2 APIs) ===
    # ... (größtenteils unverändert, aber mit neuen Assertions) ...
    create_vault_res = client.post('/api/vaults/',
                                   json={'name': "User One's Workflow Vault"},
                                   headers=auth_headers_1)
    vault1 = create_vault_res.json
    vault1_id = vault1['id']
    tree_res = client.get(f'/api/vaults/{vault1_id}/nodes/', headers=auth_headers_1)
    root_node_id = tree_res.json[0]['id']
    node_a_res = client.post(f'/api/vaults/{vault1_id}/nodes/', json={
        'title': 'Topic A: Project Goals',
        'content': 'Initial project goals are: 1. Deliver on time. 2. Stay within budget.',
        'parent_id': root_node_id
    }, headers=auth_headers_1)
    node_a = node_a_res.json
    node_a_id = node_a['id']
    node_b_res = client.post(f'/api/vaults/{vault1_id}/nodes/', json={
        'title': 'Topic B: Team Roles',
        'content': 'Team roles are not yet defined.',
        'parent_id': root_node_id
    }, headers=auth_headers_1)
    node_b = node_b_res.json
    node_b_id = node_b['id']

    # Update Node A, um eine zweite Version zu erzeugen
    update_res = client.put(f'/api/vaults/{vault1_id}/nodes/{node_a_id}', json={
        'content': 'UPDATED project goals: 1. Deliver on time. 2. Stay within budget. 3. Ensure high quality.'
    }, headers=auth_headers_1)
    assert update_res.status_code == 200

    # =========================================================================
    # NEUER TEST-SCHRITT 1.5: ÜBERPRÜFE NODE-STRUKTUR UND VERSIONEN API
    # =========================================================================
    # Holen des "leichten" Node A
    get_node_a_res = client.get(f'/api/vaults/{vault1_id}/nodes/{node_a_id}', headers=auth_headers_1)
    assert get_node_a_res.status_code == 200
    node_a_light = get_node_a_res.json

    # Prüfe die neue "leichte" Struktur
    assert 'versions' not in node_a_light  # Der Versionsverlauf darf nicht mehr direkt enthalten sein
    assert node_a_light['has_versions'] is True
    assert node_a_light['version_count'] == 2
    assert node_a_light[
               'content'] == 'UPDATED project goals: 1. Deliver on time. 2. Stay within budget. 3. Ensure high quality.'

    # Holen des Versionsverlaufs über den neuen Endpunkt
    versions_res = client.get(f'/api/vaults/{vault1_id}/nodes/{node_a_id}/versions', headers=auth_headers_1)
    assert versions_res.status_code == 200
    versions_data = versions_res.json

    assert isinstance(versions_data, list)
    assert len(versions_data) == 2
    assert versions_data[0]['version'] == 2  # Neueste zuerst
    assert versions_data[0][
               'content'] == 'UPDATED project goals: 1. Deliver on time. 2. Stay within budget. 3. Ensure high quality.'
    assert versions_data[1]['version'] == 1
    assert versions_data[1]['content'] == 'Initial project goals are: 1. Deliver on time. 2. Stay within budget.'
    # =========================================================================

    # === PART 2: USER 2 - ACCESS CONTROL CHECK (V2 APIs) ===
    # ... (unverändert) ...
    forbidden_res = client.get(f'/api/vaults/{vault1_id}/nodes/', headers=auth_headers_2)
    assert forbidden_res.status_code == 403

    # === PART 3 & 4: CHAT & PROPOSAL WORKFLOW (V2 APIs) ===
    # ... (unverändert) ...
    new_session_res = client.post(f'/api/vaults/{vault1_id}/sessions/', headers=auth_headers_1)
    session_id = new_session_res.json['id']
    mocker.patch('backend.services.chat_service.llm_service.generate_response_stream',
                 return_value=iter(["Antwort ", "zu den Zielen."]))
    client.post(f'/api/vaults/{vault1_id}/sessions/{session_id}/messages', json={
        'user_input': "Elaborate on goals.",
        'node_ids': [node_a_id],
        'model': 'mock'
    }, headers=auth_headers_1)

    mock_proposal_content = "Based on our discussion, team roles are: Lead, Dev, QA."
    mocker.patch(
        'backend.services.chat_service.propose_node_update_from_chat',
        return_value={
            "original_content": node_b['content'],
            "proposed_content": mock_proposal_content
        }
    )
    propose_res = client.post(f'/api/vaults/{vault1_id}/nodes/{node_b_id}/propose-update', json={
        'session_id': session_id,
        'context_node_ids': [node_a_id],
        'model': 'mock'
    }, headers=auth_headers_1)
    proposal = propose_res.json

    apply_update_res = client.put(f'/api/vaults/{vault1_id}/nodes/{node_b_id}', json={
        'content': proposal['proposed_content']
    }, headers=auth_headers_1)
    assert apply_update_res.status_code == 200

    # =========================================================================
    # NEUER TEST-SCHRITT 4.5: FINALEN ZUSTAND VON NODE B ÜBERPRÜFEN
    # =========================================================================
    get_node_b_res = client.get(f'/api/vaults/{vault1_id}/nodes/{node_b_id}', headers=auth_headers_1)
    assert get_node_b_res.status_code == 200
    node_b_final = get_node_b_res.json

    # Wir prüfen die neuen Felder.
    assert node_b_final['version_count'] == 2  # Initial (1) + Proposal-Update (2)
    assert node_b_final['content'] == mock_proposal_content

    # Optional, aber gut: Prüfe auch hier den Verlauf
    versions_b_res = client.get(f'/api/vaults/{vault1_id}/nodes/{node_b_id}/versions', headers=auth_headers_1)
    assert versions_b_res.status_code == 200
    versions_b_data = versions_b_res.json
    assert len(versions_b_data) == 2
    assert versions_b_data[0]['content'] == mock_proposal_content
    assert versions_b_data[1]['content'] == 'Team roles are not yet defined.'
    # =========================================================================