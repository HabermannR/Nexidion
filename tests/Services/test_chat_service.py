import pytest
import json
from backend.services import chat_service, node_service
from backend.models import User, Vault, ChatSession, ChatMessage, Node


def test_list_sessions(test_user_1_obj: User, test_vault_1_obj: Vault):
    """
    Testet das Auflisten von Chat-Sessions über den chat_service.
    """
    # 1. Setup: Erstelle eine Session über den Service.
    #    Das ist besser, als die DB direkt zu manipulieren, da wir so
    #    die Logik von `create_new_session` gleich mit abdecken.
    #    Der Standardtitel laut deinem Code ist "New Chat".
    chat_service.create_new_session(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )

    # 2. Ausführung: Rufe die zu testende Funktion auf.
    sessions = chat_service.list_sessions(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )

    # 3. Überprüfung: Die Assertions sind fast identisch.
    assert len(sessions) == 1
    assert isinstance(sessions[0], dict)  # Der Service gibt Dictionaries zurück
    assert sessions[0]['title'] == "New Chat"
    assert sessions[0]['vault_id'] == test_vault_1_obj.id
    assert sessions[0]['owner_id'] == test_user_1_obj.id


def test_get_session_history_not_found(test_user_1_obj: User):
    """
    Testet den Abruf einer nicht existierenden Session über den chat_service.
    """
    # Die Logik hier bleibt fast gleich, da der Service den gleichen Fehler auslöst.
    # Wir rufen nur die neue Funktion auf.

    # 1. Setup: (Keines nötig, wir wollen ja einen Fehler provozieren)

    # 2. Ausführung & Überprüfung:
    with pytest.raises(ValueError, match="Chat session with ID not-found-id not found."):
        chat_service.get_session_history(
            session_id="not-found-id",
            user_id=test_user_1_obj.id
        )


def test_get_session_history_permission_denied(test_user_1_obj: User, test_user_2_obj: User, test_vault_2_obj: Vault):
    """Testet, dass User 1 nicht auf die Session von User 2 zugreifen kann."""
    # 1. ARRANGE: Erstelle eine Session für User 2 über den Service
    session_user2 = chat_service.create_new_session(
        vault_id=test_vault_2_obj.id,
        user_id=test_user_2_obj.id
    )

    # Annahme: User 1 hat keinen Zugriff auf test_vault_2_obj.
    # Der Fehler sollte von `_verify_vault_access` kommen.
    # Wir nehmen an, dieser wirft einen PermissionError.
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        # 2. ACT & ASSERT
        chat_service.get_session_history(session_user2.id, test_user_1_obj.id)


def test_delete_session_not_found(test_user_1_obj: User):
    """Testet das Löschen einer nicht existierenden Session über den Service."""
    # Der Service wirft einen ValueError, wenn die Session nicht gefunden wird.
    with pytest.raises(ValueError, match="Chat session with ID not-found-id not found."):
        chat_service.delete_session("not-found-id", test_user_1_obj.id)


def test_delete_session_permission_denied(test_user_1_obj: User, test_user_2_obj: User, test_vault_2_obj: Vault):
    """Testet, dass User 1 nicht die Session von User 2 löschen kann."""
    # 1. ARRANGE: Erstelle eine Session für User 2
    session_user2 = chat_service.create_new_session(
        vault_id=test_vault_2_obj.id,
        user_id=test_user_2_obj.id
    )

    # 2. ACT & ASSERT
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        chat_service.delete_session(session_user2.id, test_user_1_obj.id)


def test_delete_session_success(test_user_1_obj: User, test_vault_1_obj: Vault, db_session):
    """Testet das erfolgreiche Löschen einer Chat-Session über den Service."""
    # 1. ARRANGE: Erstelle eine Session über den Service
    session = chat_service.create_new_session(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )
    session_id = session.id
    assert db_session.session.get(ChatSession, session_id) is not None

    # 2. ACT: Rufe die Löschfunktion im Service auf
    chat_service.delete_session(session_id=session_id, user_id=test_user_1_obj.id)

    # 3. ASSERT: Überprüfe, ob die Session aus der DB entfernt wurde
    assert db_session.session.get(ChatSession, session_id) is None


def test_update_session_title_success(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob der Titel einer Session erfolgreich aktualisiert und gespeichert wird.
    """
    # 1. ARRANGE
    # Erstelle eine Session in der DB
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id,
        title="Alter Titel"
    )
    db_session.session.add(session)
    db_session.session.commit()

    new_title = "Brandneuer Titel"

    # 2. ACT
    # Rufe die Service-Funktion direkt auf
    updated_session = chat_service.update_session_title(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        new_title=new_title
    )

    # 3. ASSERT
    # Überprüfe das zurückgegebene Objekt
    assert isinstance(updated_session, ChatSession)
    assert updated_session.title == new_title
    assert updated_session.id == session.id

    # Überprüfe den Zustand in der Datenbank explizit
    db_session.session.refresh(session)
    assert session.title == new_title


def test_update_session_title_raises_error_for_wrong_user(test_user_1_obj, test_user_2_obj, test_vault_1_obj, db_session):
    """
    Testet, ob ein PermissionError ausgelöst wird, wenn ein nicht berechtigter User
    versucht, den Titel zu ändern. Dies testet indirekt, dass _verify_session_access
    korrekt aufgerufen wird.
    """
    # 1. ARRANGE
    # Session gehört User 1
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id,
        title="Titel von User 1"
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT & 3. ASSERT
    # User 2 versucht den Titel zu ändern
    with pytest.raises(PermissionError):
        chat_service.update_session_title(
            session_id=session.id,
            user_id=test_user_2_obj.id, # <-- Falscher User
            new_title="Hacking Versuch"
        )


def test_get_session_history_success_and_sorted(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob der Verlauf einer Session korrekt und nach `sort_order` sortiert zurückgegeben wird.
    """
    # 1. ARRANGE
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    # Erstelle Nachrichten in "falscher" Reihenfolge, um die Sortierung zu testen
    msg3 = ChatMessage(session=session, role='assistant', content='Antwort', author_id=99, sort_order=3)
    msg1 = ChatMessage(session=session, role='user', content='Frage', author_id=test_user_1_obj.id, sort_order=1)
    msg2 = ChatMessage(session=session, role='assistant', content='Präzisierende Frage', author_id=99, sort_order=2)

    db_session.session.add_all([session, msg3, msg1, msg2])
    db_session.session.commit()

    # 2. ACT
    history = chat_service.get_session_history(
        session_id=session.id,
        user_id=test_user_1_obj.id
    )

    # 3. ASSERT
    assert isinstance(history, dict)
    assert history['id'] == session.id
    assert 'messages' in history

    messages = history['messages']
    assert len(messages) == 3

    # Überprüfe die korrekte Sortierung basierend auf `sort_order`
    assert messages[0]['content'] == 'Frage'
    assert messages[0]['sort_order'] == 1

    assert messages[1]['content'] == 'Präzisierende Frage'
    assert messages[1]['sort_order'] == 2

    assert messages[2]['content'] == 'Antwort'
    assert messages[2]['sort_order'] == 3


def test_get_session_history_empty_session(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob eine leere Nachrichtenliste für eine neue Session zurückgegeben wird.
    """
    # 1. ARRANGE
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT
    history = chat_service.get_session_history(
        session_id=session.id,
        user_id=test_user_1_obj.id
    )

    # 3. ASSERT
    assert history['id'] == session.id
    assert isinstance(history['messages'], list)
    assert len(history['messages']) == 0


def test_get_session_history_raises_error_for_wrong_user(test_user_1_obj, test_user_2_obj, test_vault_1_obj,
                                                         db_session):
    """
    Testet, ob ein PermissionError ausgelöst wird, wenn ein nicht berechtigter User
    versucht, den Verlauf abzurufen.
    """
    # 1. ARRANGE
    # Session gehört User 1
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT & 3. ASSERT
    # User 2 versucht, den Verlauf abzurufen
    with pytest.raises(PermissionError):
        chat_service.get_session_history(
            session_id=session.id,
            user_id=test_user_2_obj.id  # <-- Falscher User
        )


# tests/services/test_chat_service.py

# =========================================================================
# TESTS FÜR stream_new_message (mit gemocktem LLM)
# =========================================================================

def test_stream_new_message_happy_path(test_user_1_obj, test_vault_1_obj, db_session, mocker):
    """
    Testet den "Happy Path" von `stream_new_message`.
    - User-Nachricht wird gespeichert.
    - LLM wird aufgerufen.
    - Assistenten-Nachricht wird mit der LLM-Antwort gespeichert.
    - Titel der Session wird generiert und gespeichert.
    """
    # 1. ARRANGE
    # Mocke den LLM-Service, um einen deterministischen Stream zurückzugeben
    mock_llm_stream = iter(["Hello, ", "this is ", "a response."])
    mocker.patch('backend.services.llm_service.generate_response_stream', return_value=mock_llm_stream)
    mocker.patch('backend.services.llm_service.generate_chat_title', return_value="A Generated Title")
    mocker.patch('backend.services.llm_service.get_llm_user', return_value=test_user_1_obj)  # Simpler Mock

    session = chat_service.create_new_session(test_vault_1_obj.id, test_user_1_obj.id)

    # 2. ACT
    stream_generator = chat_service.stream_new_message(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        user_input="Test input",
        model="mock_model",
        node_ids=[]
    )
    # Konsumiere den Generator vollständig
    events = list(stream_generator)

    # 3. ASSERT
    # Überprüfe die Datenbank
    db_session.session.refresh(session)
    assert session.title == "A Generated Title"

    messages = db_session.session.query(ChatMessage).filter_by(session_id=session.id).order_by(
        ChatMessage.sort_order).all()
    assert len(messages) == 2

    user_msg = messages[0]
    assert user_msg.role == 'user'
    assert user_msg.content == "Test input"
    assert user_msg.sort_order == 1

    # Wir parsen die Events und prüfen ihren Inhalt, nicht den rohen String.

    # 1. Filtere nur die 'data' Events, die einen Token enthalten
    token_events = []
    for e in events:
        if e.startswith('data:'):
            try:
                data = json.loads(e[len('data:'):].strip())
                if 'token' in data:
                    token_events.append(data)
            except json.JSONDecodeError:
                continue

    # 2. Prüfe, ob wir die erwarteten Token-Events haben
    assert len(token_events) == 3, "Sollte drei Token-Chunks empfangen haben"

    # 3. Prüfe den Inhalt der einzelnen Events
    assert token_events[0]['token'] == "Hello, "
    assert token_events[1]['token'] == "this is "
    assert token_events[2]['token'] == "a response."

    # Überprüfe die SSE-Events (optional, aber gut für Vollständigkeit)
    assert any("event: user_message" in e for e in events)
    assert any("event: assistant_message_start" in e for e in events)
    assert any("event: assistant_message_end" in e for e in events)
    assert any("event: session_updated" in e for e in events)


def test_stream_new_message_handles_llm_error_gracefully(test_user_1_obj, test_vault_1_obj, db_session, mocker):
    """
    Testet, dass `stream_new_message` eine Teil-Antwort speichert, wenn der LLM-Stream mittendrin abbricht.
    """

    # 1. ARRANGE
    # Simuliere einen Stream, der nach zwei Chunks eine Exception wirft
    def faulty_stream_generator():
        yield "Partial "
        yield "response, "
        raise ValueError("LLM API failed!")

    mocker.patch('backend.services.llm_service.generate_response_stream', return_value=faulty_stream_generator())
    mocker.patch('backend.services.llm_service.get_llm_user', return_value=test_user_1_obj)

    session = chat_service.create_new_session(test_vault_1_obj.id, test_user_1_obj.id)

    # 2. ACT
    stream_generator = chat_service.stream_new_message(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        user_input="Another test",
        model="mock_model",
        node_ids=[]
    )
    events = list(stream_generator)

    # 3. ASSERT
    # Überprüfe den DB-Zustand: Die Teil-Antwort sollte gespeichert sein!
    messages = db_session.session.query(ChatMessage).filter_by(session_id=session.id).order_by(
        ChatMessage.sort_order).all()
    assert len(messages) == 2

    assistant_msg = messages[1]
    assert assistant_msg.role == 'assistant'
    assert assistant_msg.content == "Partial response,"  # Nur die erfolgreichen Chunks

    # Überprüfe, dass ein Fehler-Event gesendet wurde
    assert any("event: error" in e for e in events)
    assert not any("event: assistant_message_end" in e for e in events)  # Der End-Event darf nicht kommen


# =========================================================================
# TESTS FÜR stream_retry_message (mit gemocktem LLM)
# =========================================================================

def test_stream_retry_message_replaces_existing_response(test_user_1_obj, test_vault_1_obj, db_session, mocker):
    """
    Testet Fall A von `stream_retry_message`: Eine existierende Antwort wird als 'retried' markiert
    und durch eine neue ersetzt.
    """
    # 1. ARRANGE
    mocker.patch('backend.services.llm_service.generate_response_stream',
                 return_value=iter(["New ", "better ", "response."]))
    mocker.patch('backend.services.llm_service.get_llm_user', return_value=test_user_1_obj)

    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_user_1_obj.id)
    msg1 = ChatMessage(session=session, role='user', content='Frage', author_id=test_user_1_obj.id, sort_order=1)
    msg2_old = ChatMessage(session=session, role='assistant', content='Alte Antwort', author_id=99, sort_order=2)
    db_session.session.add_all([session, msg1, msg2_old])
    db_session.session.commit()

    # 2. ACT
    stream_generator = chat_service.stream_retry_message(
        session_id=session.id,
        message_id=msg1.id,  # Wir "retryen" die User-Nachricht
        user_id=test_user_1_obj.id,
        model="mock_model"
    )
    list(stream_generator)  # Konsumiere den Generator

    # 3. ASSERT
    # Holt ALLE Nachrichten, unabhängig vom Status, um die Zählung zu überprüfen
    all_messages = db_session.session.query(ChatMessage).filter_by(session_id=session.id).order_by(
        ChatMessage.sort_order).all()

    # === KORRIGIERTE ASSERTION ===
    assert len(all_messages) == 3, "Sollte jetzt 3 Nachrichten insgesamt haben: 1 User, 1 retried, 1 active assistant"

    # Finde die Nachrichten nach Status und Rolle für detailliertere Prüfungen
    user_msg = next((m for m in all_messages if m.role == 'user'), None)
    retried_msg = next((m for m in all_messages if m.status == 'retried'), None)
    active_assistant_msg = next((m for m in all_messages if m.status == 'active' and m.role == 'assistant'), None)

    # Prüfe die User-Nachricht
    assert user_msg is not None
    assert user_msg.id == msg1.id

    # Prüfe die alte, "retried" Nachricht
    assert retried_msg is not None
    assert retried_msg.id == msg2_old.id
    assert retried_msg.content == 'Alte Antwort'

    # Prüfe die neue, aktive Nachricht
    assert active_assistant_msg is not None
    assert active_assistant_msg.content == 'New better response.'
    assert active_assistant_msg.sort_order == 2  # Behält die gleiche `sort_order`


def test_stream_retry_message_inserts_and_shifts(test_user_1_obj, test_vault_1_obj, db_session, mocker):
    """
    Testet Fall B von `stream_retry_message`: Eine neue Antwort wird eingefügt
    und nachfolgende Nachrichten werden verschoben.
    """
    # 1. ARRANGE
    mocker.patch('backend.services.llm_service.generate_response_stream', return_value=iter(["Retry ", "response."]))
    mocker.patch('backend.services.llm_service.get_llm_user', return_value=test_user_1_obj)

    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_user_1_obj.id)
    msg1 = ChatMessage(session=session, role='user', content='Frage 1', author_id=test_user_1_obj.id, sort_order=1)
    msg2 = ChatMessage(session=session, role='user', content='Frage 2', author_id=test_user_1_obj.id, sort_order=2)
    msg3_old = ChatMessage(session=session, role='assistant', content='Antwort auf Frage 2', author_id=99, sort_order=3)
    db_session.session.add_all([session, msg1, msg2, msg3_old])
    db_session.session.commit()

    # 2. ACT
    # Wir "retryen" die erste User-Nachricht. Es gibt keine Assistenten-Antwort an Position 2.
    stream_generator = chat_service.stream_retry_message(
        session_id=session.id,
        message_id=msg1.id,
        user_id=test_user_1_obj.id,
        model="mock_model"
    )
    list(stream_generator)

    # 3. ASSERT
    messages = db_session.session.query(ChatMessage).filter_by(session_id=session.id).order_by(
        ChatMessage.sort_order).all()
    assert len(messages) == 4  # Jetzt haben wir eine Nachricht mehr

    # Finde die neue Nachricht
    new_msg = messages[1]  # Sollte an Position 2 (index 1) sein
    assert new_msg.role == 'assistant'
    assert new_msg.content == 'Retry response.'
    assert new_msg.sort_order == 2

    # Überprüfe, ob die nachfolgenden Nachrichten verschoben wurden
    shifted_msg2 = messages[2]
    assert shifted_msg2.id == msg2.id
    assert shifted_msg2.sort_order == 3  # Wurde von 2 nach 3 verschoben

    shifted_msg3 = messages[3]
    assert shifted_msg3.id == msg3_old.id
    assert shifted_msg3.sort_order == 4  # Wurde von 3 nach 4 verschoben


# =========================================================================
# TESTS FÜR propose_node_update_from_chat (mit gemocktem LLM)
# =========================================================================

@pytest.fixture
def proposal_test_setup(db_session, test_user_1_obj, test_vault_1_obj):
    """
    Ein dediziertes Fixture, das die DB-Objekte für die Proposal-Tests erstellt.
    Macht die Tests sauberer und wiederverwendbar.
    """
    # === KORREKTUR HIER ===
    # Finde den Root-Node (der automatisch beim Erstellen des Vaults angelegt wird)
    # mit einer direkten DB-Abfrage. Das ist der robusteste Weg im Test-Setup.
    root_node = db_session.session.query(Node).filter_by(
        vault_id=test_vault_1_obj.id,
        parent_id=None
    ).one_or_none()

    # Ein Vault sollte immer genau einen Root-Node haben.
    assert root_node is not None, "Root-Node konnte für den Test-Vault nicht gefunden werden."

    # Erstelle die restlichen Objekte wie gehabt
    context_node = node_service.create_node(
        title="Project Requirements",
        content="The project must be completed by Q4.",
        parent_id=root_node.id, vault_id=test_vault_1_obj.id, author_id=test_user_1_obj.id
    )

    target_node = node_service.create_node(
        title="Team Allocation",
        content="Current team: Alice (Lead).",
        parent_id=root_node.id, vault_id=test_vault_1_obj.id, author_id=test_user_1_obj.id
    )

    session = ChatSession(vault_id=test_vault_1_obj.id, owner_id=test_user_1_obj.id)
    msg1 = ChatMessage(session=session, role='user', content="Who else should be on the team?",
                       author_id=test_user_1_obj.id, sort_order=1)
    msg2 = ChatMessage(session=session, role='assistant', content="We should add Bob and Carol.",
                       author_id=test_user_1_obj.id, sort_order=2)

    db_session.session.add_all([session, msg1, msg2])
    db_session.session.commit()

    return {
        "user_id": test_user_1_obj.id,
        "session_id": session.id,
        "target_node_id": target_node.id,
        "context_node_ids": [context_node.id]
    }


def test_propose_node_update_happy_path(proposal_setup, mocker):
    """
    Testet den "Happy Path" von `propose_node_update_from_chat`.
    Stellt sicher, dass der LLM-Service mit dem korrekt zusammengebauten Prompt aufgerufen wird.
    """
    # 1. ARRANGE
    # ----------
    # Das komplette Datenbank-Setup kommt jetzt aus der 'proposal_setup'-Fixture.
    # Wir müssen nur noch den LLM-Service mocken.
    mock_llm_response = "This is the new proposed content from the mocked LLM."
    mock_generate_structured = mocker.patch(
        'backend.services.llm_service.generate_structured_response',
        return_value=mock_llm_response
    )

    # 2. ACT
    # ------
    # Wir rufen den Service mit den Daten aus der Fixture auf.
    result = chat_service.propose_node_update_from_chat(
        target_node_id=proposal_setup["target_node_id"],
        session_id=proposal_setup["session_id"],
        context_node_ids=proposal_setup["context_node_ids"],
        model="mock_model",
        user_id=proposal_setup["user_id"]
    )

    # 3. ASSERT
    # ---------
    # Überprüfe das Ergebnis der Funktion
    assert result["original_content"] == "Current team: Alice (Lead)."
    assert result["proposed_content"] == mock_llm_response

    # Überprüfe, ob der LLM-Service korrekt aufgerufen wurde
    mock_generate_structured.assert_called_once()

    # Detaillierte Prüfung des Prompts, der an das LLM gesendet wurde
    call_args, call_kwargs = mock_generate_structured.call_args
    user_prompt = call_kwargs.get("user_prompt", "")

    # Prüfe, ob alle wichtigen Teile im Prompt enthalten sind
    assert "Original Content of the Node to Update (Title: Team Allocation)" in user_prompt
    assert "Current team: Alice (Lead)." in user_prompt
    assert "Full Chat History" in user_prompt
    assert "User: Who else should be on the team?" in user_prompt
    assert "Assistant: We should add Bob and Carol." in user_prompt
    assert "Additional Context from Nodes: Project Requirements" in user_prompt
    assert "The project must be completed by Q4." in user_prompt
    assert "Now, please analyze all the information" in user_prompt


def test_propose_node_update_raises_error_if_node_not_found(proposal_setup):
    """
    Testet, dass ein `ValueError` ausgelöst wird, wenn der Ziel-Node nicht existiert.
    """
    # 1. ARRANGE (Setup wird durch die 'proposal_setup' Fixture bereitgestellt)

    # 2. ACT & 3. ASSERT
    with pytest.raises(ValueError, match="Target node non-existent-id not found or access denied."):
        chat_service.propose_node_update_from_chat(
            target_node_id="non-existent-id",  # Eine ID, die garantiert nicht existiert
            session_id=proposal_setup["session_id"],
            context_node_ids=proposal_setup["context_node_ids"],
            model="mock_model",
            user_id=proposal_setup["user_id"]
        )


def test_propose_node_update_raises_error_for_wrong_user(proposal_setup, test_user_2_obj):
    """
    Testet, dass ein `PermissionError` ausgelöst wird, wenn ein nicht berechtigter
    Benutzer versucht, einen Vorschlag zu generieren.
    """
    # 1. ARRANGE (Setup wird durch 'proposal_setup' bereitgestellt; alles gehört User 1)

    # 2. ACT & 3. ASSERT
    # User 2 versucht, den Vorschlag für die Daten von User 1 zu generieren
    with pytest.raises(PermissionError):
        chat_service.propose_node_update_from_chat(
            target_node_id=proposal_setup["target_node_id"],
            session_id=proposal_setup["session_id"],
            context_node_ids=proposal_setup["context_node_ids"],
            model="mock_model",
            user_id=test_user_2_obj.id  # <-- Hier wird der falsche User verwendet
        )