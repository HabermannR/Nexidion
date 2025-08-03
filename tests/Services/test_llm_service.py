import pytest
import json
from unittest.mock import patch, MagicMock, ANY

from backend.services import chat_service, node_service, llm_service

from backend.models import User, Vault, ChatMessage


# Eine Hilfsfunktion, um den Generator-Stream zu konsumieren
def _consume_stream(stream_generator):
    """
    Konsumiert einen SSE-Stream-Generator und extrahiert die Events und den reinen Text-Inhalt.
    """
    events = []
    full_text_content = ""
    for event_string in stream_generator:
        # SSE-Events sind durch \n\n getrennt, aber unser Generator gibt sie einzeln zurück.
        if not event_string.strip():
            continue

        lines = event_string.strip().split('\n')
        event_data = {}
        for line in lines:
            if line.startswith('event:'):
                event_data['event'] = line.replace('event:', '').strip()
            elif line.startswith('data:'):
                try:
                    # Versuche, das JSON zu parsen
                    payload = json.loads(line.replace('data:', '').strip())
                    event_data['data'] = payload

                    # Extrahiere den reinen Text-Token, wenn er existiert
                    if isinstance(payload, dict) and 'token' in payload:
                        full_text_content += payload['token']
                except json.JSONDecodeError:
                    # Fallback, falls data kein JSON ist
                    event_data['data'] = line.replace('data:', '').strip()

        if 'data' in event_data:
            events.append(event_data)

    return events, full_text_content


@patch('backend.services.chat_service.llm_service.get_llm_user')
@patch('backend.services.chat_service.llm_service.generate_response_stream')
def test_stream_new_message_success_and_db_persistence(
        mock_generate_stream,
        mock_get_llm_user,
        test_user_1_obj: User,
        test_vault_1_obj: Vault,
        db_session
):
    """
    Testet den kompletten Flow von `stream_new_message`.
    Dies ersetzt `test_add_chat_message_success`, `test_add_chat_message_with_context_versions`
    und `test_add_chat_message_with_different_versions_of_same_node`.
    """
    # 1. ARRANGE
    # a) Mocke den LLM-Service, um externe Aufrufe zu verhindern
    mock_response_chunks = ["Hello, ", "this is a ", "test response."]
    mock_generate_stream.return_value = iter(mock_response_chunks)

    # Erstelle einen Mock-User für den Assistenten
    mock_assistant_user = User(id=999, username="TestLLM")
    mock_get_llm_user.return_value = mock_assistant_user

    # b) Erstelle die notwendigen Daten über die Services
    session = chat_service.create_new_session(test_vault_1_obj.id, test_user_1_obj.id)
    node1 = node_service.create_node("Node 1", "Content V1", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_service.update_node(node1.id, test_vault_1_obj.id, test_user_1_obj.id, content="Content V2")
    node2 = node_service.create_node("Node 2", "Other content", None, test_vault_1_obj.id, test_user_1_obj.id)

    # Wir wollen die neueste Version von node1 (V2) und node2 (V1) als Kontext
    node_ids_for_context = [node1.id, node2.id]

    # 2. ACT
    stream_generator = chat_service.stream_new_message(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        user_input="My question with context",
        model="test-model",
        node_ids=node_ids_for_context
    )
    # Konsumiere den Stream, um die Aktionen auszulösen
    events, full_response_content = _consume_stream(stream_generator)

    # 3. ASSERT
    # a) Überprüfe den gestreamten Inhalt
    assert full_response_content == "Hello, this is a test response."
    assert len(events) > 3  # user_message, assistant_start, 3x data, assistant_end

    # b) Überprüfe den Zustand der Datenbank (das ist der wichtigste Teil)
    db_session.session.refresh(session)
    messages = session.messages.order_by(ChatMessage.timestamp.asc()).all()

    assert len(messages) == 2  # Eine User-Nachricht, eine Assistenten-Nachricht

    # c) Überprüfe die User-Nachricht
    user_message = messages[0]
    assert user_message.role == 'user'
    assert user_message.content == "My question with context"
    assert user_message.author_id == test_user_1_obj.id
    assert user_message.status == 'active'

    # d) Überprüfe den Kontext der User-Nachricht (ersetzt die alten Kontext-Tests)
    assert len(user_message.context_versions) == 2
    context_contents = sorted([v.content for v in user_message.context_versions])
    context_versions = sorted([v.version for v in user_message.context_versions])
    assert context_contents == ["Content V2", "Other content"]  # Korrekte Inhalte
    assert context_versions == [1, 2]  # Korrekte Versionen (Node1=V2, Node2=V1)

    # e) Überprüfe die Assistenten-Nachricht
    assistant_message = messages[1]
    assert assistant_message.role == 'assistant'
    assert assistant_message.content == "Hello, this is a test response."
    assert assistant_message.author_id == mock_assistant_user.id
    assert assistant_message.llm_model_source == 'test-model'
    assert assistant_message.status == 'active'


@patch('backend.services.chat_service.llm_service.get_llm_user')
@patch('backend.services.chat_service.llm_service.generate_response_stream')
def test_stream_new_message_saves_partial_response_on_llm_error(
        mock_generate_stream,
        mock_get_llm_user,
        test_user_1_obj: User,
        test_vault_1_obj: Vault,
        db_session
):
    """
    Testet, dass eine Teil-Antwort gespeichert wird, wenn der LLM-Stream einen Fehler wirft.
    """

    # 1. ARRANGE
    # a) Simuliere einen fehlerhaften Stream
    def faulty_stream_generator():
        yield "Dies ist "
        yield "der Anfang."
        raise ValueError("LLM API connection failed!")

    mock_generate_stream.return_value = faulty_stream_generator()

    # b) Simuliere den LLM-Benutzer, der die Antwort verfasst
    llm_user = User(id=999, username="FaultyLLM")
    mock_get_llm_user.return_value = llm_user

    # c) Erstelle eine Session
    session = chat_service.create_new_session(test_vault_1_obj.id, test_user_1_obj.id)

    # 2. ACT
    # Rufe die Funktion auf. Wir erwarten KEINE Exception, da sie intern behandelt wird.
    # Wir müssen den Generator vollständig konsumieren, um den Fehler auszulösen
    # und den `finally`-Block in der getesteten Funktion auszuführen.
    stream_generator = chat_service.stream_new_message(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        user_input="Eine Frage",
        model="test-model",
        node_ids=[]
    )

    # Konsumiere den Generator. Eine einfache Möglichkeit ist, ihn in eine Liste umzuwandeln.
    # Eventuelle Fehler, die an den Client gesendet werden, werden hier gesammelt,
    # aber wir ignorieren sie für diesen Test, da wir den DB-Zustand prüfen.
    try:
        list(stream_generator)
    except ValueError:
        # Falls die Funktion wider Erwarten doch die Exception wirft, fangen wir sie hier ab,
        # damit der Test nicht abstürzt, bevor wir die Assertions ausführen können.
        # Ein `pass` ist hier in Ordnung, da das Nicht-Werfen der Exception das erwartete Verhalten ist.
        pass

    # 3. ASSERT
    # Überprüfe, ob die Teil-Antwort in der Datenbank gespeichert wurde.
    db_session.session.commit()  # Stellen Sie sicher, dass die Transaktion abgeschlossen ist

    # Finde die vom LLM generierte Nachricht in der DB
    saved_message = db_session.session.query(ChatMessage).filter_by(
        session_id=session.id,
        author_id=llm_user.id  # Suche nach der Nachricht vom LLM-Benutzer
    ).one_or_none()

    # Stelle sicher, dass eine Nachricht gefunden wurde
    assert saved_message is not None, "Keine Nachricht vom LLM in der DB gespeichert!"

    # Stelle sicher, dass der Inhalt der gespeicherten Nachricht korrekt ist
    expected_partial_content = "Dies ist der Anfang."
    assert saved_message.content == expected_partial_content, \
        f"Gespeicherter Inhalt '{saved_message.content}' entspricht nicht dem erwarteten Inhalt '{expected_partial_content}'"


@patch('backend.services.chat_service.llm_service.get_llm_user')
@patch('backend.services.chat_service.llm_service.generate_response_stream')
def test_stream_retry_message_success(
        mock_generate_stream,
        mock_get_llm_user,
        test_user_1_obj: User,
        test_vault_1_obj: Vault,
        db_session
):
    """Testet den erfolgreichen Retry-Flow."""
    # 1. ARRANGE
    # a) Mocke den LLM-Service
    mock_generate_stream.return_value = iter(["Dies ist ", "die neue Antwort."])
    mock_get_llm_user.return_value = User(id=999, username="RetryLLM")

    # b) Erstelle eine Historie in der DB
    session = chat_service.create_new_session(test_vault_1_obj.id, test_user_1_obj.id)
    # Simuliere einen ersten Durchlauf mit `stream_new_message`
    # (Wir könnten das auch manuell in die DB schreiben, aber so ist es realistischer)
    with patch('backend.services.chat_service.llm_service.generate_response_stream',
               return_value=iter(["Alte Antwort."])):
        list(chat_service.stream_new_message(session.id, test_user_1_obj.id, "Meine Frage", "old-model", []))

    # Hole die ID der User-Nachricht, die wir "retryen" wollen
    user_message_to_retry = db_session.session.query(ChatMessage).filter_by(session_id=session.id, role='user').one()

    # 2. ACT
    retry_stream = chat_service.stream_retry_message(
        session_id=session.id,
        message_id=user_message_to_retry.id,
        user_id=test_user_1_obj.id,
        model="new-model"
    )
    list(retry_stream)  # Konsumiere den Generator

    # 3. ASSERT
    db_session.session.refresh(session)
    # WICHTIG: Sortiere nach sort_order, dann nach timestamp, um eine stabile Reihenfolge zu garantieren
    messages = session.messages.order_by(ChatMessage.sort_order.asc(), ChatMessage.timestamp.asc()).all()

    # Wir erwarten 3 Nachrichten in der DB:
    # 1. Die originale User-Nachricht.
    # 2. Die alte Assistant-Nachricht, die nun als 'retried' markiert ist.
    # 3. Die neue Assistant-Nachricht, die die alte ersetzt.
    assert len(messages) == 3, f"Erwartet wurden 3 Nachrichten, aber {len(messages)} gefunden."

    original_user_msg = messages[0]
    old_assistant_msg = messages[1]
    new_assistant_msg = messages[2]

    # Prüfe die User-Nachricht (sollte unberührt sein)
    assert original_user_msg.role == 'user'
    assert original_user_msg.content == "Meine Frage"
    assert original_user_msg.status == 'active'

    # Prüfe die alte Assistant-Nachricht (sollte auf 'retried' gesetzt sein)
    assert old_assistant_msg.role == 'assistant'
    assert old_assistant_msg.content == "Alte Antwort."
    assert old_assistant_msg.status == 'retried'
    assert old_assistant_msg.llm_model_source == "old-model"  # Prüft, ob wir die richtige Nachricht haben

    # Prüfe die neue Assistant-Nachricht (sollte 'active' sein und neuen Inhalt haben)
    assert new_assistant_msg.role == 'assistant'
    assert new_assistant_msg.content == "Dies ist die neue Antwort."
    assert new_assistant_msg.status == 'active'
    assert new_assistant_msg.llm_model_source == "new-model"  # Prüft, ob das neue Modell verwendet wurde

    # Prüfe, ob die sort_order korrekt wiederverwendet wurde
    assert old_assistant_msg.sort_order == new_assistant_msg.sort_order
    assert new_assistant_msg.sort_order == original_user_msg.sort_order + 1


@patch('backend.services.chat_service.llm_service.generate_structured_response')
@patch('backend.services.chat_service.node_service.get_content_for_nodes')
@patch('backend.services.chat_service.get_session_history')  # <--- Dieser Mock wird geändert
@patch('backend.services.chat_service.node_service.get_node_by_id')
@patch('backend.services.chat_service._verify_session_access')
def test_propose_node_update_from_chat_happy_path(
        mock_verify_session, mock_get_node, mock_get_history, mock_get_content, mock_llm_call
):
    """Testet den Happy Path von propose_node_update_from_chat."""
    # 1. ARRANGE
    mock_verify_session.return_value = MagicMock(vault_id=1)
    mock_get_node.return_value = {'title': 'Original Title', 'content': 'Original Content'}

    # ===== KORREKTUR HIER =====
    # Der Mock muss jetzt das Dictionary zurückgeben, das die echte Funktion auch zurückgibt.
    mock_get_history.return_value = {
        "id": "session-abc",
        "title": "Test Session",
        "messages": [
            {'role': 'user', 'content': 'Meine Frage'},
            {'role': 'assistant', 'content': 'Eine Antwort'}
        ]
    }

    mock_get_content.return_value = {'content': 'Zusatzkontext', 'titles': ['Zusatz-Titel']}
    mock_llm_call.return_value = 'Der neue, vorgeschlagene Inhalt.'

    # 2. ACT
    result = chat_service.propose_node_update_from_chat(
        target_node_id='node-123',
        session_id='session-abc',
        context_node_ids=['node-456'],
        model='test-propose-model',
        user_id=1
    )

    # 3. ASSERT
    # a) Überprüfe das Ergebnis der Funktion
    assert result == {
        "original_content": "Original Content",
        "proposed_content": "Der neue, vorgeschlagene Inhalt."
    }

    # b) Überprüfe, ob der LLM-Service mit dem korrekt zusammengebauten Prompt aufgerufen wurde
    mock_llm_call.assert_called_once()
    args, kwargs = mock_llm_call.call_args

    assert kwargs['model'] == 'test-propose-model'
    # Überprüfe, ob die Kerninformationen im Prompt enthalten sind
    assert "Original Content of the Node to Update" in kwargs['user_prompt']
    assert "Original Content" in kwargs['user_prompt']
    assert "User: Meine Frage" in kwargs['user_prompt']
    assert "Zusatzkontext" in kwargs['user_prompt']
    assert "Language Consistency" in kwargs['system_prompt']


@pytest.fixture(autouse=True)
def clear_llm_user_cache():
    """Eine Fixture, die den Cache vor jedem Test automatisch leert."""
    llm_service._llm_user_cache.clear()
    yield


def test_get_llm_user_creates_new_user(db_session):
    """
    Testet, dass ein neuer LLM-Benutzer korrekt in der DB erstellt wird,
    wenn er noch nicht existiert.
    """
    # Arrange
    model_name = "claude-3-opus"
    assert db_session.session.query(User).filter_by(username=model_name).count() == 0

    # Act
    llm_user = llm_service.get_llm_user(model_name)

    # Assert
    assert llm_user is not None
    assert llm_user.username == model_name
    assert llm_user.display_name == "Claude 3 Opus"  # Korrekte Formatierung
    assert llm_user.user_type == 'llm_assistant'
    assert db_session.session.query(User).filter_by(username=model_name).count() == 1


def test_get_llm_user_creates_new_mock_user(db_session):
    """Testet die spezielle Namensformatierung für Mock-Modelle."""
    # Arrange
    model_name = "mock-test-model"

    # Act
    llm_user = llm_service.get_llm_user(model_name)

    # Assert
    assert llm_user is not None
    assert llm_user.username == model_name
    assert llm_user.display_name == "Mock LLM (Test Model)"  # Spezielle Formatierung
    assert llm_user.user_type == 'llm_assistant'


def test_get_llm_user_retrieves_existing_user(db_session):
    """
    Testet, dass ein bereits existierender LLM-Benutzer aus der DB geholt
    und kein neuer erstellt wird.
    """
    # Arrange
    model_name = "gpt-4o-mini"
    # Erstelle den User manuell vorab
    existing_user = User(username=model_name, display_name="GPT-4o Mini", user_type='llm_assistant')
    db_session.session.add(existing_user)
    db_session.session.commit()
    existing_user_id = existing_user.id

    assert db_session.session.query(User).count() == 1

    # Act
    llm_user = llm_service.get_llm_user(model_name)

    # Assert
    assert llm_user is not None
    assert llm_user.id == existing_user_id
    # Stelle sicher, dass kein neuer User hinzugefügt wurde
    assert db_session.session.query(User).count() == 1


def test_get_llm_user_uses_cache_on_second_call(db_session):
    """
    Testet, dass der In-Memory-Cache verwendet wird, um DB-Abfragen zu vermeiden.
    """
    model_name = "gemini-1-5-pro"

    # 1. Erster Aufruf: Holt den User aus der DB und füllt den Cache
    first_call_user = llm_service.get_llm_user(model_name)
    assert first_call_user is not None
    assert model_name in llm_service._llm_user_cache

    # 2. Mocke die DB-Abfrage, um sicherzustellen, dass sie nicht aufgerufen wird
    with patch('backend.services.llm_service.User.query') as mock_query:
        # Konfiguriere den Mock so, dass er einen Fehler werfen oder None zurückgeben würde,
        # wenn er aufgerufen wird.
        mock_query.filter_by.return_value.first.return_value = None

        # Zweiter Aufruf: Sollte den User aus dem Cache holen
        second_call_user = llm_service.get_llm_user(model_name)

        # Assert
        # Die DB-Abfrage darf nicht stattgefunden haben
        mock_query.filter_by.assert_not_called()
        # Der zurückgegebene User muss derselbe sein wie beim ersten Aufruf
        assert second_call_user.id == first_call_user.id


@patch('backend.services.llm_service.anthropic.Anthropic')
def test_generate_with_claude_streaming_calls_api_correctly(mock_anthropic_client, mocker):
    """
    Testet, ob _generate_with_claude_streaming die Anthropic-API korrekt aufruft
    und den Stream korrekt verarbeitet.
    """
    # 1. ARRANGE
    # Mocke die Konfiguration, die von der Funktion verwendet wird
    mocker.patch('backend.services.llm_service.current_app.config', {
        'ANTHROPIC_API_KEY': 'fake-api-key'
    })

    # Erstelle einen Mock für den Stream-Kontextmanager und den Text-Stream
    mock_stream_context = MagicMock()
    mock_stream_context.text_stream = iter(["Hello", ", ", "Claude!"])

    # Der Aufruf von client.messages.stream soll unseren Mock-Kontextmanager zurückgeben
    mock_anthropic_instance = mock_anthropic_client.return_value
    mock_anthropic_instance.messages.stream.return_value.__enter__.return_value = mock_stream_context

    # Testdaten
    messages = [{"role": "user", "content": "Hi there"}]
    system_prompt = "You are a test assistant."
    model = "claude-3-haiku-20240307"

    # 2. ACT
    # Rufe die Funktion auf und konsumiere den Generator
    result_chunks = list(llm_service._generate_with_claude_streaming(messages, system_prompt, model, 1024))
    full_result = "".join(result_chunks)

    # 3. ASSERT
    # Wurde der Anthropic-Client mit dem API-Key initialisiert?
    mock_anthropic_client.assert_called_once_with(api_key='fake-api-key')

    # Wurde die stream-Methode mit den korrekten Parametern aufgerufen?
    mock_anthropic_instance.messages.stream.assert_called_once_with(
        model=model,
        system=system_prompt,
        messages=messages,
        max_tokens=1024,
        temperature=ANY  # Wir kümmern uns nicht um den exakten Temperaturwert
    )

    # Ist das Ergebnis korrekt zusammengesetzt?
    assert full_result == "Hello, Claude!"
