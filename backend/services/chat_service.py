# backend/services/chat_service.py

import logging
import json
from flask import current_app
from sqlalchemy import func

from backend.models import db, ChatSession, ChatMessage
from backend.services import llm_service, node_service
from .vault_service import _verify_vault_access


logger = logging.getLogger(__name__)


# --- Helper für Berechtigungsprüfung ---
# Diese bleiben hier, da sie Teil der Business-Logik sind.



def _verify_session_access(session_id: str, user_id: int) -> ChatSession:
    """Prüft, ob ein User Zugriff auf eine Session hat und gibt sie zurück."""
    session = db.session.get(ChatSession, session_id)
    if not session:
        raise ValueError(f"Chat session with ID {session_id} not found.")
    _verify_vault_access(session.vault_id, user_id)
    return session


# --- Privater Helper zum Vorbereiten des LLM-Kontexts ---
def _prepare_llm_context(session: ChatSession, node_ids: list, user_id: int) -> tuple[str, list]:
    context_content = ""
    if node_ids:
        context_data = node_service.get_content_for_nodes(node_ids, session.vault_id, user_id)
        context_content = context_data.get('content', '')

    system_prompt = (
        "You are a helpful assistant for a knowledge base. "
        "Use the following context to answer the user's question. "
        "If the context is empty, use your general knowledge.\n\n"
        f"<context>\n{context_content}\n</context>"
    )

    # *** GEÄNDERT: Sortierung nach sort_order ***
    active_messages = session.messages.filter_by(status='active').order_by(ChatMessage.sort_order.asc()).all()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in active_messages]

    return system_prompt, chat_history


# --- Kernfunktionen (Streaming-First-Ansatz) ---

# in backend/services/chat_service.py

def stream_new_message(session_id: str, user_id: int, user_input: str, model: str, node_ids: list,
                       client_message_id: str = None):
    """
    Fügt eine User-Nachricht und die gestreamte Antwort des Assistenten hinzu.
    Speichert eine Teil-Antwort, wenn der Stream fehlschlägt.
    """
    # Schritt 1 (User-Nachricht) bleibt unverändert.
    # Wir nehmen ihn aus dem Haupt-try/except, da ein Fehler hier anders behandelt werden sollte.
    try:
        session = _verify_session_access(session_id, user_id)
        max_sort_order = db.session.query(func.max(ChatMessage.sort_order)).filter_by(
            session_id=session.id).scalar() or 0
        user_message_sort_order = max_sort_order + 1

        context_versions = []
        if node_ids:
            context_nodes = node_service.get_nodes_by_ids_for_user(node_ids, session.vault_id, user_id)
            context_versions = [node.current_version_object for node in context_nodes if node.current_version_object]

        user_message = ChatMessage(
            session_id=session.id, role='user', content=user_input, author_id=user_id, status='active',
            context_versions=context_versions, sort_order=user_message_sort_order
        )
        db.session.add(user_message)
        db.session.commit()

        if client_message_id:
            confirmation_data = {"client_id": client_message_id, "server_message": user_message.to_dict()}
            yield f"event: user_message_confirmed\ndata: {json.dumps(confirmation_data)}\n\n"
        else:
            yield f"event: user_message\ndata: {json.dumps(user_message.to_dict())}\n\n"
    except Exception as e:
        db.session.rollback()
        logger.error(f"STREAM (New Message - User Part): Fehler beim Erstellen der User-Nachricht: {e}", exc_info=True)
        error_payload = {'error': 'A server error occurred while saving your message.'}
        if client_message_id: error_payload['client_id'] = client_message_id
        yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        return

    # Schritt 2 und 3: Assistenten-Nachricht mit robuster Fehlerbehandlung
    assistant_sort_order = user_message_sort_order + 1
    chosen_model = model or current_app.config.get('DEFAULT_CHAT_MODEL', 'claude-3-haiku-20240307')
    full_response = ""
    assistant_message = None

    try:
        # Assistenten-Nachricht erstellen und committen, um eine ID zu haben
        assistant_user = llm_service.get_llm_user(chosen_model)
        assistant_message = ChatMessage(
            session_id=session.id, role='assistant', content="", author_id=assistant_user.id,
            status='active', llm_model_source=chosen_model, sort_order=assistant_sort_order
        )
        db.session.add(assistant_message)
        db.session.commit()
        yield f"event: assistant_message_start\ndata: {json.dumps(assistant_message.to_dict())}\n\n"

        # Kontext vorbereiten
        system_prompt, all_messages_for_llm = _prepare_llm_context(session, node_ids, user_id)

        # Der fehleranfällige Stream-Aufruf
        llm_stream = llm_service.generate_response_stream(
            messages=all_messages_for_llm, system_prompt=system_prompt, model=chosen_model
        )

        for chunk in llm_stream:
            if chunk:
                full_response += chunk
                payload = {"id": str(assistant_message.id), "token": chunk}
                yield f"data: {json.dumps(payload)}\n\n"

        # --- Wenn wir hier ankommen, war der Stream erfolgreich (Happy Path) ---
        db.session.refresh(assistant_message)
        assistant_message.content = full_response.strip()

        title_was_updated = False
        is_first_assistant_message = db.session.query(ChatMessage).filter_by(
            session_id=session.id, role='assistant').count() == 1

        if is_first_assistant_message and session.title == "New Chat":
            history_for_title = f"User: {user_input}\nAssistant: {full_response.strip()}"
            new_title = llm_service.generate_chat_title(history_for_title, model=chosen_model)
            session.title = new_title
            title_was_updated = True

        db.session.commit()

        yield f"event: assistant_message_end\ndata: {json.dumps(assistant_message.to_dict())}\n\n"
        if title_was_updated:
            session_update_payload = {"id": session.id, "title": session.title}
            yield f"event: session_updated\ndata: {json.dumps(session_update_payload)}\n\n"

    except Exception as e:
        # --- Hier landen wir, wenn der Stream eine Exception wirft (Error Path) ---
        logger.error(f"STREAM (New Message - LLM Part): Fehler beim Streamen: {e}", exc_info=True)

        # WICHTIG: Speichere die Teil-Antwort, anstatt ein Rollback durchzuführen
        if assistant_message and full_response:
            try:
                db.session.refresh(assistant_message)
                assistant_message.content = full_response.strip()
                db.session.commit()
                logger.info(f"Teil-Antwort für Nachricht {assistant_message.id} wurde erfolgreich gespeichert.")
            except Exception as db_err:
                logger.error(f"Konnte Teil-Antwort nicht speichern nach Stream-Fehler: {db_err}", exc_info=True)
                db.session.rollback()

        error_payload = {'error': 'A server error occurred while generating the response.'}
        if client_message_id: error_payload['client_id'] = client_message_id
        yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        return


def stream_retry_message(session_id: str, message_id: str, user_id: int, model: str):
    """
    Generiert eine neue Antwort für eine User-Nachricht.
    - Ersetzt eine existierende Antwort, indem sie deren Status auf 'retried' setzt.
    - Fügt eine neue Antwort ein und verschiebt nachfolgende, falls keine zu ersetzen ist.
    Arbeitet innerhalb einer einzigen Transaktion, um Konsistenz zu gewährleisten.
    """
    session = _verify_session_access(session_id, user_id)
    full_response = ""
    new_assistant_message = None

    try:
        user_message_to_retry = db.session.get(ChatMessage, message_id)
        if not user_message_to_retry or user_message_to_retry.role != 'user':
            raise ValueError("Message to resubmit not found or is not a user message.")

        # --- Schritt 1: Finde die zu ersetzende Nachricht ---
        # Wichtig: Noch kein Commit hier!

        message_to_replace = db.session.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.sort_order == user_message_to_retry.sort_order + 1,
            ChatMessage.role == 'assistant'
        ).with_for_update().one_or_none()  # `one_or_none` ist sicherer

        if message_to_replace:
            # FALL A: Ersetzen
            logger.info(f"Resubmit: Marking message {message_to_replace.id} as 'retried'.")
            message_to_replace.status = 'retried'
            new_assistant_sort_order = message_to_replace.sort_order

            # Sende sofort das UI-Update. Der Client kann darauf reagieren.
            update_data = {"id": str(message_to_replace.id), "status": "retried"}
            yield f"event: message_status_updated\ndata: {json.dumps(update_data)}\n\n"
        else:
            # FALL B: Einfügen und verschieben
            new_assistant_sort_order = user_message_to_retry.sort_order + 1
            logger.info(f"Resubmit: Inserting new response at sort_order {new_assistant_sort_order}.")
            db.session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.sort_order >= new_assistant_sort_order
            ).update({'sort_order': ChatMessage.sort_order + 1}, synchronize_session='fetch')

        # --- Schritt 2: Neue Antwort vorbereiten (immer noch in derselben Transaktion) ---

        chosen_model = model or current_app.config.get('DEFAULT_CHAT_MODEL', 'claude-3-haiku-20240307')
        assistant_user = llm_service.get_llm_user(chosen_model)

        # Erstelle das neue Nachrichtenobjekt, füge es aber noch nicht hinzu,
        # da der Stream fehlschlagen könnte.
        new_assistant_message = ChatMessage(
            session_id=session.id, role='assistant', content="", author_id=assistant_user.id,
            status='active', llm_model_source=chosen_model,
            sort_order=new_assistant_sort_order
        )

        # Füge es zur Session hinzu und mache einen flush, um eine ID zu bekommen.
        # Ein flush schreibt in die DB, beendet aber die Transaktion NICHT.
        db.session.add(new_assistant_message)
        db.session.flush()

        yield f"event: assistant_message_start\ndata: {json.dumps(new_assistant_message.to_dict())}\n\n"

        # --- Schritt 3: Kontext holen und Stream ausführen ---

        messages_for_context = db.session.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.sort_order <= user_message_to_retry.sort_order,
            ChatMessage.status == 'active'
        ).order_by(ChatMessage.sort_order.asc()).all()

        original_node_ids = [v.node_id for v in user_message_to_retry.context_versions]
        chat_history_for_llm = [{"role": msg.role, "content": msg.content} for msg in messages_for_context]
        system_prompt, _ = _prepare_llm_context(session, original_node_ids, user_id)

        llm_stream = llm_service.generate_response_stream(
            messages=chat_history_for_llm, system_prompt=system_prompt, model=chosen_model
        )

        for chunk in llm_stream:
            if chunk:
                full_response += chunk
                payload = {"id": str(new_assistant_message.id), "token": chunk}
                yield f"data: {json.dumps(payload)}\n\n"

        # --- Schritt 4: Finale Operationen und der einzige Commit ---

        new_assistant_message.content = full_response.strip()
        db.session.commit()  # Alle Änderungen werden jetzt atomar geschrieben!

        yield f"event: assistant_message_end\ndata: {json.dumps(new_assistant_message.to_dict())}\n\n"

    except Exception as e:
        # Bei JEDEM Fehler, rolle die gesamte Transaktion zurück.
        db.session.rollback()
        logger.error(f"STREAM (Retry): Fehler beim Verarbeiten: {e}", exc_info=True)

        # Wenn der Stream fehlschlägt, nachdem die leere Nachricht erstellt wurde,
        # können wir trotzdem versuchen, eine Teil-Antwort zu speichern.
        # Dies ist eine fortgeschrittene Fehlerbehandlung.
        if new_assistant_message and full_response:
            try:
                # Erstelle eine NEUE Session, da die alte zurückgerollt wurde.
                # Dies ist komplex, für den Moment ist ein einfacher Rollback sicherer.
                logger.warning("Stream failed, partial response could not be saved due to transaction rollback.")
            except Exception as final_err:
                logger.error(f"Could not save partial response after initial error: {final_err}")

        yield f"event: error\ndata: {json.dumps({'error': 'A server error occurred during resubmit.'})}\n\n"
        return


# --- Einfache CRUD-Operationen ---
# Diese delegieren meist nur an die DB-Schicht, aber enthalten die Autorisierungslogik.

def list_sessions(vault_id: int, user_id: int) -> list[dict]:
    _verify_vault_access(vault_id, user_id)
    sessions = ChatSession.query.filter_by(vault_id=vault_id, owner_id=user_id).order_by(
        ChatSession.created_at.desc()).all()
    return [s.to_dict() for s in sessions]


def create_new_session(vault_id: int, user_id: int) -> ChatSession:
    _verify_vault_access(vault_id, user_id)
    session = ChatSession(vault_id=vault_id, owner_id=user_id, title="New Chat")
    db.session.add(session)
    db.session.commit()
    return session

def delete_session(session_id: str, user_id: int) -> None:
    """
    Löscht eine komplette Chat-Session und alle zugehörigen Nachrichten.
    Wirft eine Exception bei Fehlern (z.B. nicht gefunden, keine Berechtigung).
    """
    # Die Berechtigungsprüfung ist in _verify_session_access enthalten.
    # Sie wirft einen Fehler, wenn die Session nicht existiert oder der User keinen Zugriff hat.
    session_to_delete = _verify_session_access(session_id, user_id)

    try:
        # Durch die 'cascade="all, delete-orphan"' Beziehung im ChatSession-Modell
        # werden alle zugehörigen ChatMessage-Einträge automatisch mitgelöscht.
        db.session.delete(session_to_delete)
        db.session.commit()
        logger.info(f"User {user_id} successfully deleted chat session {session_id}.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error while deleting session {session_id} for user {user_id}: {e}")
        # Wirf einen allgemeinen Fehler, um interne Details zu verbergen.
        raise RuntimeError("Could not delete the session due to a server error.")


def get_session_history(session_id: str, user_id: int) -> dict:
    session = _verify_session_access(session_id, user_id)

    # *** GEÄNDERT: Sortierung nach sort_order ***
    messages = session.messages.order_by(ChatMessage.sort_order.asc()).all()

    # Der Filter für 'active' etc. sollte jetzt im Frontend stattfinden,
    # damit das Frontend alle Status-Updates korrekt verarbeiten kann.
    message_dicts = [m.to_dict() for m in messages]

    return {
        "id": session.id,
        "title": session.title,
        "vault_id": session.vault_id,
        "created_at": session.created_at.isoformat(),
        "messages": message_dicts
    }


def soft_delete_message(session_id: str, message_id: str, user_id: int):
    """
    Setzt eine Nachricht auf den Status 'deleted'.
    Die `sort_order` anderer Nachrichten wird NICHT geändert.
    """
    session = _verify_session_access(session_id, user_id)

    try:
        # Finde die Nachricht, die gelöscht werden soll.
        message_to_delete = db.session.query(ChatMessage).filter_by(
            id=message_id,
            session_id=session_id
        ).one_or_none()

        if not message_to_delete:
            # Sende keinen Fehler, wenn die Nachricht bereits weg ist.
            # Das macht das Frontend robuster.
            logger.warning(f"Attempted to delete message {message_id}, but it was not found.")
            return

        # Optional: Berechtigungsprüfung, ob der User diese Nachricht löschen darf.
        if message_to_delete.author_id != user_id and session.owner_id != user_id:
            raise PermissionError("You are not authorized to delete this message.")

        # Ändere nur den Status. Das ist alles.
        message_to_delete.status = 'deleted'

        db.session.commit()
        logger.info(f"User {user_id} soft-deleted message {message_id}.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during soft-delete of message {message_id}: {e}", exc_info=True)
        # Wirf den Fehler weiter, damit die API-Schicht einen 500er zurückgeben kann.
        raise


# ==============================================================================
# ADVANCED FEATURES (e.g., Node Update Proposals)
# ==============================================================================

def propose_node_update_from_chat(
        target_node_id: str,
        session_id: str,
        context_node_ids: list,
        model: str,
        user_id: int
) -> dict:
    """
    Generiert einen Update-Vorschlag für einen Node basierend auf einem Chat-Verlauf.

    Diese Funktion orchestriert den Prozess:
    1. Holt die relevanten Daten (Ziel-Node, Kontext-Nodes, Chat-Verlauf).
    2. Konstruiert einen detaillierten Prompt für das LLM.
    3. Ruft den LLM-Service auf, um eine strukturierte Antwort zu erhalten.
    4. Gibt den Original- und den vorgeschlagenen Inhalt zurück.

    Args:
        target_node_id: Die UUID des zu aktualisierenden Nodes.
        session_id: Die UUID der Chat-Session, die als Referenz dient.
        context_node_ids: Eine Liste von Node-UUIDs für zusätzlichen Kontext.
        model: Das zu verwendende LLM-Modell.
        user_id: Die ID des anfragenden Benutzers zur Autorisierung.

    Returns:
        Ein Dictionary mit {"original_content": "...", "proposed_content": "..."}.

    Raises:
        ValueError: Wenn ein Node oder eine Session nicht gefunden wird.
        PermissionError: Wenn der Benutzer keinen Zugriff hat.
    """
    logger.info(f"User {user_id} started node update proposal for node {target_node_id} from session {session_id}.")

    # --- Schritt 1: Daten sammeln und Berechtigungen prüfen ---
    # `_verify_session_access` prüft auch den Vault-Zugriff, was für die Nodes ausreicht.
    session = _verify_session_access(session_id, user_id)
    vault_id = session.vault_id

    # Hole Ziel-Node-Daten. node_service prüft den Zugriff.
    target_node_data = node_service.get_node_by_id(target_node_id, vault_id, user_id)
    if not target_node_data:
        raise ValueError(f"Target node {target_node_id} not found or access denied.")
    original_content = target_node_data['content']
    target_title = target_node_data['title']

    # Hole das gesamte Session-Objekt, das den Verlauf enthält
    chat_session_data = get_session_history(session_id, user_id)

    # Greife auf die 'messages'-Liste innerhalb des Objekts zu
    messages_list = chat_session_data.get('messages', [])  # .get() ist sicherer als direkter Zugriff

    # Formatiere den Verlauf für den Prompt
    # `msg` ist jetzt garantiert ein Dictionary
    chat_history_text = "\n".join(
        [f"{msg.get('role', 'unknown').title()}: {msg.get('content', '')}" for msg in messages_list])

    # Hole zusätzlichen Kontext aus anderen Nodes
    context_data = node_service.get_content_for_nodes(context_node_ids, vault_id, user_id)
    context_content = context_data.get('content', '')
    context_titles = context_data.get('titles', [])

    # --- Schritt 2: Prompt Engineering ---
    # Der Prompt bleibt robust und detailliert, da er die Kernanweisung für das LLM ist.
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
{chat_history_text}
---
**Additional Context from Nodes: {', '.join(context_titles)}**
---
{context_content}
---
Now, please analyze all the information, follow all rules (especially the language rule), and provide the updated content for the node '{target_title}' in the required JSON format. Use your own knowledge."""

    # --- Schritt 3: LLM-Service aufrufen ---
    # Die ganze Komplexität der LLM-Kommunikation ist jetzt im llm_service gekapselt.
    try:
        logger.info(f"Calling llm_service.generate_structured_response with model {model}.")
        proposed_content = llm_service.generate_structured_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )

        # Rückgabe des Ergebnisses
        return {
            "original_content": original_content,
            "proposed_content": proposed_content
        }
    except Exception as e:
        logger.error(f"Error calling LLM service for node update proposal: {e}", exc_info=True)
        # Gib den Fehler weiter, damit die API-Schicht ihn fangen kann.
        raise

def update_session_title(session_id: str, user_id: int, new_title: str) -> ChatSession:
    """Aktualisiert den Titel einer Session und prüft den Besitz."""
    session = _verify_session_access(session_id, user_id)
    session.title = new_title
    db.session.commit()
    logger.info(f"User {user_id} updated title for session {session_id} to '{new_title}'.")
    return session