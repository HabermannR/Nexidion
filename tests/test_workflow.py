# tests/test_workflow.py
import pytest


def parse_stream_response(response_bytes):
    """
    Helper function to parse the custom event-stream format from the chat API.
    It extracts session_id, message_id, content, and any error messages.
    """
    session_id = None
    message_id = None
    content = ""
    error = None
    lines = [line for line in response_bytes.decode('utf-8').split('\n') if line]
    for line in lines:
        if line.startswith('session_id:'):
            session_id = line.split(':', 1)[1].strip()
        elif line.startswith('message_id:'):
            message_id = line.split(':', 1)[1].strip()
        elif line.startswith('error:'):
            error = line.split(':', 1)[1].strip()
        else:
            content += line
    return {'session_id': session_id, 'message_id': message_id, 'content': content, 'error': error}


def test_complete_user_workflow(client, db_session, auth_headers_1, auth_headers_2, mocker):
    """
    This test uses function-scoped fixtures from conftest.py.
    The database is clean at the start of this test. All API calls here
    operate on the same isolated database instance for this single test run.
    """
    # === PART 1: USER 1 - VAULT & NODE CREATION ===
    create_vault_res = client.post('/api/vaults', json={'name': "User One's Workflow Vault"}, headers=auth_headers_1)
    assert create_vault_res.status_code == 201
    vault1 = create_vault_res.json
    vault1_id = vault1['id']
    tree_res = client.get(f'/api/nodes/tree?vault_id={vault1_id}', headers=auth_headers_1)
    assert tree_res.status_code == 200
    root_node_id = tree_res.json[0]['id']
    node_a_res = client.post('/api/nodes', json={
        'vault_id': vault1_id, 'title': 'Topic A: Project Goals',
        'content': 'Initial project goals are: 1. Deliver on time. 2. Stay within budget.',
        'parent_id': root_node_id
    }, headers=auth_headers_1)
    assert node_a_res.status_code == 201
    node_a_id = node_a_res.json['id']
    node_b_res = client.post('/api/nodes', json={
        'vault_id': vault1_id, 'title': 'Topic B: Team Roles',
        'content': 'Team roles are not yet defined.', 'parent_id': root_node_id
    }, headers=auth_headers_1)
    assert node_b_res.status_code == 201
    node_b_id = node_b_res.json['id']
    update_res = client.put(f'/api/nodes/{node_a_id}', json={
        'vault_id': vault1_id,
        'content': 'UPDATED project goals: 1. Deliver on time. 2. Stay within budget. 3. Ensure high quality.'
    }, headers=auth_headers_1)
    assert update_res.status_code == 200

    # === PART 2: USER 2 - VAULT CREATION & ACCESS CONTROL ===
    create_vault2_res = client.post('/api/vaults', json={'name': "User Two's Private Space"}, headers=auth_headers_2)
    assert create_vault2_res.status_code == 201
    vault2_id = create_vault2_res.json['id']
    forbidden_res = client.get(f'/api/nodes/tree?vault_id={vault1_id}', headers=auth_headers_2)
    assert forbidden_res.status_code == 403

    # === PART 3: USER 1 - CHAT WORKFLOW (using Mock LLM) ===
    mocker.patch('backend.llm.time.sleep', return_value=None)
    new_chat_res = client.post('/api/chat/sessions/stream', json={
        'vault_id': vault1_id, 'user_input': "Elaborate on goals.",
        'node_ids': [node_a_id], 'model': 'mock'
    }, headers=auth_headers_1)
    assert new_chat_res.status_code == 200
    stream_data_1 = parse_stream_response(new_chat_res.data)
    session_id = stream_data_1['session_id']
    assistant_msg_1_id = stream_data_1['message_id']
    assert session_id is not None and assistant_msg_1_id is not None
    assert "MOCK-MODELL-EINS" in stream_data_1['content']  # Prüft auf die erste Mock-Antwort
    follow_up_res = client.post(f'/api/chat/sessions/{session_id}/messages/stream', json={
        'user_input': "Rephrase for exec summary.",
    }, headers=auth_headers_1)
    assert follow_up_res.status_code == 200
    stream_data_2 = parse_stream_response(follow_up_res.data)
    assistant_msg_2_id = stream_data_2['message_id']
    assert "MOCK-MODELL-EINS" in stream_data_2['content']  # Der Follow-up sollte das gleiche Modell verwenden
    retry_res = client.post(f'/api/chat/sessions/{session_id}/messages/{assistant_msg_2_id}/retry',
                            headers=auth_headers_1, json={})
    assert retry_res.status_code == 200
    assert "MOCK-MODELL-EINS" in retry_res.data.decode('utf-8')

    # === PART 3.5: CHAT MODEL SWITCHING & RETRY LOGIC (JETZT MIT EINDEUTIGEN ASSERTS) ===
    switch_chat_res = client.post('/api/chat/sessions/stream', json={
        'vault_id': vault1_id,
        'user_input': "Initial message with model 'mock'",
        'model': 'mock'
    }, headers=auth_headers_1)
    assert switch_chat_res.status_code == 200
    switch_stream_1 = parse_stream_response(switch_chat_res.data)
    switch_session_id = switch_stream_1['session_id']
    first_assistant_msg_id = switch_stream_1['message_id']
    assert "MOCK-MODELL-EINS" in switch_stream_1['content']  # Korrekt, Antwort von mock

    model_switch_res = client.post(f'/api/chat/sessions/{switch_session_id}/messages/stream', json={
        'user_input': "Second message, switching to model 'mock2'",
        'model': 'mock2'
    }, headers=auth_headers_1)
    assert model_switch_res.status_code == 200
    switch_stream_2 = parse_stream_response(model_switch_res.data)
    assert "MOCK-MODELL-ZWEI" in switch_stream_2['content']  # Korrekt, Antwort von mock2

    retry_first_msg_res = client.post(f'/api/chat/sessions/{switch_session_id}/messages/{first_assistant_msg_id}/retry',
                                      headers=auth_headers_1, json={})
    assert retry_first_msg_res.status_code == 200
    retry_response_text = retry_first_msg_res.data.decode('utf-8')
    # === KORRIGIERTE ASSERTS ===
    assert "MOCK-MODELL-ZWEI" in retry_response_text  # Die Retry-Antwort MUSS von mock2 kommen
    assert "MOCK-MODELL-EINS" not in retry_response_text  # Die Retry-Antwort darf NICHT von mock1 kommen

    # === NEUER TEST-TEIL: RETRY MIT EXPLIZITEM MODELL-OVERRIDE ===
    # Wir nehmen die allererste Nachricht (die ursprünglich von 'mock' kam und gerade von 'mock2' neu generiert wurde)
    # und wiederholen sie NOCHMALS, aber dieses Mal erzwingen wir wieder das ursprüngliche Modell 'mock'.
    print("Testing explicit model override on retry...")
    retry_with_override_res = client.post(
        f'/api/chat/sessions/{switch_session_id}/messages/{first_assistant_msg_id}/retry',
        headers=auth_headers_1,
        json={'model': 'mock'}  # <-- HIER SCHICKEN WIR DAS MODELL EXPLIZIT MIT
    )
    assert retry_with_override_res.status_code == 200
    retry_response_text_2 = retry_with_override_res.data.decode('utf-8')

    # Jetzt muss die Antwort von MOCK-MODELL-EINS kommen, weil wir es erzwungen haben!
    assert "MOCK-MODELL-EINS" in retry_response_text_2
    assert "MOCK-MODELL-ZWEI" not in retry_response_text_2
    print("Explicit model override on retry successful!")

    # === PART 4: USER 1 - NODE PROPOSAL & UPDATE ===
    history_res = client.get(f'/api/chat/sessions/{session_id}', headers=auth_headers_1)
    assert history_res.status_code == 200
    chat_history_str = "\n".join([f"{m['author']}: {m['content']}" for m in history_res.json['messages']])

    # +++ THE FIX: Use the 'mock' model which is now configured for structured responses +++
    propose_res = client.post(f'/api/nodes/{node_b_id}/propose-update', json={
        'vault_id': vault1_id,
        'chat_history': chat_history_str,
        'context_node_ids': [node_a_id],
        'model': 'mock'  # This now works because of the change in llm.py
    }, headers=auth_headers_1)

    assert propose_res.status_code == 200, f"Proposal failed: {propose_res.text}"
    proposal = propose_res.json
    assert proposal['original_content'] == 'Team roles are not yet defined.'
    # We can now assert for the specific mock content
    assert "Project Lead" in proposal['proposed_content']

    apply_update_res = client.put(f'/api/nodes/{node_b_id}', json={
        'vault_id': vault1_id,
        'content': proposal['proposed_content']
    }, headers=auth_headers_1)
    assert apply_update_res.status_code == 200

    get_node_b_res = client.get(f'/api/nodes/{node_b_id}?vault_id={vault1_id}', headers=auth_headers_1)
    assert get_node_b_res.status_code == 200
    node_b_final = get_node_b_res.json
    assert node_b_final['current_version'] == 2
    assert node_b_final['content'] == proposal['proposed_content']