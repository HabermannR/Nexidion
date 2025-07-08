# chatservice.py (Multi-User-Version)

import logging
from models import db
import database
import llm

logger = logging.getLogger(__name__)
# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

def list_sessions(vault_id: int, user_id: int) -> list[dict]:
    """
    MODIFIZIERT: Ruft die Chat-Sitzungen für einen bestimmten Benutzer in einem Vault ab.
    Delegiert die Abfrage vollständig an die Datenbankschicht, die die Autorisierung durchführt.
    """
    return database.list_chat_sessions(vault_id=vault_id, user_id=user_id)


def get_session_history(session_id: str, user_id: int) -> dict | None:
    """
    MODIFIZIERT: Ruft die Historie einer Sitzung ab.
    Delegiert die Abfrage an die Datenbankschicht, die den Besitz der Sitzung überprüft.
    """
    return database.get_chat_session_history(session_id=session_id, user_id=user_id)


# ==============================================================================
# CORE CHAT LOGIC (NON-STREAMING)
# ==============================================================================

def create_new_chat_session(user_input: str, node_ids: list, model: str, vault_id: int, user_id: int) -> dict:
    """
    MODIFIZIERT: Erstellt eine neue Chat-Sitzung, die einem Benutzer gehört.
    """
    # === TRANSAKTION 1: Session und User-Nachricht erstellen und SOFORT speichern ===
    try:
        # Titel für die neue Session generieren
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input
        # Session in der DB erstellen, gehört jetzt dem `user_id`
        new_session = database.create_chat_session(title=title, vault_id=vault_id, owner_id=user_id)

        # Kontext für die Benutzernachricht holen (Autorisierungscheck passiert in der DB-Funktion)
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id, user_id)
        # Benutzernachricht speichern, mit dem `user_id` als Autor
        database.add_chat_message(
            session_id=new_session.id,
            role='user',
            content=user_input,
            author_id=user_id,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"FATAL: Could not create session or save user message for user {user_id}: {e}")
        db.session.rollback()
        raise

    # === TRANSAKTION 2: KI-Antwort generieren und speichern ===
    try:
        # Holen Sie sich den Assistant-User aus der DB, um ihn als Autor zu verwenden
        assistant_user = llm.get_llm_user(model)

        # Verlauf und Kontext holen
        history = database.get_chat_session_history(new_session.id, user_id)
        chat_history = history.get('messages', [])
        context_data = database.get_content_for_nodes(node_ids, vault_id, user_id)
        context_content = context_data.get('content', '')
        system_prompt = f"You are a helpful assistant... <context>\n{context_content}\n</context>"

        # LLM-Antwort generieren
        assistant_response_text = llm.generate_response(
            messages=chat_history,
            system_prompt=system_prompt,
            model=model
        )

        # KI-Nachricht speichern, mit dem `assistant_user` als Autor
        database.add_chat_message(
            session_id=new_session.id,
            role='assistant',
            content=assistant_response_text,
            author_id=assistant_user.id,
            llm_model_source=model  # Speichert das verwendete Modell
        )
        db.session.commit()

        return {
            "session_id": new_session.id,
            "content": assistant_response_text,
            "role": "assistant"
        }
    except Exception as e:
        logger.error(f"AI response failed for new session {new_session.id}, but user message was saved: {e}")
        db.session.rollback()
        return {"session_id": new_session.id, "content": None, "role": "assistant"}


def add_message_to_session(session_id: str, user_input: str, node_ids: list, user_id: int) -> dict:
    """
    MODIFIZIERT: Fügt eine Nachricht zu einer bestehenden Sitzung hinzu und prüft den Besitz.
    """
    # === Autorisierung und Vorbereitung ===
    session = database.get_chat_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session with id {session_id} not found.")
    if session.owner_id != user_id:
        raise PermissionError("You do not have permission to access this chat session.")

    # === TRANSAKTION 1: User-Nachricht SOFORT speichern ===
    try:
        context_versions = database.get_versions_for_node_ids(node_ids, session.vault_id, user_id)
        database.add_chat_message(
            session_id=session.id,
            role='user',
            content=user_input,
            author_id=user_id,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"FATAL: Could not save user message to session {session_id} for user {user_id}: {e}")
        db.session.rollback()
        raise

    # === TRANSAKTION 2: KI-Antwort generieren und speichern ===
    try:
        # Bestimme das Modell für die Antwort. Nimm das der letzten Assistenten-Nachricht oder ein Default.
        last_assistant_msg = next(
            (msg for msg in reversed(session.messages) if msg.role == 'assistant' and msg.llm_model_source), None)
        model_to_use = last_assistant_msg.llm_model_source if last_assistant_msg else 'claude-3-haiku-20240307'  # Fallback

        assistant_user = llm.get_llm_user(model_to_use)

        history = database.get_chat_session_history(session_id, user_id)
        chat_history = history.get('messages', [])
        context_data = database.get_content_for_nodes(node_ids, session.vault_id, user_id)
        system_prompt = f"You are a helpful assistant... <context>\n{context_data.get('content', '')}\n</context>"

        assistant_response_text = llm.generate_response(
            messages=chat_history,
            system_prompt=system_prompt,
            model=model_to_use
        )

        database.add_chat_message(
            session_id=session.id,
            role='assistant',
            content=assistant_response_text,
            author_id=assistant_user.id,
            llm_model_source=model_to_use
        )
        db.session.commit()

        return {"session_id": session_id, "content": assistant_response_text, "role": "assistant"}
    except Exception as e:
        logger.error(f"AI response failed for session {session_id}, but user message was saved: {e}")
        db.session.rollback()
        return {"session_id": session_id, "content": None, "role": "assistant"}


# ==============================================================================
# CORE CHAT LOGIC (STREAMING)
# ==============================================================================

def stream_new_chat_session(user_input: str, node_ids: list, model: str, vault_id: int, user_id: int):
    """
    MODIFIZIERT: Erstellt eine neue Chat-Sitzung für einen Benutzer und streamt die Antwort.
    """
    # Schritt 1: Session und User-Nachricht erstellen
    try:
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input
        new_session = database.create_chat_session(title=title, vault_id=vault_id, owner_id=user_id)
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id, user_id)
        database.add_chat_message(
            session_id=new_session.id,
            role='user',
            content=user_input,
            author_id=user_id,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL for user {user_id}: {e}")
        db.session.rollback()
        yield f"error: Failed to start the chat session."
        return

    yield f"session_id:{new_session.id}\n\n"

    logger.info(f"chatservice Initiating stream for model {model}")
    # Schritt 2: Streamen und am Ende speichern
    full_assistant_response = ""
    try:
        logger.info(f"Test")
        assistant_user_id = llm.get_llm_user(model).id
        logger.info(f"assistant_user {assistant_user_id}")
        history = database.get_chat_session_history(new_session.id, user_id)
        chat_history = history.get('messages', [])
        context_data = database.get_content_for_nodes(node_ids, vault_id, user_id)

        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )
        logger.info(f"start stream")
        raw_stream = llm.generate_response_stream(messages=chat_history, system_prompt=system_prompt, model=model)
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        for chunk in filtered_stream:
            full_assistant_response += chunk
            yield chunk

        if full_assistant_response:
            database.add_chat_message(
                session_id=new_session.id,
                role='assistant',
                content=full_assistant_response,
                author_id=assistant_user_id,
                llm_model_source=model
            )
            db.session.commit()
    except Exception as e:
        logger.error(f"STREAM AI FAILED for new session {new_session.id}: {e}", exc_info=True)
        db.session.rollback()
        yield f"\n\nerror: The AI failed to generate a response."



def stream_message_in_session(session_id: str, user_input: str, node_ids: list, user_id: int):
    """
    MODIFIZIERT: Fügt Nachricht zu bestehender Session hinzu, prüft Besitz und streamt.
    """
    # Autorisierung
    session = database.get_chat_session_by_id(session_id)
    if not session:
        yield f"error: Session with id {session_id} not found."
        return
    if session.owner_id != user_id:
        yield f"error: You do not have permission to access this chat session."
        return

    # Schritt 1: Benutzernachricht speichern
    try:
        context_versions = database.get_versions_for_node_ids(node_ids, session.vault_id, user_id)
        database.add_chat_message(
            session_id=session.id, role='user', content=user_input, author_id=user_id, context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL for user {user_id}: {e}")
        db.session.rollback()
        yield f"error: Failed to save your message."
        return

    # Schritt 2: Streamen und am Ende speichern
    full_assistant_response = ""
    try:
        last_assistant_msg = next((msg for msg in reversed(session.messages) if msg.role == 'assistant' and msg.llm_model_source), None)
        model_to_use = last_assistant_msg.llm_model_source if last_assistant_msg else 'claude-3-haiku-20240307'

        assistant_user_id = llm.get_llm_user(model_to_use).id
        history = database.get_chat_session_history(session.id, user_id)
        chat_history = history.get('messages', [])
        context_data = database.get_content_for_nodes(node_ids, session.vault_id, user_id)
        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )

        raw_stream = llm.generate_response_stream(messages=chat_history, system_prompt=system_prompt,
                                                  model=model_to_use)
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        for chunk in filtered_stream:
            full_assistant_response += chunk
            yield chunk

        if full_assistant_response:
            database.add_chat_message(
                session_id=session.id,
                role='assistant',
                content=full_assistant_response,
                author_id=assistant_user_id,
                llm_model_source=model_to_use
            )
            db.session.commit()
    except Exception as e:
        logger.error(f"STREAM AI FAILED for session {session_id}: {e}")
        db.session.rollback()
        yield f"\n\nerror: The AI failed to generate a response."



# ==============================================================================
# ADVANCED FEATURES (e.g., Node Update Proposals)
# ==============================================================================

def propose_node_update_from_chat(target_node_id: str, chat_history: str, context_node_ids: list, model: str, vault_id: int, user_id: int) -> dict:
    """
    MODIFIZIERT: Generiert einen Update-Vorschlag und prüft den Zugriff auf alle beteiligten Nodes.
    """
    try:
        # DATA GATHERING (Autorisierung passiert in den DB-Funktionen)
        target_node_data = database.get_node_by_id(target_node_id, vault_id=vault_id, user_id=user_id)
        if not target_node_data:
            raise ValueError(f"Target node with ID {target_node_id} not found in your vault.")

        target_title = target_node_data['title']
        original_content = target_node_data['content']

        # --- CONTEXT FETCHING (CLEANED UP) ---
        context_content = ""
        context_titles = []
        if context_node_ids:
            # Use the same reliable function, but this time we also need the titles.
            context_data = database.get_content_for_nodes(node_ids=context_node_ids, vault_id=vault_id, user_id=user_id)
            context_content = context_data.get('content', '')
            context_titles = context_data.get('titles', [])

        # --- PROMPT ENGINEERING ---
        system_prompt = """
You are an expert content editor for a knowledge base. Your task is to update the content of a specific knowledge node based on a chat conversation and additional context.
Carefully analyze the 'Original Content of the Node to Update', the 'Full Chat History', and the 'Additional Context'.
Your goal is to synthesize the information to create a new, improved, and complete version of the node's content. Use also knowledge you have additionally.
***IMPORTANT LANGUAGE RULE: The 'new_content' you generate MUST be in the same language as the 'Original Content of the Node to Update'. Do not translate it. If the original is in German, the new content must be in German.***
The final output MUST be a single, complete text that will entirely replace the original content.
You MUST provide your response ONLY in the following JSON format:
{
  "tool_input": {
    "new_content": "The full, rewritten content for the node goes here, in the original language, using proper Markdown formatting."
  }
}
        """
        user_prompt = f"""
Here is the data for your task:
---
**Original Content of the Node to Update (Title: {target_title})**
---
{original_content}
---
**Full Chat History**
---
{chat_history}
---
**Additional Context from Nodes: {', '.join(context_titles)}**
---
{context_content}
---
Now, please analyze all the information, follow all rules (especially the language rule), and provide the updated content for the node '{target_title}' in the required JSON format. Use your own knowledge."""

        # --- LLM CALL ---
        proposed_content = llm.generate_structured_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )
        return {
            "original_content": original_content,
            "proposed_content": proposed_content
        }

    except Exception as e:
        logger.error(f"Error in propose_node_update_from_chat: {e}")
        raise


def _filter_think_tags_from_stream(stream_generator):
    """
    (KORRIGIERTE VERSION) Filtert <think>-Tags und streamt IMMER,
    auch wenn keine Tags vorhanden sind.
    """
    buffer = ""
    in_think_block = False

    for chunk in stream_generator:
        buffer += chunk

        while True:  # Verarbeite den Puffer, bis er "stabil" ist
            if in_think_block:
                end_tag_pos = buffer.find("</think>")
                if end_tag_pos != -1:
                    buffer = buffer[end_tag_pos + len("</think>"):]
                    in_think_block = False
                    continue  # Starte die Schleife neu, um den Rest des Puffers zu prüfen
                else:
                    # Ende-Tag noch nicht da, warte auf mehr Chunks
                    break  # Verlasse die while-Schleife für diesen Chunk
            else:  # NICHT in einem think-Block
                start_tag_pos = buffer.find("<think>")
                if start_tag_pos != -1:
                    # Anfangs-Tag gefunden
                    content_to_yield = buffer[:start_tag_pos]
                    if content_to_yield:
                        yield content_to_yield

                    buffer = buffer[start_tag_pos + len("<think>"):]
                    in_think_block = True
                    continue  # Starte die Schleife neu
                else:
                    # KEIN Tag im Puffer gefunden.
                    # Dies ist der entscheidende Fix: Gib den Puffer aus und leere ihn.
                    if buffer:
                        yield buffer
                    buffer = ""
                    break  # Verlasse die while-Schleife für diesen Chunk

    # Dieser letzte Check ist jetzt überflüssig, wenn die Schleife korrekt ist,
    # aber als Sicherheitsnetz schadet er nicht.
    if buffer and not in_think_block:
        yield buffer