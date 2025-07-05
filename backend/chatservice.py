import logging
import re
import database
import llm
# db wird für das Transaktionsmanagement importiert (commit/rollback)
from models import db, ChatSession


# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

def list_sessions(vault_id: int) -> list[dict]:
    """
    Retrieves a list of all chat sessions for a specific vault.
    Delegates the database query to the database layer.
    """
    return database.list_chat_sessions(vault_id)


def get_session_history(session_id: str) -> dict | None:
    """
    Retrieves the complete history of a single chat session.
    Delegates the database query to the database layer.
    """
    return database.get_chat_session_history(session_id)


# ==============================================================================
# CORE CHAT LOGIC (REFAKORISIERT)
# ==============================================================================

def create_new_chat_session(user_input: str, node_ids: list, model: str, vault_id: int) -> dict:
    """
    Creates a new chat session. The user message is saved immediately.
    The AI response is generated and saved in a second, independent step.
    """
    # === TRANSAKTION 1: Session und User-Nachricht erstellen und SOFORT speichern ===
    try:
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input
        new_session = database.create_chat_session(title=title, llm_model=model, vault_id=vault_id)

        context_versions = database.get_versions_for_node_ids(node_ids, vault_id)
        database.add_chat_message(
            session_id=new_session.id,
            role='user',
            content=user_input,
            context_versions=context_versions
        )
        db.session.commit()  # Commit für Session und User-Nachricht
    except Exception as e:
        logging.error(f"FATAL: Could not even create session or save user message: {e}")
        db.session.rollback()
        raise  # Wenn das fehlschlägt, ist etwas fundamental falsch.

    # === TRANSAKTION 2: KI-Antwort generieren und speichern ===
    try:
        # Lade die Session neu, um den aktuellen Chatverlauf (inkl. der eben gespeicherten User-Nachricht) zu haben
        session_with_history = database.get_chat_session_by_id(new_session.id)
        chat_history = [{'role': msg.role, 'content': msg.content} for msg in session_with_history.messages]

        context_data = database.get_content_for_nodes(node_ids, vault_id=vault_id)
        context_content = context_data.get('content', '')

        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_content}\n</context>"
        )
        # Für die LLM brauchen wir nur die letzte User-Nachricht, da die History schon alles enthält
        messages_for_llm = chat_history

        assistant_response_text = llm.generate_response(
            messages=messages_for_llm,
            system_prompt=system_prompt,
            model=new_session.llm_model
        )

        database.add_chat_message(
            session_id=new_session.id,
            role='assistant',
            content=assistant_response_text
        )
        db.session.commit()  # Commit NUR für die KI-Antwort

        return {
            "session_id": new_session.id,
            "content": assistant_response_text,
            "role": "assistant"
        }
    except Exception as e:
        logging.error(f"AI response failed for new session {new_session.id}, but user message was saved: {e}")
        db.session.rollback()  # Wichtig: Rollt nur den Versuch zurück, die KI-Nachricht zu speichern.
        # Gib eine leere Antwort zurück, um zu signalisieren, dass die KI fehlgeschlagen ist.
        # Das Frontend kann dann den Chat neu laden und sieht die User-Nachricht allein.
        return {"session_id": new_session.id, "content": None, "role": "assistant"}


def add_message_to_session(session_id: str, user_input: str, node_ids: list) -> dict:
    """
    Adds a user message to a session immediately.
    The AI response is generated and saved in a second, independent step.
    """
    session = database.get_chat_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session with id {session_id} not found.")
    vault_id_from_session = session.vault_id

    # === TRANSAKTION 1: User-Nachricht SOFORT speichern ===
    try:
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id_from_session)
        database.add_chat_message(
            session_id=session.id,
            role='user',
            content=user_input,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logging.error(f"FATAL: Could not save user message to session {session_id}: {e}")
        db.session.rollback()
        raise

    # === TRANSAKTION 2: KI-Antwort generieren und speichern ===
    try:
        # Lade die Session neu, um den aktuellen Chatverlauf (inkl. der eben gespeicherten User-Nachricht) zu haben
        session_with_history = database.get_chat_session_by_id(session_id)
        chat_history = [{'role': msg.role, 'content': msg.content} for msg in session_with_history.messages]

        context_data = database.get_content_for_nodes(node_ids, vault_id=vault_id_from_session)
        context_content = context_data.get('content', '')

        system_prompt = (
            "You are a helpful assistant for a knowledge base. "
            "Use the following context to answer the user's question. "
            "If the context is empty, use your general knowledge.\n\n"
            f"<context>\n{context_content}\n</context>"
        )
        messages_for_llm = chat_history

        assistant_response_text = llm.generate_response(
            messages=messages_for_llm,
            system_prompt=system_prompt,
            model=session.llm_model
        )

        database.add_chat_message(
            session_id=session.id,
            role='assistant',
            content=assistant_response_text
        )
        db.session.commit()

        return {
            "session_id": session_id,
            "content": assistant_response_text,
            "role": "assistant"
        }
    except Exception as e:
        logging.error(f"AI response failed for session {session_id}, but user message was saved: {e}")
        db.session.rollback()
        # Gib eine leere Antwort zurück. Das Frontend kann darauf reagieren.
        return {"session_id": session_id, "content": None, "role": "assistant"}


def stream_new_chat_session(user_input: str, node_ids: list, model: str, vault_id: int):
    """
    Erstellt eine neue Chat-Sitzung und streamt die KI-Antwort DIREKT.
    Dies ist ein GENERATOR.
    """
    # Schritt 1: Session und User-Nachricht erstellen (unverändert)
    try:
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input
        new_session = database.create_chat_session(title=title, llm_model=model, vault_id=vault_id)
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id)
        database.add_chat_message(
            session_id=new_session.id,
            role='user',
            content=user_input,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logging.error(f"STREAM FATAL: Could not create session or save user message: {e}")
        db.session.rollback()
        yield f"error: Failed to start the chat session."
        return

    # Schritt 2: Session-ID an das Frontend senden (unverändert)
    yield f"session_id:{new_session.id}\n\n"

    # Schritt 3: Streamen und am Ende speichern
    full_assistant_response = ""
    try:
        session_with_history = database.get_chat_session_by_id(new_session.id)
        chat_history = [{'role': msg.role, 'content': msg.content} for msg in session_with_history.messages]
        context_data = database.get_content_for_nodes(node_ids, vault_id=vault_id)
        system_prompt = (
            f"You are a helpful assistant... <context>\n{context_data.get('content', '')}\n</context>"
        )

        # Holen Sie sich den rohen Stream und leiten Sie jeden Teil sofort weiter.
        raw_stream = llm.generate_response_stream(
            messages=chat_history,
            system_prompt=system_prompt,
            model=new_session.llm_model
        )

        # 2. Wickeln Sie den rohen Stream in unseren Filter-Generator
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        # 3. Iterieren Sie über den gefilterten Stream
        for chunk in filtered_stream:
            full_assistant_response += chunk
            yield chunk

        # Nach dem Stream speichern (unverändert)
        database.add_chat_message(
            session_id=new_session.id,
            role='assistant',
            content=full_assistant_response
        )
        db.session.commit()

    except Exception as e:
        logging.error(f"STREAM AI FAILED for new session {new_session.id}: {e}")
        db.session.rollback()
        yield f"\n\nerror: The AI failed to generate a response. Your message has been saved."


def stream_message_in_session(session_id: str, user_input: str, node_ids: list):
    """
    Adds a message to an existing session and streams the AI response.
    This is a GENERATOR.
    """
    session = database.get_chat_session_by_id(session_id)
    if not session:
        yield f"error: Session with id {session_id} not found."
        return
    vault_id = session.vault_id

    # === Step 1: Save the user message immediately (like your Transaction 1) ===
    try:
        context_versions = database.get_versions_for_node_ids(node_ids, vault_id)
        database.add_chat_message(
            session_id=session.id,
            role='user',
            content=user_input,
            context_versions=context_versions
        )
        db.session.commit()
    except Exception as e:
        logging.error(f"STREAM FATAL: Could not save user message to session {session_id}: {e}")
        db.session.rollback()
        yield f"error: Failed to save your message. Please try again."
        return

    # Schritt 2: Streamen und am Ende speichern
    full_assistant_response = ""
    try:
        session_with_history = database.get_chat_session_by_id(session_id)
        chat_history = [{'role': msg.role, 'content': msg.content} for msg in session_with_history.messages]
        context_data = database.get_content_for_nodes(node_ids, vault_id=session_with_history.vault_id)
        system_prompt = (
            f"You are a helpful assistant... <context>\n{context_data.get('content', '')}\n</context>"
        )

        # Holen Sie sich den rohen Stream und leiten Sie jeden Teil sofort weiter.
        raw_stream = llm.generate_response_stream(
            messages=chat_history,
            system_prompt=system_prompt,
            model=session_with_history.llm_model
        )

        # 2. Wickeln Sie den rohen Stream in unseren Filter-Generator
        filtered_stream = _filter_think_tags_from_stream(raw_stream)

        # 3. Iterieren Sie über den gefilterten Stream
        for chunk in filtered_stream:
            full_assistant_response += chunk
            yield chunk

        # Nach dem Stream speichern (unverändert)
        if full_assistant_response:
            database.add_chat_message(
                session_id=session.id,
                role='assistant',
                content=full_assistant_response
            )
            db.session.commit()

    except Exception as e:
        logging.error(f"STREAM AI FAILED for session {session_id}: {e}")
        db.session.rollback()
        yield f"\n\nerror: The AI failed to generate a response. Your message has been saved."



# ==============================================================================
# ADVANCED FEATURES (e.g., Node Update Proposals)
# ==============================================================================

def propose_node_update_from_chat(target_node_id: str, chat_history: str, context_node_ids: list, model: str,
                                  vault_id: int) -> dict:
    """
    Generates a suggestion to update a node's content based on a chat conversation.
    """
    try:
        # --- DATA GATHERING ---
        target_node_data = database.get_node_by_id(target_node_id, vault_id=vault_id)
        if not target_node_data:
            raise ValueError(f"Target node with ID {target_node_id} not found in vault {vault_id}.")

        target_title = target_node_data['title']
        original_content = target_node_data['content']

        # --- CONTEXT FETCHING (CLEANED UP) ---
        context_content = ""
        context_titles = []
        if context_node_ids:
            # Use the same reliable function, but this time we also need the titles.
            context_data = database.get_content_for_nodes(context_node_ids, vault_id=vault_id)
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
Now, please analyze all the information, follow all rules (especially the language rule), and provide the updated content for the node '{target_title}' in the required JSON format. Use your own knowledge. /no_think
        """

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
        logging.error(f"Error in propose_node_update_from_chat: {e}")
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