import pytest
import json

# CORRECT: Import User model, as it's now needed in each test
from backend.models import Node, ChatSession, ChatMessage, User
from backend.services import vault_service, node_service, chat_service


# =========================================================================
# DER EIGENTLICHE, JETZT GENERALISIERTE TEST
# =========================================================================

@pytest.mark.llm
# CORRECT: Use the function-scoped 'db_session' fixture for a clean database.
def test_stream_new_message_service_with_real_llm(db_session, llm_model_name):
    """
    Testet den `chat_service.stream_new_message` Service-Layer mit einem
    echten LLM, der dynamisch über die Kommandozeile (--llm) ausgewählt wird.
    """
    # === 1. SETUP: Erstelle eine minimale Datenstruktur direkt in der DB ===
    # CORRECT: Create a user, since the DB is empty for each test run.
    test_user = User(username='stream_user', display_name='Stream User', user_type='human')
    test_user.set_password('password')
    db_session.session.add(test_user)
    db_session.session.commit()
    user_id = test_user.id

    # This will now succeed on every run because the DB is clean.
    vault = vault_service.create_vault(name="E2E Stream Service Real Test", owner_id=user_id)
    root_node = db_session.session.query(Node).filter_by(vault_id=vault.id, parent_id=None).one()
    node_a = node_service.create_node(
        title="Key Concept: Photosynthesis",
        content="Photosynthesis is the process used by plants, algae and certain bacteria to harness "
                "energy from sunlight and turn it into chemical energy.",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )
    # CORRECT: Renamed variable to 'chat_session' to avoid confusion.
    chat_session = ChatSession(vault_id=vault.id, owner_id=user_id)
    db_session.session.add(chat_session)
    db_session.session.commit()

    # === 2. EXECUTE: Rufe die Service-Funktion mit dem dynamischen Modellnamen auf ===
    print(f"\n[INFO] Running E2E test with model: {llm_model_name}")
    stream_generator = chat_service.stream_new_message(
        session_id=chat_session.id, user_id=user_id,
        user_input="Explain photosynthesis in simple terms for a child.",
        model=llm_model_name,
        node_ids=[node_a.id], client_message_id='test-client-id-123'
    )

    # === 3. ASSERT: Konsumiere den Generator und prüfe die gestreamten Daten ===
    assert hasattr(stream_generator, '__iter__'), "Die Service-Funktion muss einen Generator zurückgeben."

    full_content, user_message_server_id, assistant_message_server_id = "", None, None
    for yielded_value in stream_generator:
        if yielded_value.startswith('event:'):
            event_type = yielded_value.splitlines()[0].split(':')[1].strip()
            data = json.loads(yielded_value.splitlines()[1][len('data:'):].strip())
            if event_type == 'user_message_confirmed':
                user_message_server_id = data['server_message']['id']
            elif event_type == 'assistant_message_start':
                assistant_message_server_id = data['id']
        elif yielded_value.startswith('data:'):
            data = json.loads(yielded_value[len('data:'):].strip())
            if 'token' in data: full_content += data['token']

    print(f"\n[LLM RESPONSE ({llm_model_name})]:\n---\n{full_content}\n---")
    assert user_message_server_id is not None, "Event 'user_message_confirmed' nicht empfangen."
    assert assistant_message_server_id is not None, "Event 'assistant_message_start' nicht empfangen."

    full_content_lower = full_content.lower()
    assert any(
        keyword in full_content_lower for keyword in ["sunlight", "light", "sun"]), "Schlüsselwort für Licht fehlt."
    assert any(
        keyword in full_content_lower for keyword in ["plant", "tree", "flower"]), "Schlüsselwort für Pflanzen fehlt."
    assert any(
        keyword in full_content_lower for keyword in ["energy", "sugar", "food"]), "Schlüsselwort für Energie fehlt."

    # CORRECT: Use the 'db_session' object for database operations.
    db_session.session.commit()
    user_msg_db = db_session.session.get(ChatMessage, user_message_server_id)
    assert user_msg_db is not None
    assistant_msg_db = db_session.session.get(ChatMessage, assistant_message_server_id)
    assert assistant_msg_db is not None
    assert assistant_msg_db.content.strip() == full_content.strip()
    assert assistant_msg_db.llm_model_source == llm_model_name


@pytest.mark.llm
# CORRECT: Use the function-scoped 'db_session' fixture.
def test_propose_node_update_service_with_real_llm(db_session, llm_model_name):
    """
    Testet den `chat_service.propose_node_update_from_chat` Service-Layer
    mit einem dynamisch ausgewählten, echten LLM.
    """
    # === 1. SETUP ===
    # CORRECT: Create a user, since the DB is empty for each test run.
    test_user = User(username='proposal_user', display_name='Proposal User', user_type='human')
    test_user.set_password('password')
    db_session.session.add(test_user)
    db_session.session.commit()
    user_id = test_user.id

    vault = vault_service.create_vault(name="E2E Proposal Test Vault", owner_id=user_id)
    root_node = db_session.session.query(Node).filter_by(vault_id=vault.id, parent_id=None).one()
    context_node = node_service.create_node(
        title="Project Requirements",
        content="The project must be completed by Q4 and support multiple languages.",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )
    target_node = node_service.create_node(
        title="Team Allocation",
        content="Current team: Alice (Lead).",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )
    chat_session = ChatSession(vault_id=vault.id, owner_id=user_id)
    db_session.session.add(chat_session)
    msg1 = ChatMessage(session=chat_session, role='user', content="Who else should be on the team for this project?",
                       author_id=user_id, sort_order=1)
    db_session.session.add(msg1)
    msg2 = ChatMessage(session=chat_session, role='assistant',
                       content="Given the Q4 deadline and multi-language requirement, we should add Bob (Backend) and Carol (Frontend/Localization).",
                       author_id=user_id, sort_order=2)
    db_session.session.add(msg2)
    db_session.session.commit()

    # === 2. EXECUTE ===
    print(f"\n[INFO] Running Proposal test with model: {llm_model_name}")
    proposal_result = chat_service.propose_node_update_from_chat(
        target_node_id=target_node.id,
        session_id=chat_session.id,
        context_node_ids=[context_node.id],
        model=llm_model_name,
        user_id=user_id
    )

    # === 3. ASSERT ===
    assert isinstance(proposal_result, dict)
    assert "original_content" in proposal_result
    assert "proposed_content" in proposal_result
    original_content = proposal_result["original_content"]
    proposed_content = proposal_result["proposed_content"]

    print(f"\n[REAL LLM PROPOSAL TEST ({llm_model_name})]")
    print(f"--- ORIGINAL CONTENT ---\n{original_content}")
    print(f"--- PROPOSED CONTENT ---\n{proposed_content}")
    print(f"------------------------")

    assert original_content == "Current team: Alice (Lead)."
    assert proposed_content is not None
    assert len(proposed_content) > len(original_content)

    proposed_content_lower = proposed_content.lower()
    assert "alice" in proposed_content_lower
    assert "bob" in proposed_content_lower
    assert "carol" in proposed_content_lower
    assert any(keyword in proposed_content_lower for keyword in ["q4", "deadline", "language", "localization"])


@pytest.mark.llm
# CORRECT: Use the function-scoped 'db_session' fixture.
def test_propose_node_update_service_purely_german_context(db_session, llm_model_name):
    """
    Testet den `chat_service.propose_node_update_from_chat` Service-Layer
    mit einem rein deutschen Kontext aus dem Schulwesen, um die Sprachkonsistenz zu prüfen.
    """
    # === 1. SETUP (Rein deutscher Kontext) ===
    # CORRECT: Create a user, since the DB is empty for each test run.
    test_user = User(username='german_user', display_name='German User', user_type='human')
    test_user.set_password('password')
    db_session.session.add(test_user)
    db_session.session.commit()
    user_id = test_user.id

    vault = vault_service.create_vault(name="Deutschunterricht 10b", owner_id=user_id)
    root_node = db_session.session.query(Node).filter_by(vault_id=vault.id, parent_id=None).one()

    context_node = node_service.create_node(
        title="Lehrplan Q2: Lyrik",
        content="Behandlung der Trümmerliteratur und der Werke von Wolfgang Borchert als Pflichtthema.",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )
    target_node = node_service.create_node(
        title="Hausaufgabe bis nächste Woche",
        content="Bitte das Gedicht 'Inventur' von Günter Eich lesen.",
        parent_id=root_node.id, vault_id=vault.id, author_id=user_id
    )
    chat_session = ChatSession(vault_id=vault.id, owner_id=user_id)
    db_session.session.add(chat_session)
    msg1 = ChatMessage(session=chat_session, role='user',
                       content="Für die Hausaufgabe zu 'Inventur': Reicht es, wenn die Schüler es nur lesen? Das ist etwas wenig.",
                       author_id=user_id, sort_order=1)
    db_session.session.add(msg1)
    msg2 = ChatMessage(session=chat_session, role='assistant',
                       content="Stimmt. Da Borchert Pflicht ist, sollten sie auch seine Kurzgeschichte 'Nachts schlafen die Ratten doch' lesen und die stilistischen Mittel der Kargheit in beiden Werken vergleichen.",
                       author_id=user_id, sort_order=2)
    db_session.session.add(msg2)
    db_session.session.commit()

    # === 2. EXECUTE ===
    print(f"\n[INFO] Running pure German context test with model: {llm_model_name}")
    proposal_result = chat_service.propose_node_update_from_chat(
        target_node_id=target_node.id,
        session_id=chat_session.id,
        context_node_ids=[context_node.id],
        model=llm_model_name,
        user_id=user_id
    )

    # === 3. ASSERT ===
    assert isinstance(proposal_result, dict)
    original_content = proposal_result["original_content"]
    proposed_content = proposal_result["proposed_content"]

    print(f"\n[REAL LLM PURE GERMAN TEST ({llm_model_name})]")
    print(f"--- ORIGINAL CONTENT ---\n{original_content}")
    print(f"--- PROPOSED CONTENT ---\n{proposed_content}")
    print(f"------------------------")

    assert original_content == "Bitte das Gedicht 'Inventur' von Günter Eich lesen."
    assert proposed_content is not None
    assert "Inventur" in proposed_content

    proposed_content_lower = proposed_content.lower()
    assert "borchert" in proposed_content_lower
    assert "ratten" in proposed_content_lower

    german_keywords = ["vergleich", "stilmittel", "kargheit", "vergleichen", "stilistischen"]
    assert any(keyword in proposed_content_lower for keyword in german_keywords)

    assert "compare" not in proposed_content_lower
    assert "stylistic devices" not in proposed_content_lower