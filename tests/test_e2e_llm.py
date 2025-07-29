# tests/test_e2e_llm.py

import pytest
import os
import json
from backend.models import Node, ChatSession, ChatMessage
from backend.services import vault_service, node_service, chat_service

# Registriere die 'llm'-Markierung in deiner `backend/pytest.ini`, um die Warnung zu entfernen.
pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="LLM API keys not set in environment variables"
)


# =========================================================================
# DER EIGENTLICHE TEST
# =========================================================================

@pytest.mark.llm
def test_stream_new_message_service_with_real_claude_llm(db_session_persistent):
    """
    Testet den `chat_service.stream_new_message` Service-Layer mit einem
    echten Aufruf an die Claude-API.

    Workflow:
    1. Setup: Erstellt Vault, Nodes und eine Chat-Session direkt in der Datenbank.
    2. Execute: Ruft die `stream_new_message` Generator-Funktion direkt auf.
    3. Assert:
        - Konsumiert den Generator und prüft die Struktur der SSE-Events.
        - Stellt sicher, dass die User- und Assistenten-Nachrichten korrekt in der DB gespeichert werden.
        - Überprüft den gestreamten Inhalt auf Plausibilität und Kontextbezug.
    """
    # === 1. SETUP: Erstelle eine minimale Datenstruktur direkt in der DB ===


    # Annahme aus conftest.py: der 'integration_user' hat die ID 1
    user_id = 1

    # Erstelle Testdaten über die Services
    vault = vault_service.create_vault(name="E2E Stream Service Real Test", owner_id=user_id)
    root_node = db_session_persistent.session.query(Node).filter_by(vault_id=vault.id, parent_id=None).one()

    node_a = node_service.create_node(
        title="Key Concept: Photosynthesis",
        content="Photosynthesis is the process used by plants, algae and certain bacteria to harness "
                "energy from sunlight and turn it into chemical energy.",
        parent_id=root_node.id,
        vault_id=vault.id,
        author_id=user_id
    )

    # Erstelle eine Chat-Session direkt in der DB
    session = ChatSession(vault_id=vault.id, owner_id=user_id)
    db_session_persistent.session.add(session)
    db_session_persistent.session.commit()

    # === 2. EXECUTE: Rufe die Service-Funktion DIREKT auf ===
    # Dies ist die exakte Funktion, die wir testen wollen.
    stream_generator = chat_service.stream_new_message(
        session_id=session.id,
        user_id=user_id,
        user_input="Explain photosynthesis in simple terms for a child.",
        model='gemini-2.5-flash',  # ECHTES Modell
        node_ids=[node_a.id],
        client_message_id='test-client-id-123'
    )

    # === 3. ASSERT: Konsumiere den Generator und prüfe die gestreamten Daten ===
    assert hasattr(stream_generator, '__iter__'), "Die Service-Funktion muss einen Generator zurückgeben."

    # Sammle alle Informationen aus dem Stream
    events = []
    full_content = ""
    user_message_server_id = None
    assistant_message_server_id = None
    final_assistant_message_data = None

    for yielded_value in stream_generator:
        assert isinstance(yielded_value, str)
        events.append(yielded_value)

        # Parse die Events, um an die Daten zu kommen
        if yielded_value.startswith('event:'):
            event_type = yielded_value.splitlines()[0].split(':')[1].strip()
            data_line = yielded_value.splitlines()[1]
            data_part = data_line[len('data:'):].strip()
            data = json.loads(data_part)

            if event_type == 'user_message_confirmed':
                assert data['client_id'] == 'test-client-id-123'
                user_message_server_id = data['server_message']['id']
            elif event_type == 'assistant_message_start':
                assistant_message_server_id = data['id']
            elif event_type == 'assistant_message_end':
                final_assistant_message_data = data

        elif yielded_value.startswith('data:'):
            data_part = yielded_value[len('data:'):].strip()
            data = json.loads(data_part)
            if 'token' in data:
                full_content += data['token']

    # Gib die Antwort für die manuelle Überprüfung aus
    print(f"\n[REAL LLM STREAM RESPONSE]:\n---\n{full_content}\n---")
    # --- 3a. Prüfe die Streaming-Events ---
    assert user_message_server_id is not None, "Event 'user_message_confirmed' wurde nicht empfangen."
    assert assistant_message_server_id is not None, "Event 'assistant_message_start' wurde nicht empfangen."
    assert final_assistant_message_data is not None, "Event 'assistant_message_end' wurde nicht empfangen."

    # --- 3b. Prüfe den finalen Inhalt ---
    full_content_lower = full_content.lower()
    # Prüfe, ob mindestens EINES der Schlüsselwörter für Licht vorkommt
    assert any(keyword in full_content_lower for keyword in ["sunlight", "sunshine", "light", "sun"]), \
        "Kein Schlüsselwort für Licht (sunlight/sunshine) in der LLM-Antwort gefunden."

    # Prüfe, ob mindestens EINES der Schlüsselwörter für Pflanzen vorkommt
    assert any(keyword in full_content_lower for keyword in ["plant", "tree", "flower"]), \
        "Kein Schlüsselwort für Pflanzen (plant/tree/flower) in der LLM-Antwort gefunden."

    # Energie ist wahrscheinlich stabil, aber wir können es auch absichern
    assert "energy" in full_content_lower, "Schlüsselwort 'energy' fehlt in der LLM-Antwort."

    # --- 3c. Prüfe den Zustand in der Datenbank nach dem Stream ---
    db_session_persistent.session.commit()  # Stelle sicher, dass alle Transaktionen abgeschlossen sind

    # Prüfe die User-Nachricht
    user_msg_db = db_session_persistent.session.get(ChatMessage, user_message_server_id)
    assert user_msg_db is not None
    assert user_msg_db.content == "Explain photosynthesis in simple terms for a child."
    assert user_msg_db.sort_order == 1

    # Prüfe die Assistenten-Nachricht
    assistant_msg_db = db_session_persistent.session.get(ChatMessage, assistant_message_server_id)
    assert assistant_msg_db is not None
    assert assistant_msg_db.content.strip() == full_content.strip()  # Wichtig: Vergleiche den Inhalt
    assert assistant_msg_db.sort_order == 2
    assert assistant_msg_db.llm_model_source == 'gemini-2.5-flash'


@pytest.mark.llm
def test_propose_node_update_service_with_real_llm(db_session_persistent):
    """
    Testet den `chat_service.propose_node_update_from_chat` Service-Layer
    mit einem echten LLM-Aufruf.

    Workflow:
    1. Setup: Erstellt einen realistischen Zustand in der DB mit zwei Nodes und
       einem kurzen Chat-Verlauf, der sich auf diese Nodes bezieht.
    2. Execute: Ruft die `propose_node_update_from_chat` Service-Funktion direkt auf.
    3. Assert:
        - Überprüft, ob das Ergebnis das korrekte Format hat.
        - Überprüft den vorgeschlagenen Inhalt auf Plausibilität und stellt sicher,
          dass Informationen aus dem Chat und dem Kontext-Node verwendet wurden.
    """
    # === 1. SETUP: Erstelle einen realistischen Zustand in der DB ===
    from backend.services import vault_service, node_service, chat_service

    user_id = 1  # Annahme aus conftest.py

    # Erstelle Vault und Nodes
    vault = vault_service.create_vault(name="E2E Proposal Test Vault", owner_id=user_id)
    root_node = db_session_persistent.session.query(Node).filter_by(vault_id=vault.id, parent_id=None).one()

    # Der Node, der als zusätzlicher Kontext dient
    context_node = node_service.create_node(
        title="Project Requirements",
        content="The project must be completed by Q4 and support multiple languages.",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )

    # Der Node, der aktualisiert werden soll (der "Ziel-Node")
    target_node = node_service.create_node(
        title="Team Allocation",
        content="Current team: Alice (Lead).",  # Startinhalt ist minimal
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )

    # Erstelle eine Chat-Session und einen kurzen, relevanten Verlauf
    session = ChatSession(vault_id=vault.id, owner_id=user_id)
    db_session_persistent.session.add(session)

    # Nachricht 1 (User)
    msg1 = ChatMessage(session=session, role='user', content="Who else should be on the team for this project?",
                       author_id=user_id, sort_order=1)
    db_session_persistent.session.add(msg1)

    # Nachricht 2 (Assistant, simuliert) - diese Antwort ist entscheidend für den Vorschlag
    msg2 = ChatMessage(session=session, role='assistant',
                       content="Given the Q4 deadline and multi-language requirement, we should add Bob (Backend) and Carol (Frontend/Localization).",
                       author_id=user_id, sort_order=2)
    db_session_persistent.session.add(msg2)
    db_session_persistent.session.commit()

    # === 2. EXECUTE: Rufe die `propose_node_update_from_chat` Service-Funktion auf ===
    # Wir verwenden ein leistungsstarkes Modell, da die Aufgabe komplex ist.
    model_to_use = 'gemini-2.5-flash'

    proposal_result = chat_service.propose_node_update_from_chat(
        target_node_id=target_node.id,
        session_id=session.id,
        context_node_ids=[context_node.id],
        model=model_to_use,
        user_id=user_id
    )


    # === 3. ASSERT: Überprüfe das Ergebnis ===

    # --- 3a. Prüfe die Struktur der Antwort ---
    assert isinstance(proposal_result, dict)
    assert "original_content" in proposal_result
    assert "proposed_content" in proposal_result

    original_content = proposal_result["original_content"]
    proposed_content = proposal_result["proposed_content"]

    # Gib das Ergebnis für die manuelle Inspektion aus
    print(f"\n[REAL LLM PROPOSAL TEST]")
    print(f"--- ORIGINAL CONTENT ---\n{original_content}")
    print(f"--- PROPOSED CONTENT ---\n{proposed_content}")
    print(f"------------------------")

    assert original_content == "Current team: Alice (Lead)."
    assert proposed_content is not None
    assert len(proposed_content) > len(original_content), "Der Vorschlag sollte länger als das Original sein."

    # --- 3b. Prüfe den Inhalt auf Plausibilität (robust) ---
    # Wir prüfen, ob die KI die Informationen aus dem Chat und Kontext synthetisiert hat.
    proposed_content_lower = proposed_content.lower()

    # Aus dem Original-Node
    assert "alice" in proposed_content_lower

    # Aus der Chat-Nachricht des Assistenten
    assert "bob" in proposed_content_lower
    assert "carol" in proposed_content_lower

    # Aus dem Kontext-Node (weniger wahrscheinlich, dass es direkt zitiert wird, aber gut zu prüfen)
    # Wir verwenden eine flexible Prüfung.
    assert any(keyword in proposed_content_lower for keyword in ["q4", "deadline", "language", "localization"]), \
        "Der Vorschlag sollte idealerweise den Kontext der Projektanforderungen widerspiegeln."

