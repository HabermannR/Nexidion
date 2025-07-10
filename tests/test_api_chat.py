# tests/test_api_chat.py

import pytest
from unittest.mock import ANY, call # call importieren, falls benötigt

def test_api_can_switch_model_mid_conversation(client, auth_headers, mocker):
    """
    Testet den API-Flow für einen Modellwechsel in einer bestehenden Konversation.
    """
    # ... (Dieser Test ist in Ordnung)
    session_id = "test-session-for-switching"
    model = "mock"
    mock_stream_in_session = mocker.patch(
        'backend.chatservice.stream_message_in_session',
        return_value=iter([f"session_id:{session_id}\n\n", "Antwort vom Mock"])
    )
    payload = {
        "user_input": "Jetzt bitte mit einem anderen Modell antworten.",
        "node_ids": [],
        "model": model
    }
    endpoint = f"/api/chat/sessions/{session_id}/messages/stream"
    response = client.post(endpoint, headers=auth_headers, json=payload)
    assert response.status_code == 200
    mock_stream_in_session.assert_called_once()
    call_args = mock_stream_in_session.call_args
    assert call_args.kwargs['session_id'] == session_id
    assert call_args.kwargs['model'] == model
    assert call_args.kwargs['user_id'] == ANY


def test_api_retry_message(client, auth_headers, mocker):
    """
    Tests the API endpoint for retrying a specific message generation.
    """
    # ... (Dieser Test ist in Ordnung, vorausgesetzt message_id ist ein int)
    session_id = "test-session-for-retry"
    message_id = 5 # Korrekt als int
    mock_response_stream = iter(["Die neue, korrigierte ", "Antwort kommt hier."])
    mock_retry_stream = mocker.patch(
        'backend.chatservice.retry_specific_message_stream',
        return_value=mock_response_stream
    )
    endpoint = f"/api/chat/sessions/{session_id}/messages/{message_id}/retry"
    response = client.post(endpoint, headers=auth_headers, json={})
    assert response.status_code == 200
    assert response.data.decode('utf-8') == "Die neue, korrigierte Antwort kommt hier."
    expected_user_id = 1
    mock_retry_stream.assert_called_with(
        session_id=session_id,
        message_id=message_id,
        user_id=expected_user_id,
        model=None
    )

def test_api_retry_message_with_model_override(client, auth_headers, mocker):
    """
    Tests the retry endpoint specifically when a model override is provided.
    """
    # 1. ARRANGE
    session_id = "test-session-for-retry-override"
    # === DER ENTSCHEIDENDE FIX: Sicherstellen, dass dies ein Integer ist ===
    message_id = 6
    model_to_use = "gpt-4o-mini"

    mock_retry_stream = mocker.patch(
        'backend.chatservice.retry_specific_message_stream',
        return_value=iter(["Antwort von GPT-4o Mini."])
    )
    endpoint = f"/api/chat/sessions/{session_id}/messages/{message_id}/retry"

    # 2. ACT
    response = client.post(endpoint, headers=auth_headers, json={'model': model_to_use})

    # 3. ASSERT
    assert response.status_code == 200
    assert response.data.decode('utf-8') == "Antwort von GPT-4o Mini."
    expected_user_id = 1
    mock_retry_stream.assert_called_with(
        session_id=session_id,
        message_id=message_id, # Vergleicht jetzt int(6) mit int(6)
        user_id=expected_user_id,
        model=model_to_use
    )
