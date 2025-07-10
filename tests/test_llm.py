import pytest
import json
from unittest.mock import MagicMock

from backend import llm
from backend.models import User

# Die 'app' Fixture ist notwendig, damit der 'app_context' funktioniert.
# Flask-Erweiterungen (und `current_app`) benötigen diesen Kontext.
def test_routing_to_openai_stream(mocker, app):
    """
    Testet, ob generate_response_stream bei einem 'gpt'-Modell
    korrekt an _generate_with_openai_streaming weiterleitet.
    """
    # 1. ARRANGE: Mocks vorbereiten
    # Wir ersetzen die eigentliche Streaming-Funktion durch einen leeren Mock.
    # Wir müssen nur wissen, DASS sie aufgerufen wurde.
    mock_openai_stream = mocker.patch('backend.llm._generate_with_openai_streaming')
    
    # Wir müssen auch sicherstellen, dass die anderen nicht aufgerufen werden.
    mock_claude_stream = mocker.patch('backend.llm._generate_with_claude_streaming')
    mock_gemini_stream = mocker.patch('backend.llm._generate_with_gemini_streaming')

    # 2. ACT: Die Router-Funktion aufrufen
    # Da es ein Generator ist, müssen wir ihn konsumieren, damit der Code darin ausgeführt wird.
    # list() ist ein einfacher Weg, das zu tun.
    with app.app_context():
        # Der app_context ist wichtig, weil die OpenAI-Funktion auf `current_app.config` zugreift.
        generator = llm.generate_response_stream(messages=[], model='gpt-4o')
        list(generator) # Konsumiere den Generator, um den Code auszuführen

    # 3. ASSERT: Überprüfen, welche Mocks aufgerufen wurden
    mock_openai_stream.assert_called_once()
    mock_claude_stream.assert_not_called()
    mock_gemini_stream.assert_not_called()

def test_routing_to_claude_stream(mocker, app):
    """
    Testet, ob generate_response_stream bei einem 'claude'-Modell
    korrekt an _generate_with_claude_streaming weiterleitet.
    """
    # ARRANGE
    mock_openai_stream = mocker.patch('backend.llm._generate_with_openai_streaming')
    mock_claude_stream = mocker.patch('backend.llm._generate_with_claude_streaming')
    mock_gemini_stream = mocker.patch('backend.llm._generate_with_gemini_streaming')

    # ACT
    with app.app_context():
        generator = llm.generate_response_stream(messages=[], model='claude-sonnet-4-20250514')
        list(generator)

    # ASSERT
    mock_openai_stream.assert_not_called()
    mock_claude_stream.assert_called_once()
    mock_gemini_stream.assert_not_called()

# Du kannst das Muster für Gemini und 'local' wiederholen
def test_routing_to_gemini_stream(mocker, app):
    # ARRANGE
    mock_openai_stream = mocker.patch('backend.llm._generate_with_openai_streaming')
    mock_claude_stream = mocker.patch('backend.llm._generate_with_claude_streaming')
    mock_gemini_stream = mocker.patch('backend.llm._generate_with_gemini_streaming')

    # ACT
    with app.app_context():
        generator = llm.generate_response_stream(messages=[], model='gemini-2.5-pro')
        list(generator)

    # ASSERT
    mock_openai_stream.assert_not_called()
    mock_claude_stream.assert_not_called()
    mock_gemini_stream.assert_called_once()
    pass

def test_routing_to_local_stream(mocker, app):
    # 'local' wird auch an die openai-Funktion geleitet
    # ARRANGE
    mock_openai_stream = mocker.patch('backend.llm._generate_with_openai_streaming')

    # ACT
    with app.app_context():
        generator = llm.generate_response_stream(messages=[], model='local')
        list(generator)
    
    # ASSERT
    mock_openai_stream.assert_called_once()
    # Wir können hier sogar prüfen, ob der Aufruf die richtigen Argumente hatte
    mock_openai_stream.assert_called_with(mocker.ANY, mocker.ANY, 'local', mocker.ANY)


def test_unsupported_model_raises_error(app):
    """
    Testet, ob ein nicht unterstütztes Modell einen ValueError auslöst.
    """
    with app.app_context():
        # pytest.raises ist ein Kontextmanager, der prüft, ob der umschlossene Code
        # den erwarteten Fehler auslöst. Wenn kein Fehler kommt, schlägt der Test fehl.
        with pytest.raises(ValueError, match="Streaming not supported or model family unknown"):
            generator = llm.generate_response_stream(messages=[], model='unsupported-model-9000')
            list(generator) # Der Fehler wird hier beim Konsumieren ausgelöst


def test_openai_streaming_function_yields_content(mocker, app):
    """
    Testet die _generate_with_openai_streaming Funktion selbst.
    Hier mocken wir den Aufruf an die OpenAI-Bibliothek.
    """

    # 1. ARRANGE

    # === DIE KORREKTUR: Instanzattribute in __init__ ===
    class MockDelta:
        def __init__(self, content=""):
            self.content = content

    class MockChoice:
        def __init__(self, content=""):
            # Jede MockChoice bekommt ihre EIGENE MockDelta
            self.delta = MockDelta(content)

    class MockChunk:
        def __init__(self, content=""):
            # Jeder MockChunk bekommt seine EIGENE Liste mit einer EIGENEN MockChoice
            self.choices = [MockChoice(content)]

    # Jetzt erstellen wir unterschiedliche, unabhängige Objekte
    fake_openai_stream = [
        MockChunk(content="Das "),
        MockChunk(content="ist "),
        MockChunk(content="ein Test.")
    ]
    # =======================================================

    # Der Rest des Tests bleibt gleich
    mock_openai_class = mocker.patch('backend.llm.openai.OpenAI')
    mock_openai_class.return_value.chat.completions.create.return_value = fake_openai_stream

    # 2. ACT
    with app.app_context():
        result_generator = llm._generate_with_openai_streaming(messages=[], system_prompt="Test", model="gpt-4",
                                                               max_tokens=10)
        result_list = list(result_generator)

    # 3. ASSERT
    mock_openai_class.return_value.chat.completions.create.assert_called_once()

    assert result_list == ["Das ", "ist ", "ein Test."]


def test_get_llm_user_creates_new_user_if_not_exists(mocker, app):
    """
    Testet den 'missing' Pfad in get_llm_user, wo ein neuer User
    erstellt, committet und in den Cache gelegt wird.
    """
    with app.app_context():
        # ARRANGE
        model_name = "test-model-123"

        # Leere den internen Cache, um einen sauberen Zustand sicherzustellen
        mocker.patch.dict(llm._llm_user_cache, {}, clear=True)

        # Mocke die Datenbankabfrage, damit sie "nichts findet"
        mock_query = mocker.patch('backend.models.User.query')
        mock_query.filter_by.return_value.first.return_value = None

        # Mocke die DB-Session-Methoden, um ihre Aufrufe zu verfolgen
        mock_session_add = mocker.patch('backend.models.db.session.add')
        mock_session_commit = mocker.patch('backend.models.db.session.commit')
        mock_session_refresh = mocker.patch('backend.models.db.session.refresh')

        # ACT
        user = llm.get_llm_user(model_name)

        # ASSERT
        # 1. Wurde die DB korrekt abgefragt?
        mock_query.filter_by.assert_called_once_with(username=model_name, user_type='llm_assistant')

        # 2. Wurde der neue User korrekt erstellt und der Session hinzugefügt?
        mock_session_add.assert_called_once()
        added_user = mock_session_add.call_args[0][0]  # Das erste Argument des Aufrufs
        assert isinstance(added_user, User)
        assert added_user.username == model_name
        assert added_user.display_name == "Test Model 123"

        # 3. Wurden commit und refresh aufgerufen?
        mock_session_commit.assert_called_once()
        mock_session_refresh.assert_called_once_with(added_user)

        # 4. Wurde der User dem Cache hinzugefügt?
        assert model_name in llm._llm_user_cache
        assert llm._llm_user_cache[model_name] == added_user


def test_get_llm_user_uses_cache_on_second_call(mocker, app):
    """
    Testet den 'missing' Pfad, bei dem ein User aus dem Cache geholt wird.
    Dies testet auch, dass db.session.merge aufgerufen wird.
    """
    with app.app_context():
        # ARRANGE
        model_name = "cached-model-456"
        fake_user = User(id=99, username=model_name, user_type='llm_assistant')

        # Befülle den Cache manuell
        mocker.patch.dict(llm._llm_user_cache, {model_name: fake_user}, clear=True)

        # Mocke db.session.merge, um den Aufruf zu verifizieren
        mock_merge = mocker.patch('backend.models.db.session.merge', return_value=fake_user)

        # Stelle sicher, dass die DB nicht abgefragt wird
        mock_query = mocker.patch('backend.models.User.query')

        # ACT
        user = llm.get_llm_user(model_name)

        # ASSERT
        # 1. Wurde die DB-Abfrage übersprungen?
        mock_query.filter_by.assert_not_called()

        # 2. Wurde der User aus dem Cache geholt und mit der Session "gemerged"?
        mock_merge.assert_called_once_with(fake_user)

        # 3. Ist das Ergebnis der gemergte User?
        assert user == fake_user


# ==============================================================================
# 2. Tests für Structured Response Funktionen
# ==============================================================================

def test_structured_response_router_routes_correctly(mocker, app):
    """
    Testet den Router `generate_structured_response`, um sicherzustellen,
    dass er an die richtige untergeordnete Funktion weiterleitet.
    """
    # ARRANGE
    mock_claude = mocker.patch('backend.llm._generate_structured_with_claude')
    mock_gemini = mocker.patch('backend.llm._generate_structured_with_gemini')
    mock_local = mocker.patch('backend.llm._generate_structured_with_local')

    with app.app_context():
        # ACT & ASSERT für Claude
        llm.generate_structured_response("", "", model='claude-anything')
        mock_claude.assert_called_once()
        mock_gemini.assert_not_called()
        mock_local.assert_not_called()

        # Reset mocks for next call
        mock_claude.reset_mock()

        # ACT & ASSERT für Gemini
        llm.generate_structured_response("", "", model='gemini-anything')
        mock_claude.assert_not_called()
        mock_gemini.assert_called_once()
        mock_local.assert_not_called()

        # Reset mocks for next call
        mock_gemini.reset_mock()

        # ACT & ASSERT für Local
        llm.generate_structured_response("", "", model='local-anything')
        mock_claude.assert_not_called()
        mock_gemini.assert_not_called()
        mock_local.assert_called_once()


def test_generate_structured_with_claude_parses_response(mocker, app):
    """
    Testet die Funktion `_generate_structured_with_claude` selbst.
    Mockt die Anthropic-API und prüft, ob die Antwort korrekt geparst wird.
    """
    # ARRANGE
    mock_anthropic_client = MagicMock()
    # Erstelle die komplexe, verschachtelte Antwortstruktur
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].input = {
        'tool_input': {
            'new_content': 'Dies ist der extrahierte Claude-Inhalt.'
        }
    }
    mock_anthropic_client.messages.create.return_value = mock_response
    mocker.patch('backend.llm.anthropic.Anthropic', return_value=mock_anthropic_client)

    with app.app_context():
        # ACT
        result = llm._generate_structured_with_claude("", "", "claude-3", 4096)

    # ASSERT
    mock_anthropic_client.messages.create.assert_called_once()
    assert result == 'Dies ist der extrahierte Claude-Inhalt.'


def test_generate_structured_with_gemini_parses_response(mocker, app):
    """
    Testet die Funktion `_generate_structured_with_gemini` selbst.
    Mockt die Gemini-API und prüft, ob die JSON-Antwort korrekt geparst wird.
    """
    # ARRANGE
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    # Gemini gibt die Antwort als JSON-String im .text-Attribut zurück
    mock_response.text = json.dumps({"new_content": "Dies ist der extrahierte Gemini-Inhalt."})
    mock_genai_client.models.generate_content.return_value = mock_response
    mocker.patch('backend.llm.genai.Client', return_value=mock_genai_client)

    with app.app_context():
        # ACT
        result = llm._generate_structured_with_gemini("", "", "gemini-pro", 4096)

    # ASSERT
    mock_genai_client.models.generate_content.assert_called_once()
    assert result == "Dies ist der extrahierte Gemini-Inhalt."


def test_generate_structured_with_local_parses_response(mocker, app):
    """
    Testet die Funktion `_generate_structured_with_local` selbst.
    Mockt die OpenAI-kompatible API und prüft, ob die Tool-Call-Antwort geparst wird.
    """
    # ARRANGE
    mock_openai_client = MagicMock()

    # Erstelle die verschachtelte OpenAI Tool-Call-Antwortstruktur
    mock_response = MagicMock()
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "update_content"
    mock_tool_call.function.arguments = json.dumps({"new_content": "Dies ist der extrahierte Local-Inhalt."})
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    mock_openai_client.chat.completions.create.return_value = mock_response
    mocker.patch('backend.llm.openai.OpenAI', return_value=mock_openai_client)

    with app.app_context():
        # ACT
        result = llm._generate_structured_with_local("", "", "local", 4096)

    # ASSERT
    mock_openai_client.chat.completions.create.assert_called_once()
    assert result == "Dies ist der extrahierte Local-Inhalt."


# ==============================================================================
# 3. Tests für Claude & Gemini Streaming
# ==============================================================================

def test_claude_streaming_function_yields_content(mocker, app):
    """
    Testet die _generate_with_claude_streaming Funktion selbst.
    Mockt den Aufruf an die Anthropic-Bibliothek und ihren Stream-Kontextmanager.
    """
    # ARRANGE
    # Die `text_stream` Eigenschaft ist ein Generator/Iterator
    fake_claude_stream = ["Hallo ", "Welt ", "aus ", "dem ", "Claude-Stream!"]

    # Der `stream`-Kontextmanager muss ein Objekt zurückgeben, das `text_stream` hat
    mock_stream_context = MagicMock()
    mock_stream_context.text_stream = fake_claude_stream

    mock_anthropic_client = MagicMock()
    # Die `stream` Methode muss einen Kontextmanager zurückgeben
    mock_anthropic_client.messages.stream.return_value.__enter__.return_value = mock_stream_context

    mocker.patch('backend.llm.anthropic.Anthropic', return_value=mock_anthropic_client)

    # ACT
    with app.app_context():
        result_generator = llm._generate_with_claude_streaming(messages=[], system_prompt="Test", model="claude-3",
                                                               max_tokens=10)
        result_list = list(result_generator)

    # ASSERT
    mock_anthropic_client.messages.stream.assert_called_once()
    assert result_list == ["Hallo ", "Welt ", "aus ", "dem ", "Claude-Stream!"]


def test_gemini_streaming_function_yields_content(mocker, app):
    """
    Testet die _generate_with_gemini_streaming Funktion selbst.
    Mockt den Aufruf an die Gemini-Bibliothek und simuliert den Stream.
    """

    # ARRANGE
    # Der Gemini-Stream liefert Chunk-Objekte mit einem .text Attribut
    class MockGeminiChunk:
        def __init__(self, text):
            self.text = text

    fake_gemini_stream = [
        MockGeminiChunk("Hallo "),
        MockGeminiChunk("Welt "),
        MockGeminiChunk("aus "),
        MockGeminiChunk("dem "),
        MockGeminiChunk("Gemini-Stream!"),
        MockGeminiChunk(None)  # Simuliert einen leeren Chunk, der übersprungen werden soll
    ]

    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content_stream.return_value = fake_gemini_stream
    mocker.patch('backend.llm.genai.Client', return_value=mock_genai_client)

    # ACT
    with app.app_context():
        result_generator = llm._generate_with_gemini_streaming(messages=[{'role': 'user', 'content': 'hi'}],
                                                               system_prompt="Test", model="gemini-pro", max_tokens=10)
        result_list = list(result_generator)

    # ASSERT
    mock_genai_client.models.generate_content_stream.assert_called_once()
    assert result_list == ["Hallo ", "Welt ", "aus ", "dem ", "Gemini-Stream!"]


# ==============================================================================
# 4. Tests für Wrapper und Helper
# ==============================================================================

def test_generate_response_non_streaming_uses_stream(mocker):
    """
    Testet, ob die nicht-streamende `generate_response` Funktion
    intern `generate_response_stream` aufruft und das Ergebnis zusammensetzt.
    """
    # ARRANGE
    # Mocke den Streaming-Generator, den die Funktion intern aufruft
    mock_stream_gen = mocker.patch('backend.llm.generate_response_stream')
    mock_stream_gen.return_value = (c for c in ["Das ", "ist ", "ein ", "Test."])

    # ACT
    result = llm.generate_response(messages=[], model='any-model')

    # ASSERT
    mock_stream_gen.assert_called_once()
    assert result == "Das ist ein Test."


def test_generate_response_stream_routes_to_mock_model(mocker):
    """
    Testet den 'missing' Pfad für das 'mock' Modell in `generate_response_stream`.
    """
    # ARRANGE
    mock_helper = mocker.patch('backend.llm._mock_llm_stream_generator')
    mock_helper.return_value = (c for c in ["mock ", "response"])

    # ACT
    generator = llm.generate_response_stream(messages=[], model='mock')
    result = list(generator)

    # ASSERT
    mock_helper.assert_called_once()
    assert result == ["mock ", "response"]


def test_mock_llm_stream_generator_yields_words(mocker):
    """
    Testet den Mock-Generator selbst. Wir mocken `time.sleep`,
    damit der Test sofort durchläuft.
    """
    # ARRANGE
    mocker.patch('time.sleep')  # Verhindert tatsächliches Warten
    mocker.patch('random.uniform')  # Verhindert tatsächliches Warten

    expected_text = "Antwort von MOCK-MODELL-EINS. 🤖 Dies ist die ursprüngliche Antwort."

    # ACT
    generator = llm._mock_llm_stream_generator()
    result_list = list(generator)
    result_text = "".join(result_list).strip()  # .strip() entfernt das letzte Leerzeichen

    # ASSERT
    assert result_text == expected_text
    # Wir können auch prüfen, ob es in mehreren Teilen kam
    assert len(result_list) > 1