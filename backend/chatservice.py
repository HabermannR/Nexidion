# backend/chatservice.py

import logging
from backend.models import db, ChatMessage  # Corrected imports
import backend.database as database
import backend.llm as llm

logger = logging.getLogger(__name__)


# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

def list_sessions(vault_id: int, user_id: int) -> list[dict]:
    """Delegates to the database layer for listing sessions for a user."""
    return database.list_chat_sessions(vault_id=vault_id, user_id=user_id)


def get_session_history(session_id: str, user_id: int) -> dict | None:
    """Delegates to the database layer for getting session history, which handles auth."""
    # This now assumes database layer returns a full DTO, not a raw object
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
        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )

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
        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )

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
    # Step 1: Create session and user message
    try:
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input
        new_session = database.create_chat_session(title=title, vault_id=vault_id, owner_id=user_id)
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id, user_id)
        database.add_chat_message(
            session_id=new_session.id, role='user', content=user_input, author_id=user_id,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL on create for user {user_id}: {e}", exc_info=True)
        db.session.rollback()
        yield f"error: Failed to start the chat session."
        return

    yield f"session_id:{new_session.id}\n\n"

    # Step 2: Create an EMPTY assistant message immediately
    try:
        assistant_user_id = llm.get_llm_user(model).id
        assistant_message = database.add_chat_message(
            session_id=new_session.id, role='assistant', content="", author_id=assistant_user_id, llm_model_source=model
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL: Could not create empty assistant message: {e}", exc_info=True)
        db.session.rollback()
        yield f"error: Failed to prepare the AI response."
        return

    # === PRIMARY FIX: Correct yield format ===
    yield f"message_id:{assistant_message.id}\n\n"

    # Step 3: Stream the response from the LLM
    full_assistant_response = ""
    try:
        # === CONSISTENCY FIX: Use same data gathering as non-streaming functions ===
        history = database.get_chat_session_history(new_session.id, user_id)
        chat_history = history.get('messages', [])
        context_data = database.get_content_for_nodes(node_ids, vault_id, user_id)
        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )

        raw_stream = llm.generate_response_stream(messages=chat_history, system_prompt=system_prompt, model=model)
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        for chunk in filtered_stream:
            full_assistant_response += chunk
            yield chunk
    except Exception as e:
        logger.error(f"STREAM AI FAILED for new session {new_session.id}: {e}", exc_info=True)
        yield f"error: The AI stream was interrupted."
    finally:
        # Step 4: Update the message with the final content
        if full_assistant_response:
            try:
                message_to_update = db.session.get(ChatMessage, assistant_message.id)
                if message_to_update:
                    message_to_update.content = full_assistant_response.strip()
                    db.session.commit()
            except Exception as e:
                logger.error(f"Failed to update final message content for {assistant_message.id}: {e}", exc_info=True)
                db.session.rollback()


def stream_message_in_session(session_id: str, user_input: str, node_ids: list, user_id: int,
                              default_model_from_config: str, model: str | None = None):
    """
    KORRIGIERT: Fügt eine Nachricht zu einer bestehenden Sitzung hinzu und streamt die Antwort.
    - Der Parameter 'model_override' wurde in 'model' umbenannt, um konsistent zu sein.
    - Die Logik zur Modellauswahl wurde verbessert: Sie verwendet das explizite Modell,
      fällt auf das letzte Modell der Sitzung zurück und erst dann auf den globalen Default.
    """
    session = database.get_chat_session_by_id(session_id)
    if not session:
        yield f"error: Session with id {session_id} not found or permission denied.\n\n"
        return

    # Step 1: Determine model to use and save user message
    try:
        # === FIX: Verbesserte und konsistente Logik zur Modellauswahl ===
        if model:
            model_to_use = model
            logger.info(f"Using explicit model override for session {session_id}: '{model_to_use}'")
        else:
            # Finde die letzte Assistant-Nachricht, um das Modell der Konversation zu übernehmen
            last_assistant_msg = next(
                (msg for msg in reversed(session.messages) if msg.role == 'assistant' and msg.llm_model_source), None)
            if last_assistant_msg and last_assistant_msg.llm_model_source:
                model_to_use = last_assistant_msg.llm_model_source
                logger.info(f"Continuing session {session_id} with last used model: '{model_to_use}'")
            else:
                model_to_use = default_model_from_config
                logger.info(f"No previous model in session {session_id}. Using default: '{model_to_use}'")

        context_versions = database.get_versions_for_node_ids(node_ids, session.vault_id, user_id)
        database.add_chat_message(
            session_id=session.id, role='user', content=user_input, author_id=user_id, context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL saving user message for user {user_id}: {e}", exc_info=True)
        db.session.rollback()
        yield f"error: Failed to save your message."
        return

    # Step 2: Create EMPTY assistant message
    try:
        assistant_user_id = llm.get_llm_user(model_to_use).id
        assistant_message = database.add_chat_message(
            session_id=session.id, role='assistant', content="", author_id=assistant_user_id,
            llm_model_source=model_to_use
        )
        db.session.commit()
    except Exception as e:
        logger.error(f"STREAM FATAL: Could not create empty assistant message: {e}", exc_info=True)
        db.session.rollback()
        yield f"error: Failed to prepare the AI response."
        return

    yield f"message_id:{assistant_message.id}\n\n"

    # Step 3: Stream the response
    full_assistant_response = ""
    try:
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
    except Exception as e:
        logger.error(f"STREAM AI FAILED for session {session_id}: {e}", exc_info=True)
        yield f"error: The AI stream was interrupted."
    finally:
        # Step 4: Update final content
        if full_assistant_response:
            try:
                message_to_update = db.session.get(ChatMessage, assistant_message.id)
                if message_to_update:
                    message_to_update.content = full_assistant_response.strip()
                    db.session.commit()
            except Exception as e:
                logger.error(f"Failed to update final message content for {assistant_message.id}: {e}", exc_info=True)
                db.session.rollback()


def retry_specific_message_stream(session_id: str, message_id: int, user_id: int, model: str = None):
    session = database.get_chat_session_by_id(session_id)
    if not session:
        yield f"error: Session with id {session_id} not found.\n\n"
        return

    target_message = db.session.get(ChatMessage, message_id)
    if not target_message or target_message.session_id != session.id:
        yield f"error: Message {message_id} not found in this session.\n\n"
        return

    message_index = session.messages.index(target_message)
    prompting_message = session.messages[message_index - 1] if message_index > 0 else None
    if not prompting_message:
        yield f"error: Cannot retry the first message."
        return

    # Model selection logic: use provided model, fallback to latest assistant model, then original message model
    if model:
        model_to_use = model
        logger.info(f"Retrying message {message_id} with explicitly provided model: '{model_to_use}'")
    else:
        # Find the most recent assistant message to get the "current" session model
        latest_assistant_message = None
        for msg in reversed(session.messages):
            if msg.role == 'assistant' and msg.llm_model_source:
                latest_assistant_message = msg
                break

        if latest_assistant_message and latest_assistant_message.llm_model_source:
            model_to_use = latest_assistant_message.llm_model_source
            logger.info(f"Retrying message {message_id} using latest assistant model: '{model_to_use}'")
        else:
            # Fallback to original message model
            model_to_use = target_message.llm_model_source
            logger.info(f"Retrying message {message_id} using original message model: '{model_to_use}'")

    # Prepare message for retry
    try:
        assistant_user = llm.get_llm_user(model_to_use)
        target_message.content = ""
        target_message.author_id = assistant_user.id
        target_message.llm_model_source = model_to_use  # Update with the model being used
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        yield f"error: Could not prepare message for retry with model '{model_to_use}': {str(e)}"
        return

    # Stream new response
    full_new_response = ""
    try:
        # === CONSISTENCY FIX: Use same data gathering pattern ===
        history_for_llm = database.get_chat_session_history(session.id, user_id)['messages'][:message_index]
        context_node_ids = [v.node_id for v in prompting_message.context_versions]
        context_data = database.get_content_for_nodes(context_node_ids, session.vault_id, user_id)
        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_data.get('content', '')}\n</context>"
        )

        raw_stream = llm.generate_response_stream(messages=history_for_llm, system_prompt=system_prompt,
                                                  model=model_to_use)
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        for chunk in filtered_stream:
            full_new_response += chunk
            yield chunk
    except Exception as e:
        logger.error(f"STREAM RETRY FAILED for message {target_message.id} with model '{model_to_use}': {e}",
                     exc_info=True)
        yield f"error: The AI stream was interrupted during retry with model '{model_to_use}'."
    finally:
        if full_new_response:
            target_message.content = full_new_response.strip()
            db.session.commit()


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