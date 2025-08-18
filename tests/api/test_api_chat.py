# tests/test_api_chat.py

from backend.models import ChatSession, ChatMessage

def test_api_add_message_and_stream(client, auth_headers_1, test_vault_1_obj, db_session, mocker):
    """
    Testet den neuen Endpunkt zum Hinzufügen einer Nachricht und zum Streamen der Antwort.
    """
    # 1. ARRANGE
    # Der API-Endpunkt prüft jetzt, ob die Session existiert, bevor er den Service aufruft.
    # Wir müssen sie also in der Test-DB anlegen.
    session_id = "test-session-for-streaming"
    vault_id = test_vault_1_obj.id
    user_id_for_test = 1 # Annahme: auth_headers_1 gehört zu User 1

    session_in_db = ChatSession(
        id=session_id,
        vault_id=vault_id,
        owner_id=user_id_for_test
    )
    db_session.session.add(session_in_db)
    db_session.session.commit()
    # =================================================================

    model_to_use = "claude-3-haiku"

    # Der Mock bleibt derselbe, da wir immer noch nicht den echten LLM-Service aufrufen wollen.
    mock_stream_service = mocker.patch(
        'backend.services.chat_service.stream_new_message',
        return_value=iter(['event: assistant_message_start\n\n', 'data: {"content": "Antwort vom Mock"}\n\n'])
    )

    payload = {
        "user_input": "Jetzt bitte mit einem anderen Modell antworten.",
        "node_ids": ["node-1", "node-2"],
        "model": model_to_use
    }

    # Baue den neuen Endpunkt zusammen (verwende die vault_id aus der Fixture)
    endpoint = f"/api/vaults/{vault_id}/sessions/{session_id}/messages"

    # 2. ACT
    response = client.post(endpoint, headers=auth_headers_1, json=payload)

    # 3. ASSERT
    # Dieser Assert sollte jetzt erfolgreich sein, da die Vorab-Prüfung die Session findet.
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    assert 'Antwort vom Mock' in response.data.decode('utf-8')

    # KORREKTUR: Fügen Sie das zusätzliche Argument hinzu, das der API-Endpunkt immer übergibt.
    mock_stream_service.assert_called_once_with(
        session_id=session_id,
        user_id=user_id_for_test,
        user_input=payload['user_input'],
        model=payload['model'],
        node_ids=payload['node_ids'],
        client_message_id=None,
        title_model=None
    )


def test_api_retry_message(client, auth_headers, mocker):
    """
    Testet den neuen API-Endpunkt für das Wiederholen einer Nachrichtengenerierung.
    """
    # 1. ARRANGE
    vault_id = 1
    session_id = "test-session-for-retry"
    message_id = "msg-abc-123"  # message_id ist jetzt ein String

    mock_response_stream = iter(["Die neue, korrigierte ", "Antwort kommt hier."])

    # Mocke die korrekte Service-Funktion
    mock_retry_stream_service = mocker.patch(
        'backend.services.chat_service.stream_retry_message',
        return_value=mock_response_stream
    )

    # Baue den neuen Endpunkt zusammen
    endpoint = f"/api/vaults/{vault_id}/sessions/{session_id}/messages/{message_id}/retry"

    # 2. ACT
    # Der Body ist leer, da kein Modell-Override stattfindet
    response = client.post(endpoint, headers=auth_headers, json={})

    # 3. ASSERT
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    assert response.data.decode('utf-8') == "Die neue, korrigierte Antwort kommt hier."

    # Überprüfe den Service-Aufruf
    mock_retry_stream_service.assert_called_once_with(
        session_id=session_id,
        message_id=message_id,
        user_id=1,  # Annahme: User ID 1
        model=None  # Kein Modell im JSON-Body übergeben
    )


def test_api_retry_message_with_model_override(client, auth_headers, mocker):
    """
    Testet den Retry-Endpunkt, wenn ein Modell-Override im Body mitgegeben wird.
    """
    # 1. ARRANGE
    vault_id = 1
    session_id = "test-session-for-retry-override"
    message_id = "msg-xyz-789"  # message_id ist ein String
    model_to_use = "gpt-4o-mini"

    # Mocke die korrekte Service-Funktion
    mock_retry_stream_service = mocker.patch(
        'backend.services.chat_service.stream_retry_message',
        return_value=iter(['data: {"content": "Antwort von GPT-4o Mini."}\n\n'])
    )

    # Baue den neuen Endpunkt zusammen
    endpoint = f"/api/vaults/{vault_id}/sessions/{session_id}/messages/{message_id}/retry"

    # 2. ACT
    response = client.post(endpoint, headers=auth_headers, json={'model': model_to_use})

    # 3. ASSERT
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    assert "Antwort von GPT-4o Mini." in response.data.decode('utf-8')

    # Überprüfe den Service-Aufruf mit dem Modell-Override
    mock_retry_stream_service.assert_called_once_with(
        session_id=session_id,
        message_id=message_id,
        user_id=1,  # Annahme: User ID 1
        model=model_to_use
    )

def test_get_sessions_success(client, auth_headers_1, test_vault_1_obj, db_session):
    """Testet den erfolgreichen Abruf von Chat-Sessions."""
    # Arrange: Erstelle zwei Sessions im Vault von User 1
    session1 = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id, title="Session Eins")
    session2 = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id, title="Session Zwei")
    db_session.session.add_all([session1, session2])
    db_session.session.commit()

    # Act
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/sessions/', headers=auth_headers_1)

    # Assert
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {s['title'] for s in data} == {"Session Eins", "Session Zwei"}

def test_get_sessions_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Testet, dass User 2 nicht auf die Sessions von User 1 zugreifen kann."""
    # Act
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/sessions/', headers=auth_headers_2)
    # Assert
    assert response.status_code == 403 # Forbidden

def test_get_sessions_for_nonexistent_vault(client, auth_headers_1):
    """Testet den Abruf von Sessions aus einem nicht existierenden Vault."""
    # Act
    response = client.get('/api/vaults/999/sessions/', headers=auth_headers_1)
    # Assert
    assert response.status_code == 404 # Not Found


def test_delete_session_success(client, auth_headers_1, test_vault_1_obj, db_session):
    """Testet das erfolgreiche Löschen einer Session."""
    # Arrange
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    db_session.session.add(session)
    db_session.session.commit()
    session_id = session.id

    # Act
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session_id}', headers=auth_headers_1)

    # Assert
    assert response.status_code == 204 # No Content
    # Überprüfe, ob die Session wirklich aus der DB entfernt wurde
    deleted_session = db_session.session.get(ChatSession, session_id)
    assert deleted_session is None

def test_delete_session_permission_denied(client, auth_headers_2, test_vault_1_obj, db_session):
    """Testet, dass User 2 nicht die Session von User 1 löschen kann."""
    # Arrange
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    db_session.session.add(session)
    db_session.session.commit()

    # Act
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}', headers=auth_headers_2)

    # Assert
    assert response.status_code == 403


def test_delete_message_success(client, auth_headers_1, test_vault_1_obj, db_session):
    """Testet das erfolgreiche Soft-Löschen einer Nachricht."""
    # Arrange
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    # KORREKTUR: Füge einen Wert für das obligatorische Feld `sort_order` hinzu.
    message = ChatMessage(
        session=session,
        role='user',
        content='delete me',
        author_id=test_vault_1_obj.owner_id,
        sort_order=1  # <-- DIES IST DIE ERGÄNZUNG
    )
    db_session.session.add_all([session, message])
    db_session.session.commit() # Dieser Commit wird jetzt erfolgreich sein.
    session_id = session.id
    message_id = message.id

    # Act
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session_id}/messages/{message_id}', headers=auth_headers_1)

    # Assert
    assert response.status_code == 204
    db_session.session.refresh(message)
    assert message.status == 'deleted'

def test_delete_message_not_found(client, auth_headers_1, test_vault_1_obj, db_session):
    """Testet das Löschen einer nicht existierenden Nachricht."""
    # Arrange
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    db_session.session.add(session)
    db_session.session.commit()

    # Act
    response = client.delete(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}/messages/non-existent-id', headers=auth_headers_1)

    # Assert
    # KORREKTUR: Erwarte 204, da die Funktion idempotent ist und keinen Fehler wirft.
    assert response.status_code == 204


def test_get_history_permission_denied(client, auth_headers_2, test_vault_1_obj, db_session):
    """
    Testet GET /sessions/<id> - Fehlerfall: Zugriff verweigert.
    User 2 versucht, auf eine Session von User 1 zuzugreifen.
    """
    # Arrange: Erstelle eine Session, die User 1 gehört
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    db_session.session.add(session)
    db_session.session.commit()

    # Act
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}', headers=auth_headers_2)

    # Assert
    assert response.status_code == 403  # Forbidden


def test_get_history_not_found(client, auth_headers_1, test_vault_1_obj):
    """
    Testet GET /sessions/<id> - Fehlerfall: Session nicht gefunden.
    """
    # Act
    response = client.get(f'/api/vaults/{test_vault_1_obj.id}/sessions/non-existent-session-id', headers=auth_headers_1)

    # Assert
    assert response.status_code == 404  # Not Found


def test_add_message_to_session_of_other_user_fails(client, auth_headers_2, test_vault_1_obj, db_session):
    """
    Testet POST /sessions/<id>/messages - Fehlerfall: Zugriff verweigert.
    """
    # Arrange
    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_vault_1_obj.owner_id)
    db_session.session.add(session)
    db_session.session.commit()
    payload = {"user_input": "hacking attempt"}

    # Act
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}/messages',
                           headers=auth_headers_2, json=payload)

    # Assert
    # Der Fehler wird jetzt synchron ausgelöst, bevor der Stream beginnt.
    # Wir können den Statuscode und die Daten direkt prüfen.
    assert response.status_code == 403
    # Die Antwort ist jetzt ein SSE-Fehler-Event, das wir parsen können.
    assert b'error' in response.data
    assert b'You do not have permission to access this vault.' in response.data
    # ==========================


def test_update_session_title_success(client, auth_headers_1, test_vault_1_obj, db_session):
    """
    Testet den erfolgreichen PUT-Request zum Aktualisieren eines Session-Titels.
    """
    # 1. ARRANGE
    # Erstelle eine Session, die dem anfragenden User (User 1) gehört.
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_vault_1_obj.owner_id,
        title="Alter Titel"
    )
    db_session.session.add(session)
    db_session.session.commit()

    endpoint = f"/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}"
    payload = {"title": "Neuer, aktualisierter Titel"}

    # 2. ACT
    response = client.put(endpoint, headers=auth_headers_1, json=payload)

    # 3. ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == "Neuer, aktualisierter Titel"
    assert data['id'] == session.id

    # Überprüfe zusätzlich, dass die Änderung auch wirklich in der Datenbank persistiert wurde.
    db_session.session.refresh(session)
    assert session.title == "Neuer, aktualisierter Titel"


def test_update_session_title_missing_title(client, auth_headers_1, test_vault_1_obj, db_session):
    """
    Testet, dass ein 400 Bad Request zurückgegeben wird, wenn der Titel im Payload fehlt.
    """
    # 1. ARRANGE
    # Wir brauchen trotzdem eine existierende Session, damit der Fehler nicht schon bei 404 auftritt.
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_vault_1_obj.owner_id,
        title="Ein Titel"
    )
    db_session.session.add(session)
    db_session.session.commit()

    endpoint = f"/api/vaults/{test_vault_1_obj.id}/sessions/{session.id}"
    invalid_payload = {"some_other_key": "some_value"}  # Absichtlich ohne 'title'

    # 2. ACT
    response = client.put(endpoint, headers=auth_headers_1, json=invalid_payload)

    # 3. ASSERT
    assert response.status_code == 400
    data = response.get_json()
    assert "Title is required" in data.get('error', '')


def test_update_session_title_permission_denied(client, auth_headers_2, test_vault_1_obj, db_session):
    """
    Testet, dass ein 403 Forbidden zurückgegeben wird, wenn ein User versucht,
    eine fremde Session zu bearbeiten.
    """
    # 1. ARRANGE
    # Erstelle eine Session, die User 1 gehört.
    session_of_user_1 = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_vault_1_obj.owner_id,  # owner_id ist 1
        title="Titel von User 1"
    )
    db_session.session.add(session_of_user_1)
    db_session.session.commit()

    endpoint = f"/api/vaults/{test_vault_1_obj.id}/sessions/{session_of_user_1.id}"
    payload = {"title": "Versuchter Hack"}

    # 2. ACT
    # User 2 (mit auth_headers_2) versucht, die Session von User 1 zu ändern.
    response = client.put(endpoint, headers=auth_headers_2, json=payload)

    # 3. ASSERT
    assert response.status_code == 403

    # Überprüfe, dass der Titel in der Datenbank NICHT geändert wurde.
    db_session.session.refresh(session_of_user_1)
    assert session_of_user_1.title == "Titel von User 1"


def test_update_session_title_not_found(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass ein 404 Not Found zurückgegeben wird, wenn die Session-ID nicht existiert.
    """
    # 1. ARRANGE
    non_existent_session_id = "abc-123-def-456"
    endpoint = f"/api/vaults/{test_vault_1_obj.id}/sessions/{non_existent_session_id}"
    payload = {"title": "Titel für eine Geister-Session"}

    # 2. ACT
    response = client.put(endpoint, headers=auth_headers_1, json=payload)

    # 3. ASSERT
    assert response.status_code == 404