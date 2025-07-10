# tests/test_chatservice.py

import pytest
from unittest.mock import MagicMock, patch, call

# Stellen Sie sicher, dass die Importe zu Ihrer Projektstruktur passen
from backend.models import ChatSession, ChatMessage, User, Version
from backend import chatservice
from backend.models import db # Import db für das Mocking von Transaktionen


def test_stream_new_chat_session_logic(mocker, app, db_session):
    """
    Testet die interne Logik von `chatservice.stream_new_chat_session`.
    (ANGEPASST an die neue Logik mit message_id)
    """
    # 1. ARRANGE
    user_id, vault_id, user_input, model = 1, 1, "Das ist mein Input", "mock-model"

    # --- Datenbank-Mocks ---
    mock_session_instance = MagicMock(spec=ChatSession, id="session-123", vault_id=1)
    mock_create_session = mocker.patch('backend.database.create_chat_session', return_value=mock_session_instance)

    mock_assistant_message = MagicMock(spec=ChatMessage, id="msg-abc-123")
    # FIX: Assign the patch object to mock_add_message to check its calls later
    mock_add_message = mocker.patch('backend.database.add_chat_message', return_value=mock_assistant_message)

    mocker.patch('backend.chatservice.db.session.get', return_value=mock_assistant_message)

    history_with_user_message = {'messages': [{'role': 'user', 'content': user_input}]}
    mocker.patch('backend.database.get_chat_session_history', return_value=history_with_user_message)
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': '', 'titles': []})
    mock_commit = mocker.patch('backend.chatservice.db.session.commit')

    # --- LLM-Mocks ---
    mock_llm_user_instance = MagicMock(spec=User, id=999)
    mocker.patch('backend.llm.get_llm_user', return_value=mock_llm_user_instance)
    mock_raw_stream = mocker.patch('backend.llm.generate_response_stream', return_value=iter(["Antwort ", "Teil 2"]))
    mocker.patch('backend.chatservice._filter_think_tags_from_stream', side_effect=lambda gen: gen)

    # 2. ACT
    with app.app_context():
        results = list(chatservice.stream_new_chat_session(
            user_input=user_input, node_ids=[], model=model, vault_id=vault_id, user_id=user_id
        ))

    # 3. ASSERT
    assert len(results) == 4
    assert results[0] == "session_id:session-123\n\n"
    assert results[1] == f"message_id:{mock_assistant_message.id}\n\n"
    assert results[2] == "Antwort "
    assert results[3] == "Teil 2"

    mock_create_session.assert_called_once_with(title=user_input, vault_id=vault_id, owner_id=user_id)
    assert mock_add_message.call_count == 2

    user_message_call = mock_add_message.call_args_list[0]
    assert user_message_call.kwargs['role'] == 'user'
    assert user_message_call.kwargs['content'] == user_input

    assistant_message_call = mock_add_message.call_args_list[1]
    assert assistant_message_call.kwargs['role'] == 'assistant'
    assert assistant_message_call.kwargs['content'] == ""

    assert mock_assistant_message.content == "Antwort Teil 2".strip()
    mock_raw_stream.assert_called_once()
    assert mock_commit.call_count == 3


def test_stream_saves_partial_response_on_llm_error(mocker, app, db_session):
    """
    Testet, ob eine Teilantwort gespeichert wird, wenn der LLM mitten im Stream einen Fehler auslöst.
    (ANGEPASST an die neue Logik mit message_id)
    """
    # 1. ARRANGE
    mock_session = MagicMock(spec=ChatSession, id="session-error-test", vault_id=1)
    mocker.patch('backend.database.create_chat_session', return_value=mock_session)

    mock_assistant_message = MagicMock(spec=ChatMessage, id="msg-err-456")
    # FIX: Assign the patch object to mock_add_message
    mock_add_message = mocker.patch('backend.database.add_chat_message', return_value=mock_assistant_message)
    mocker.patch('backend.chatservice.db.session.get', return_value=mock_assistant_message)

    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': []})
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': '', 'titles': []})
    mock_commit = mocker.patch('backend.chatservice.db.session.commit')
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(spec=User, id=999))

    def faulty_stream_generator(*args, **kwargs):
        yield "Anfang der Antwort. "
        yield "Zweiter Teil. "
        raise RuntimeError("LLM API connection failed!")

    mocker.patch('backend.llm.generate_response_stream', side_effect=faulty_stream_generator)

    # 2. ACT
    with app.app_context():
        results = list(chatservice.stream_new_chat_session(
            user_input="Test mit Fehler", node_ids=[], model="faulty-model", vault_id=1, user_id=1
        ))

    # 3. ASSERT
    assert len(results) == 5
    assert results[0] == "session_id:session-error-test\n\n"
    assert results[1] == f"message_id:{mock_assistant_message.id}\n\n"
    assert results[2] == "Anfang der Antwort. "
    assert results[3] == "Zweiter Teil. "
    assert results[4] == "error: The AI stream was interrupted."

    assert mock_add_message.call_count == 2
    assert mock_assistant_message.content == "Anfang der Antwort. Zweiter Teil.".strip()
    assert mock_commit.call_count == 3


def test_retry_specific_message_stream_successful(mocker, app, db_session):
    """
    Testet den "Happy Path" des Retry-Features.
    (Minimal angepasst für volle Konsistenz)
    """
    # 1. ARRANGE
    user_id = 1
    session_id = "session-to-retry"
    user_msg_1 = MagicMock(spec=ChatMessage, id='msg-user-1', role='user', content='Erste Frage')
    ai_msg_1 = MagicMock(spec=ChatMessage, id='msg-ai-1', role='assistant', content='Erste Antwort.')
    user_msg_2 = MagicMock(spec=ChatMessage, id='msg-user-2', role='user', content='Zweite Frage')
    mock_context_version = MagicMock(spec=Version, node_id='node-abc')
    user_msg_2.context_versions = [mock_context_version]
    target_message_id_int = 90210
    target_message_to_retry = MagicMock(
        spec=ChatMessage, id=target_message_id_int, role='assistant',
        content='Anfang der...', llm_model_source='test-model',
        session_id=session_id  # FIX: Add session_id to pass validation
    )

    mock_session = MagicMock(
        spec=ChatSession, id=session_id, owner_id=user_id, vault_id=1,
        llm_model='test-model',
        messages=[user_msg_1, ai_msg_1, user_msg_2, target_message_to_retry]
    )

    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.chatservice.db.session.get', return_value=target_message_to_retry)
    mocker.patch('backend.database.get_chat_session_history', return_value={
        'messages': [{'role': 'user', 'content': 'Erste Frage'}, {'role': 'assistant', 'content': 'Erste Antwort.'},
                     {'role': 'user', 'content': 'Zweite Frage'}]})
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': 'Kontext-Inhalt', 'titles': []})
    mock_db_commit = mocker.patch('backend.chatservice.db.session.commit')
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(spec=User, id=99))
    mock_llm_stream = mocker.patch('backend.llm.generate_response_stream', return_value=iter(["Neue Antwort."]))

    # 2. ACT
    with app.app_context():
        result_generator = chatservice.retry_specific_message_stream(session_id, target_message_id_int, user_id)
        results = list(result_generator)

    # 3. ASSERT
    assert "".join(results) == "Neue Antwort."
    assert target_message_to_retry.content == "Neue Antwort.".strip()
    assert mock_db_commit.call_count == 2


def test_retry_saves_partial_response_on_llm_error(mocker, app, db_session):
    """
    Testet, dass bei einem Fehler WÄHREND des Retry-Streams die Teilantwort gespeichert wird.
    """
    # ARRANGE
    target_id_int = 88
    session_id = "sid"
    # FIX: Add session_id to the mock message to pass validation
    target_message = MagicMock(spec=ChatMessage, id=target_id_int, role='assistant', llm_model_source='test-model', session_id=session_id)
    user_message = MagicMock(spec=ChatMessage, role='user', context_versions=[])
    mock_session = MagicMock(spec=ChatSession, id=session_id, owner_id=1, vault_id=1, messages=[user_message, target_message], llm_model='test-model')

    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.chatservice.db.session.get', return_value=target_message)
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': [{'role': 'user'}]})
    mocker.patch('backend.database.get_content_for_nodes', return_value={})
    mock_db_commit = mocker.patch('backend.chatservice.db.session.commit')
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(spec=User, id=99))

    def faulty_stream_generator(*args, **kwargs):
        yield "Anfang der neuen Antwort. "
        raise RuntimeError("LLM API ist abgestürzt!")

    mocker.patch('backend.llm.generate_response_stream', side_effect=faulty_stream_generator)

    # ACT
    with app.app_context():
        result_generator = chatservice.retry_specific_message_stream(session_id, target_id_int, 1)
        results = list(result_generator)

    # ASSERT
    assert len(results) == 2
    assert results[0] == "Anfang der neuen Antwort. "
    assert results[1] == "error: The AI stream was interrupted during retry with model 'test-model'."
    assert target_message.content == "Anfang der neuen Antwort. ".strip()
    # FIX: The number of commits should be 2 (1 for prep, 1 in finally)
    assert mock_db_commit.call_count == 2


def test_stream_new_chat_session_fails_to_find_message_on_update(mocker, app, db_session):
    """
    Testet das Szenario, dass der finale DB-Commit nach dem Stream fehlschlägt.
    """
    # 1. ARRANGE (Setup wie im erfolgreichen Test)
    mocker.patch('backend.database.create_chat_session', return_value=MagicMock(id="s1", vault_id=1))
    mock_assistant_message = MagicMock(spec=ChatMessage, id="msg-abc-123")
    mocker.patch('backend.database.add_chat_message', return_value=mock_assistant_message)
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': ''})
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': []})
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(spec=User, id=99))
    mocker.patch('backend.llm.generate_response_stream', return_value=iter(["Teil 1"]))
    mock_log_error = mocker.patch('backend.chatservice.logger.error')
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')

    # FIX: The test should mock `get` succeeding but `commit` failing.
    mocker.patch('backend.chatservice.db.session.get', return_value=mock_assistant_message)
    mocker.patch('backend.chatservice.db.session.commit', side_effect=[
        None, # Commit for user message
        None, # Commit for empty assistant message
        RuntimeError("DB constraint failed on update") # Fail the final commit
    ])

    # 2. ACT
    with app.app_context():
        list(chatservice.stream_new_chat_session("in", [], "m", 1, 1))

    # 3. ASSERT
    # FIX: Assert that the logger was called due to the commit failure.
    mock_log_error.assert_called_once()
    assert "Failed to update final message content" in mock_log_error.call_args[0][0]
    mock_rollback.assert_called_once()


def test_retry_preceding_message_is_not_user(mocker, app, db_session):
    """
    Testet den Fehlerfall, wenn man versucht, die allererste Nachricht in einer
    Sitzung zu wiederholen (was keinen Sinn ergibt).
    """
    # 1. ARRANGE
    session_id = "s1"
    # FIX: Setup a session with only one message, which we will try to retry.
    msg_to_retry = MagicMock(spec=ChatMessage, id=1, role='assistant', session_id=session_id)
    mock_session = MagicMock(spec=ChatSession, id=session_id, owner_id=1, messages=[msg_to_retry])

    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.chatservice.db.session.get', return_value=msg_to_retry)

    # 2. ACT
    with app.app_context():
        results = list(chatservice.retry_specific_message_stream(session_id, 1, 1))

    # 3. ASSERT
    # FIX: Assert the correct error message for this edge case.
    assert results == ["error: Cannot retry the first message."]


@pytest.mark.parametrize(
    "test_id, setup_mocks, expected_error",
    [
        (
            "session_not_found",
            lambda m: m.patch('backend.database.get_chat_session_by_id', return_value=None),
            "error: Session with id sid not found.\n\n"
        ),
        (
            "message_not_found_in_session",
            lambda m: (
                # Session exists...
                m.patch('backend.database.get_chat_session_by_id', return_value=MagicMock(owner_id=1, id='sid')),
                # ...but the message isn't found.
                m.patch('backend.chatservice.db.session.get', return_value=None)
            ),
            "error: Message 123 not found in this session.\n\n"
        ),
        (
            "cannot_retry_first_message",
            lambda m: (
                # FIX: Add session_id to all mock objects to pass validation checks
                m.patch('backend.database.get_chat_session_by_id', return_value=MagicMock(
                    owner_id=1, id='sid', messages=[MagicMock(spec=ChatMessage, id=123, role='assistant', session_id='sid')]
                )),
                m.patch('backend.chatservice.db.session.get', return_value=MagicMock(id=123, role='assistant', session_id='sid'))
            ),
            "error: Cannot retry the first message."
        )
    ]
)
def setup_cannot_retry_first_message_mocks(m):
    """Creates a shared mock message and uses it in both required patches."""
    # 1. Create the shared mock message object ONCE
    the_one_message = MagicMock(spec=ChatMessage, id=123, role='assistant', session_id='sid')

    # 2. Use it to build the mock session's message list
    m.patch('backend.database.get_chat_session_by_id', return_value=MagicMock(
        owner_id=1, id='sid', messages=[the_one_message]
    ))

    # 3. Use the SAME object as the return value for db.session.get
    m.patch('backend.chatservice.db.session.get', return_value=the_one_message)


@pytest.mark.parametrize(
    "test_id, setup_mocks, expected_error",
    [
        (
            "session_not_found",
            lambda m: m.patch('backend.database.get_chat_session_by_id', return_value=None),
            "error: Session with id sid not found.\n\n"
        ),
        (
            "message_not_found_in_session",
            lambda m: (
                # Session exists...
                m.patch('backend.database.get_chat_session_by_id', return_value=MagicMock(owner_id=1, id='sid')),
                # ...but the message isn't found.
                m.patch('backend.chatservice.db.session.get', return_value=None)
            ),
            "error: Message 123 not found in this session.\n\n"
        ),
        (
            "cannot_retry_first_message",
            # FIX: Replace the faulty lambda with our new helper function
            setup_cannot_retry_first_message_mocks,
            "error: Cannot retry the first message."
        )
    ]
)
def test_retry_specific_message_stream_guard_clauses(mocker, app, test_id, setup_mocks, expected_error, db_session):
    """
    Testet die verschiedenen Guard Clauses (Validierungsprüfungen) am Anfang von
    `retry_specific_message_stream`.
    """
    # 1. ARRANGE
    setup_mocks(mocker)

    # 2. ACT
    with app.app_context():
        results = list(chatservice.retry_specific_message_stream("sid", "123", 1))

    # 3. ASSERT
    assert len(results) == 1
    assert results[0] == expected_error

# ==============================================================================
# Tests für list_sessions
# ==============================================================================

def test_list_sessions_delegation(mocker):
    """
    Testet, ob `list_sessions` korrekt an die Datenbank-Schicht delegiert.
    """
    # ARRANGE
    mock_db_list = mocker.patch('backend.database.list_chat_sessions', return_value=[{"id": "s1"}])
    vault_id, user_id = 1, 100

    # ACT
    result = chatservice.list_sessions(vault_id=vault_id, user_id=user_id)

    # ASSERT
    mock_db_list.assert_called_once_with(vault_id=vault_id, user_id=user_id)
    assert result == [{"id": "s1"}]


# ==============================================================================
# Tests für create_new_chat_session (Non-Streaming)
# ==============================================================================

def test_create_new_chat_session_db_error_on_creation(mocker, app):
    """
    Testet den Fehlerfall, wenn die erste Transaktion (Erstellen der Session) fehlschlägt.
    """
    # ARRANGE
    mocker.patch('backend.database.create_chat_session', side_effect=ValueError("DB Error"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # ACT & ASSERT
    with app.app_context():
        with pytest.raises(ValueError, match="DB Error"):
            chatservice.create_new_chat_session("input", [], "model", 1, 1)

    mock_logger.assert_called_once()
    assert "FATAL: Could not create session" in mock_logger.call_args[0][0]
    mock_rollback.assert_called_once()


def test_create_new_chat_session_llm_error_after_user_message_saved(mocker, app):
    """
    Testet, dass eine Session-ID zurückgegeben wird, wenn der LLM-Call nach dem Speichern
    der User-Nachricht fehlschlägt.
    """
    # ARRANGE
    mock_session = MagicMock(spec=ChatSession, id="session-llm-fail")
    mocker.patch('backend.database.create_chat_session', return_value=mock_session)
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.add_chat_message') # User message succeeds
    mocker.patch('backend.chatservice.db.session.commit') # First commit succeeds

    # Mock LLM part to fail
    mocker.patch('backend.llm.get_llm_user', side_effect=RuntimeError("LLM unavailable"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    # KORREKTUR: Logger über seinen String-Pfad patchen
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # ACT
    with app.app_context():
        result = chatservice.create_new_chat_session("input", [], "model", 1, 1)

    # ASSERT
    assert result == {"session_id": "session-llm-fail", "content": None, "role": "assistant"}
    mock_rollback.assert_called_once() # Rollback for the second transaction
    mock_logger.assert_called_once()
    assert "AI response failed for new session" in mock_logger.call_args[0][0]


# ==============================================================================
# Tests für add_message_to_session (Non-Streaming)
# ==============================================================================

@pytest.mark.parametrize("session_owner, current_user, error_type, error_message", [
    (None, 1, ValueError, "Session with id session-perm-test not found."),
    (2, 1, PermissionError, "You do not have permission to access this chat session.")
])
def test_add_message_to_session_guards(mocker, app, session_owner, current_user, error_type, error_message):
    """
    Testet die Guard Clauses für nicht gefundene Sessions und Berechtigungsfehler.
    """
    # ARRANGE
    mock_session = MagicMock(spec=ChatSession, owner_id=session_owner) if session_owner else None
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)

    # ACT & ASSERT
    with app.app_context():
        with pytest.raises(error_type, match=error_message):
            chatservice.add_message_to_session("session-perm-test", "input", [], current_user)


def test_add_message_to_session_db_error(mocker, app):
    """
    Testet den Fehlerfall, wenn das Speichern der User-Nachricht fehlschlägt.
    """
    # ARRANGE
    mock_session = MagicMock(spec=ChatSession, id="s1", owner_id=1, vault_id=1)
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    # KORREKTUR: Mock für get_versions_for_node_ids hinzufügen, um DB-Call zu verhindern
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.add_chat_message', side_effect=ValueError("DB Error"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # ACT & ASSERT
    with app.app_context():
        with pytest.raises(ValueError, match="DB Error"):
            chatservice.add_message_to_session("s1", "input", [], 1)

    mock_logger.assert_called_once()
    assert "FATAL: Could not save user message" in mock_logger.call_args[0][0]
    mock_rollback.assert_called_once()


def test_add_message_to_session_llm_error(mocker, app):
    """
    Testet den Fehlerfall, wenn der LLM-Call fehlschlägt, nachdem die User-Nachricht gespeichert wurde.
    """
    # ARRANGE
    mock_session = MagicMock(spec=ChatSession, id="s1", owner_id=1, vault_id=1, messages=[])
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.add_chat_message') # User message succeeds
    mocker.patch('backend.chatservice.db.session.commit') # First commit succeeds

    mocker.patch('backend.llm.get_llm_user', side_effect=RuntimeError("LLM unavailable"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # ACT
    with app.app_context():
        result = chatservice.add_message_to_session("s1", "input", [], 1)

    # ASSERT
    assert result == {"session_id": "s1", "content": None, "role": "assistant"}
    mock_rollback.assert_called_once()
    mock_logger.assert_called_once()
    assert "AI response failed for session s1" in mock_logger.call_args[0][0]


# ==============================================================================
# Tests für Streaming-Funktionen (Fehlerfälle)
# ==============================================================================

def test_stream_new_chat_session_creation_error(mocker, app):
    """
    Testet, dass ein Fehler-Event gestreamt wird, wenn das Erstellen der Session fehlschlägt.
    """
    # ARRANGE
    mocker.patch('backend.database.create_chat_session', side_effect=Exception("DB down"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')

    # ACT
    with app.app_context():
        result = list(chatservice.stream_new_chat_session("in", [], "m", 1, 1))

    # ASSERT
    assert result == ["error: Failed to start the chat session."]
    mock_rollback.assert_called_once()


def test_stream_new_chat_session_prepare_assistant_error(mocker, app):
    """
    Testet, dass ein Fehler-Event gestreamt wird, wenn das Erstellen der leeren
    Assistenten-Nachricht fehlschlägt.
    """
    # ARRANGE
    mocker.patch('backend.database.create_chat_session', return_value=MagicMock(id="s1"))
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    # Der erste Call (User-Nachricht) gelingt, der zweite (leere Assistenten-Nachricht) schlägt fehl.
    mocker.patch('backend.database.add_chat_message', side_effect=[MagicMock(), Exception("Constraint failed")])
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(id=99))
    mocker.patch('backend.chatservice.db.session.commit') # Erster Commit gelingt

    # ACT
    with app.app_context():
        # Wir erwarten session_id, dann den Fehler
        results = list(chatservice.stream_new_chat_session("in", [], "m", 1, 1))

    # ASSERT
    assert results == ["session_id:s1\n\n", "error: Failed to prepare the AI response."]
    mock_rollback.assert_called_once()


def test_stream_message_in_session_session_not_found(mocker, app):
    """
    Testet den Fehlerfall, wenn die Session für das Streamen nicht gefunden wird.
    """
    # ARRANGE
    mocker.patch('backend.database.get_chat_session_by_id', return_value=None)

    # ACT
    with app.app_context():
        result = list(chatservice.stream_message_in_session("s-not-found", "in", [], 1, "default-model"))

    # ASSERT
    assert result == ["error: Session with id s-not-found not found or permission denied.\n\n"]


def test_stream_message_in_session_uses_default_model_if_none_in_history(mocker, app):
    """
    Testet, ob das Default-Modell verwendet wird, wenn keine vorherige Assistenten-Nachricht
    in der Session existiert.
    """
    # ARRANGE
    default_model = "claude-default-model"
    # Session hat nur eine User-Nachricht, keine vom Assistenten
    mock_session = MagicMock(spec=ChatSession, id="s1", vault_id=1, messages=[MagicMock(role='user')])
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mock_logger = mocker.patch('backend.chatservice.logger.info')

    # Mock den Rest des Flows, um den Test einfach zu halten
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.database.add_chat_message', return_value=MagicMock(id=123))
    mocker.patch('backend.chatservice.db.session.commit')
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(id=99))
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': []})
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': ''})
    mock_llm_call = mocker.patch('backend.llm.generate_response_stream', return_value=iter([]))

    # ACT
    with app.app_context():
        list(chatservice.stream_message_in_session("s1", "in", [], 1, default_model))

    # ASSERT
    mock_logger.assert_called_once_with(f"No previous model in session s1. Using default: '{default_model}'")
    mock_llm_call.assert_called_once()
    assert mock_llm_call.call_args.kwargs['model'] == default_model


def test_stream_message_in_session_save_user_message_error(mocker, app):
    """
    Testet den Fehlerfall beim Speichern der User-Nachricht in einer bestehenden Stream-Session.
    """
    # ARRANGE
    mock_session = MagicMock(spec=ChatSession, id="s1", vault_id=1, messages=[])
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.database.add_chat_message', side_effect=Exception("DB Error"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')

    # ACT
    with app.app_context():
        result = list(chatservice.stream_message_in_session("s1", "in", [], 1, "model"))

    # ASSERT
    assert result == ["error: Failed to save your message."]
    mock_rollback.assert_called_once()


def test_stream_message_in_session_final_update_db_error(mocker, app):
    """
    Testet, dass ein DB-Fehler beim finalen Update der Nachricht im `finally`-Block abgefangen wird.
    """
    # ARRANGE (vereinfachtes Setup)
    mock_session = MagicMock(spec=ChatSession, id="s1", vault_id=1, messages=[])
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mock_assistant_message = MagicMock(spec=ChatMessage, id=123)
    mocker.patch('backend.database.add_chat_message', return_value=mock_assistant_message)
    mocker.patch('backend.llm.generate_response_stream', return_value=iter(["final content"]))
    mocker.patch('backend.chatservice.db.session.get', return_value=mock_assistant_message)
    # Simuliere Fehler nur beim letzten Commit
    mocker.patch('backend.chatservice.db.session.commit', side_effect=[None, None, Exception("Final update failed")])
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # Mock alle anderen Abhängigkeiten
    mocker.patch('backend.database.get_versions_for_node_ids', return_value=[])
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(id=99))
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': []})
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': ''})

    # ACT
    with app.app_context():
        # Der Generator wird vollständig durchlaufen
        list(chatservice.stream_message_in_session("s1", "in", [], 1, "model"))

    # ASSERT
    mock_logger.assert_called_with(f"Failed to update final message content for {mock_assistant_message.id}: Final update failed", exc_info=True)
    mock_rollback.assert_called_once()


# ==============================================================================
# Tests für retry_specific_message_stream
# ==============================================================================

def test_retry_stream_model_fallback_to_original_message_model(mocker, app):
    """
    Testet, dass beim Retry auf das Modell der ursprünglichen Nachricht zurückgegriffen wird,
    wenn kein anderes Modell angegeben oder in der Session gefunden wird.
    """
    # ARRANGE
    original_model = "original-gpt-4"
    target_message = MagicMock(spec=ChatMessage, id=1, role='assistant', llm_model_source=original_model, session_id='s1')
    # KORREKTUR: Die Session darf keine *andere* Assistenten-Nachricht mit einem Modell haben.
    # Die Ziel-Nachricht selbst wird als "latest assistant message" gefunden.
    mock_session = MagicMock(spec=ChatSession, id='s1', owner_id=1, vault_id=1, messages=[MagicMock(role='user'), target_message])

    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.chatservice.db.session.get', return_value=target_message)
    mock_logger = mocker.patch('backend.chatservice.logger.info')
    mock_llm_call = mocker.patch('backend.llm.generate_response_stream', return_value=iter([]))

    # Mock den Rest des Flows
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(id=99))
    mocker.patch('backend.chatservice.db.session.commit')
    mocker.patch('backend.database.get_chat_session_history', return_value={'messages': []})
    mocker.patch('backend.database.get_content_for_nodes', return_value={'content': ''})

    # ACT
    with app.app_context():
        list(chatservice.retry_specific_message_stream('s1', 1, 1, model=None)) # model=None ist explizit

    # ASSERT
    # KORREKTUR: Die Logik findet die Ziel-Nachricht als "latest assistant model".
    # Wir müssen also auf die korrekte Log-Nachricht prüfen.
    mock_logger.assert_called_with(f"Retrying message 1 using latest assistant model: '{original_model}'")
    mock_llm_call.assert_called_once()
    assert mock_llm_call.call_args.kwargs['model'] == original_model


def test_retry_stream_prepare_message_error(mocker, app):
    """
    Testet den Fehlerfall, wenn das Vorbereiten der Nachricht für den Retry fehlschlägt.
    """
    # ARRANGE
    target_message = MagicMock(spec=ChatMessage, id=1, role='assistant', session_id='s1')
    mock_session = MagicMock(spec=ChatSession, id='s1', owner_id=1, messages=[MagicMock(role='user'), target_message])
    mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session)
    mocker.patch('backend.chatservice.db.session.get', return_value=target_message)
    mocker.patch('backend.llm.get_llm_user', return_value=MagicMock(id=99))
    # Der Commit beim Vorbereiten schlägt fehl
    mocker.patch('backend.chatservice.db.session.commit', side_effect=Exception("DB Prep Failed"))
    mock_rollback = mocker.patch('backend.chatservice.db.session.rollback')

    # ACT
    with app.app_context():
        result = list(chatservice.retry_specific_message_stream('s1', 1, 1, model="m1"))

    # ASSERT
    assert result == ["error: Could not prepare message for retry with model 'm1': DB Prep Failed"]
    mock_rollback.assert_called_once()


# ==============================================================================
# Tests für propose_node_update_from_chat
# ==============================================================================

def test_propose_node_update_from_chat_target_node_not_found(mocker, app):
    """
    Testet, dass ein ValueError ausgelöst wird, wenn der Ziel-Node nicht existiert.
    """
    # ARRANGE
    mocker.patch('backend.database.get_node_by_id', return_value=None)

    # ACT & ASSERT
    with app.app_context():
        with pytest.raises(ValueError, match="Target node with ID node-x not found in your vault."):
            chatservice.propose_node_update_from_chat("node-x", "history", [], "model", 1, 1)


def test_propose_node_update_from_chat_general_error(mocker, app):
    """
    Testet das Abfangen einer allgemeinen Exception während des LLM-Calls.
    """
    # ARRANGE
    mocker.patch('backend.database.get_node_by_id', return_value={'title': 't', 'content': 'c'})
    mocker.patch('backend.llm.generate_structured_response', side_effect=Exception("API Error"))
    mock_logger = mocker.patch('backend.chatservice.logger.error')

    # ACT & ASSERT
    with app.app_context():
        with pytest.raises(Exception, match="API Error"):
            chatservice.propose_node_update_from_chat("node-x", "history", [], "model", 1, 1)

    mock_logger.assert_called_once()
    assert "Error in propose_node_update_from_chat" in mock_logger.call_args[0][0]


# ==============================================================================
# Tests für _filter_think_tags_from_stream
# ==============================================================================

@pytest.mark.parametrize("input_chunks, expected_output", [
    # Fall 1: Inhalt vor einem <think>-Tag
    (["Hello <think>"], ["Hello "]),
    # KORREKTUR: Ein verwaistes </think>-Tag wird als normaler Text behandelt, nicht entfernt.
    # Der Test prüft nun dieses korrekte Verhalten.
    (["</think>World"], ["</think>World"]),
    # Fall 3: Kompletter Block in einem Chunk
    (["A<think>B</think>C"], ["A", "C"]),
    # Fall 4: Tags über mehrere Chunks verteilt
    (["A<think>B", "</think>C"], ["A", "C"]),
    # Fall 5: Unvollständiger End-Tag (wird nicht verarbeitet, Puffer bleibt)
    (["<think>A</think"], []),
    # Fall 6: Finaler Puffer wird am Ende ausgegeben (Sicherheitsnetz)
    (["<think>A</think>Final"], ["Final"]),
])
def test_filter_think_tags_from_stream_logic(input_chunks, expected_output):
    """
    Testet verschiedene Szenarien des <think>-Tag-Filters, um die interne Logik
    der while-Schleife abzudecken.
    """
    # ARRANGE
    stream_generator = iter(input_chunks)

    # ACT
    result = list(chatservice._filter_think_tags_from_stream(stream_generator))

    # ASSERT
    assert result == expected_output


def test_create_new_chat_session_happy_path(mocker, app):
    """
    Testet den erfolgreichen Durchlauf ("Happy Path") von create_new_chat_session.
    Alle Datenbank- und LLM-Operationen gelingen.
    """
    # 1. ARRANGE (Vorbereitung)

    # -- Konstanten für den Test --
    USER_INPUT = "Was ist die Hauptstadt von Deutschland?"
    NODE_IDS = ["node-1", "node-2"]
    MODEL = "claude-3-sonnet"
    VAULT_ID = 1
    USER_ID = 10
    SESSION_ID = "session-happy-123"
    ASSISTANT_USER_ID = 999
    AI_RESPONSE = "Die Hauptstadt von Deutschland ist Berlin."
    CONTEXT_CONTENT = "Zusätzlicher Kontext aus den Nodes."

    # -- Mocking der Abhängigkeiten --

    # Transaktion 1: Session und User-Nachricht erstellen
    mock_session_obj = MagicMock(spec=ChatSession, id=SESSION_ID)
    mock_create_session = mocker.patch('backend.database.create_chat_session', return_value=mock_session_obj)

    mock_context_versions = [MagicMock(spec=Version)]
    mock_get_versions = mocker.patch('backend.database.get_versions_for_node_ids', return_value=mock_context_versions)

    # Da add_chat_message zweimal aufgerufen wird, mocken wir es allgemein
    mock_add_message = mocker.patch('backend.database.add_chat_message')

    # Transaktion 2: KI-Antwort generieren
    mock_assistant_user = MagicMock(spec=User, id=ASSISTANT_USER_ID)
    # KORREKTUR: Das Mock-Objekt in einer Variablen speichern, um es später zu überprüfen
    mock_get_llm_user = mocker.patch('backend.llm.get_llm_user', return_value=mock_assistant_user)

    mock_history = {'messages': [{'role': 'user', 'content': USER_INPUT}]}
    mocker.patch('backend.database.get_chat_session_history', return_value=mock_history)

    mock_context_data = {'content': CONTEXT_CONTENT}
    mocker.patch('backend.database.get_content_for_nodes', return_value=mock_context_data)

    mock_generate_response = mocker.patch('backend.llm.generate_response', return_value=AI_RESPONSE)

    # Mocking der DB-Commits
    mock_commit = mocker.patch('backend.chatservice.db.session.commit')

    # 2. ACT (Ausführung)
    with app.app_context():
        result = chatservice.create_new_chat_session(
            user_input=USER_INPUT,
            node_ids=NODE_IDS,
            model=MODEL,
            vault_id=VAULT_ID,
            user_id=USER_ID
        )

    # 3. ASSERT (Überprüfung)

    # -- Überprüfung des Rückgabewerts --
    assert result == {
        "session_id": SESSION_ID,
        "content": AI_RESPONSE,
        "role": "assistant"
    }

    # -- Überprüfung der Funktionsaufrufe --

    # Transaktion 1
    mock_create_session.assert_called_once_with(title=USER_INPUT, vault_id=VAULT_ID, owner_id=USER_ID)
    mock_get_versions.assert_called_once_with(NODE_IDS, VAULT_ID, USER_ID)

    # Transaktion 2
    # KORREKTUR: Die zuvor gespeicherte Variable für die Überprüfung verwenden
    mock_get_llm_user.assert_called_once_with(MODEL)

    expected_system_prompt = (
        "You are a helpful assistant for a knowledge base. "
        "Use the following context to answer the user's question. "
        "If the context is empty, use your general knowledge.\n\n"
        f"<context>\n{CONTEXT_CONTENT}\n</context>"
    )
    mock_generate_response.assert_called_once_with(
        messages=mock_history['messages'],
        system_prompt=expected_system_prompt,
        model=MODEL
    )

    # Überprüfung beider `add_chat_message`-Aufrufe
    assert mock_add_message.call_count == 2

    # Erster Aufruf: User-Nachricht
    user_message_call = mock_add_message.call_args_list[0]
    user_message_call.assert_called_with(
        session_id=SESSION_ID,
        role='user',
        content=USER_INPUT,
        author_id=USER_ID,
        context_versions=mock_context_versions
    )

    # Zweiter Aufruf: Assistant-Nachricht
    assistant_message_call = mock_add_message.call_args_list[1]
    assistant_message_call.assert_called_with(
        session_id=SESSION_ID,
        role='assistant',
        content=AI_RESPONSE,
        author_id=ASSISTANT_USER_ID,
        llm_model_source=MODEL
    )

    # Sicherstellen, dass beide Transaktionen committet wurden
    assert mock_commit.call_count == 2


def test_add_message_to_session_happy_path(mocker, app):
    """
    Testet den erfolgreichen Durchlauf ("Happy Path") von add_message_to_session.
    Die Funktion findet eine bestehende Session, verwendet das Modell der letzten
    KI-Nachricht und generiert erfolgreich eine neue Antwort.
    """
    # 1. ARRANGE (Vorbereitung)

    # -- Konstanten für den Test --
    SESSION_ID = "session-continue-456"
    USER_ID = 20
    VAULT_ID = 2
    USER_INPUT = "Erzähl mir mehr darüber."
    NODE_IDS = ["node-3"]
    PREVIOUS_MODEL = "claude-3-opus-20240229"  # Das Modell aus der "Vergangenheit"
    AI_RESPONSE = "Gerne, hier sind weitere Details."
    CONTEXT_CONTENT = "Kontext für die neue Frage."
    ASSISTANT_USER_ID = 998

    # -- Mocking der Abhängigkeiten --

    # Mock für die bestehende Session und ihre letzte Nachricht
    mock_last_assistant_msg = MagicMock(
        spec=ChatMessage,
        role='assistant',
        llm_model_source=PREVIOUS_MODEL
    )
    mock_session_obj = MagicMock(
        spec=ChatSession,
        id=SESSION_ID,
        owner_id=USER_ID,
        vault_id=VAULT_ID,
        messages=[mock_last_assistant_msg]  # Wichtig für die Modellauswahl
    )
    mock_get_session = mocker.patch('backend.database.get_chat_session_by_id', return_value=mock_session_obj)

    # Transaktion 1: User-Nachricht speichern
    mock_context_versions = [MagicMock(spec=Version)]
    mock_get_versions = mocker.patch('backend.database.get_versions_for_node_ids', return_value=mock_context_versions)
    mock_add_message = mocker.patch('backend.database.add_chat_message')

    # Transaktion 2: KI-Antwort generieren
    mock_assistant_user = MagicMock(spec=User, id=ASSISTANT_USER_ID)
    mock_get_llm_user = mocker.patch('backend.llm.get_llm_user', return_value=mock_assistant_user)

    mock_history = {'messages': [{'role': 'user', 'content': USER_INPUT}]}
    mocker.patch('backend.database.get_chat_session_history', return_value=mock_history)

    mock_context_data = {'content': CONTEXT_CONTENT}
    mocker.patch('backend.database.get_content_for_nodes', return_value=mock_context_data)

    mock_generate_response = mocker.patch('backend.llm.generate_response', return_value=AI_RESPONSE)

    # Mocking der DB-Commits
    mock_commit = mocker.patch('backend.chatservice.db.session.commit')

    # 2. ACT (Ausführung)
    with app.app_context():
        result = chatservice.add_message_to_session(
            session_id=SESSION_ID,
            user_input=USER_INPUT,
            node_ids=NODE_IDS,
            user_id=USER_ID
        )

    # 3. ASSERT (Überprüfung)

    # -- Überprüfung des Rückgabewerts --
    assert result == {
        "session_id": SESSION_ID,
        "content": AI_RESPONSE,
        "role": "assistant"
    }

    # -- Überprüfung der Funktionsaufrufe --

    # Autorisierung
    mock_get_session.assert_called_once_with(SESSION_ID)

    # Transaktion 1
    mock_get_versions.assert_called_once_with(NODE_IDS, VAULT_ID, USER_ID)

    # Transaktion 2
    # Wichtig: Prüfen, ob das korrekte Modell aus der Historie ausgewählt wurde
    mock_get_llm_user.assert_called_once_with(PREVIOUS_MODEL)

    # Der System-Prompt muss exakt nachgebildet werden
    expected_system_prompt = (
        "You are a helpful assistant for a knowledge base. "
        "Use the following context to answer the user's question. "
        "If the context is empty, use your general knowledge.\n\n"
        f"<context>\n{CONTEXT_CONTENT}\n</context>"
    )
    mock_generate_response.assert_called_once_with(
        messages=mock_history['messages'],
        system_prompt=expected_system_prompt,
        model=PREVIOUS_MODEL  # Prüfen, ob das übergebene Modell stimmt
    )

    # Überprüfung beider `add_chat_message`-Aufrufe
    assert mock_add_message.call_count == 2
    user_message_call = mock_add_message.call_args_list[0]
    user_message_call.assert_called_with(
        session_id=SESSION_ID,
        role='user',
        content=USER_INPUT,
        author_id=USER_ID,
        context_versions=mock_context_versions
    )

    assistant_message_call = mock_add_message.call_args_list[1]
    assistant_message_call.assert_called_with(
        session_id=SESSION_ID,
        role='assistant',
        content=AI_RESPONSE,
        author_id=ASSISTANT_USER_ID,
        llm_model_source=PREVIOUS_MODEL
    )

    # Sicherstellen, dass beide Transaktionen committet wurden
    assert mock_commit.call_count == 2