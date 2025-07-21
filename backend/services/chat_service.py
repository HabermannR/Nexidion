# backend/services/chat_service.py

import logging
import json
from flask import current_app

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
    """Sammelt und formatiert den Kontext und die Historie für den LLM-Aufruf."""

    # ===== KORREKTUR HIER =====
    # Behandeln Sie den Fall, dass keine Node-IDs übergeben werden, um einen Fehler zu vermeiden.
    context_content = ""
    if node_ids:
        # Holen des Kontexts nur, wenn IDs vorhanden sind.
        context_data = node_service.get_content_for_nodes(node_ids, session.vault_id, user_id)
        context_content = context_data.get('content', '')

    # 2. Erstellen des System-Prompts
    system_prompt = (
        "You are a helpful assistant for a knowledge base. "
        "Use the following context to answer the user's question. "
        "If the context is empty, use your general knowledge.\n\n"
        f"<context>\n{context_content}\n</context>"
    )

    # 3. Holen der "aktiven" Chathistorie
    active_messages = session.messages.filter_by(status='active').order_by(ChatMessage.timestamp.asc()).all()
    # Wir brauchen die Historie für den LLM, nicht die vollständigen DTOs
    chat_history = [{"role": msg.role, "content": msg.content} for msg in active_messages]

    return system_prompt, chat_history


# --- Kernfunktionen (Streaming-First-Ansatz) ---

def stream_new_message(session_id: str, user_id: int, user_input: str, model: str, node_ids: list):
    """
    Fügt eine User-Nachricht hinzu, streamt die Antwort des Assistenten und speichert alles.
    Dies ist die zentrale Funktion, die fast alles abdeckt.
    """
    session = _verify_session_access(session_id, user_id)

    # --- Schritt 1: User-Nachricht speichern ---
    try:
        context_versions = []
        if node_ids:  # Nur wenn IDs vorhanden sind
            # 1. Rufe die neue, performantere Funktion auf, die Node-Objekte zurückgibt.
            context_nodes = node_service.get_nodes_by_ids_for_user(node_ids, session.vault_id, user_id)

            # 2. Extrahiere die Version-Objekte aus den Nodes.
            #    Dies stellt sicher, dass der Rest des Codes, der `context_versions` erwartet,
            #    weiterhin funktioniert.
            context_versions = [
                node.current_version_object
                for node in context_nodes
                if node.current_version_object is not None
            ]

        user_message = ChatMessage(
            session_id=session.id,
            role='user',
            content=user_input,
            author_id=user_id,
            status='active',
            context_versions=context_versions
        )
        db.session.add(user_message)
        db.session.commit()
        # Sende die gespeicherte Nachricht sofort an den Client
        yield f"event: user_message\ndata: {json.dumps(user_message.to_dict())}\n\n"
    except Exception as e:
        db.session.rollback()
        logger.error(f"STREAM: Fehler beim Speichern der User-Nachricht für User {user_id}: {e}")
        yield f"event: error\ndata: {json.dumps({'error': 'Could not save your message.'})}\n\n"
        return

    # --- Schritt 2: LLM-Antwort vorbereiten und streamen ---
    chosen_model = model or current_app.config.get('DEFAULT_CHAT_MODEL', 'claude-3-haiku-20240307')
    full_response = ""
    assistant_message = None

    try:
        # Erstelle eine leere Assistenten-Nachricht, um eine ID zu bekommen
        assistant_user = llm_service.get_llm_user(chosen_model)
        assistant_message = ChatMessage(
            session_id=session.id, role='assistant', content="", author_id=assistant_user.id,
            status='active', llm_model_source=chosen_model
        )
        db.session.add(assistant_message)
        db.session.commit()
        yield f"event: assistant_message_start\ndata: {json.dumps(assistant_message.to_dict())}\n\n"

        # Bereite Kontext vor und rufe den LLM-Service auf
        # WICHTIG: Die Historie für den LLM sollte nur die relevanten Felder enthalten.
        # Die `to_dict()`-Methode könnte zu viele Infos enthalten.
        system_prompt, all_messages_for_llm = _prepare_llm_context(session, node_ids, user_id)

        # Der LLM benötigt nur die Nachrichten vor der aktuellen Antwort.
        # Da die User-Nachricht bereits in der DB ist, wird sie von _prepare_llm_context mitgelesen.
        llm_stream = llm_service.generate_response_stream(
            messages=all_messages_for_llm, system_prompt=system_prompt, model=chosen_model
        )

        # KORREKTUR: Die Schleife ist jetzt viel einfacher, weil sie nur Text erwartet.
        for chunk in llm_stream:
            # chunk ist jetzt ein einfacher Text-String (z.B. "Hello ")
            if chunk:
                full_response += chunk
                payload = {
                    "id": str(assistant_message.id),
                    "token": chunk
                }
                yield f"data: {json.dumps(payload)}\n\n"


    except Exception as e:

        # KORREKTUR: Wandle die Exception explizit in einen String um, bevor du sie loggst.

        # Das verhindert den 'ellipsis' JSON-Fehler.

        error_str = str(e)

        logger.error(f"STREAM: LLM-Stream für Session {session_id} fehlgeschlagen: {error_str}")

        yield f"event: error\ndata: {json.dumps({'error': 'The AI stream was interrupted.'})}\n\n"
    finally:
        # --- Schritt 3: Finale Assistenten-Nachricht & Titel aktualisieren ---
        if assistant_message and full_response:
            try:
                db.session.refresh(session)
                db.session.refresh(assistant_message)

                is_first_assistant_message = session.messages.filter_by(role='assistant').count() == 1

                assistant_message.content = full_response.strip()
                db.session.flush()

                title_was_updated = False  # Flag, um zu wissen, ob wir das Event senden müssen
                if is_first_assistant_message and session.title == "New Chat":
                    history_for_title = f"User: {user_input}\nAssistant: {full_response.strip()}"
                    new_title = llm_service.generate_chat_title(history_for_title, model=chosen_model)
                    session.title = new_title
                    title_was_updated = True  # Setze das Flag
                    logger.info(f"Generated new title for session {session.id}: {new_title}")

                db.session.commit()

                # ===== KORREKTUR HIER =====
                # Sende das Event für die fertige Nachricht (verwendet das normale to_dict)
                yield f"event: assistant_message_end\ndata: {json.dumps(assistant_message.to_dict())}\n\n"

                # Sende das Session-Update-Event NUR, wenn der Titel auch geändert wurde
                if title_was_updated:
                    session_update_payload = {"id": session.id, "title": session.title}
                    yield f"event: session_updated\ndata: {json.dumps(session_update_payload)}\n\n"

            except Exception as e:
                db.session.rollback()
                # Wichtig: Loggen Sie die Exception mit Traceback für besseres Debugging
                logger.error(f"STREAM: Error on final save of assistant answer {assistant_message.id}: {e}",
                             exc_info=True)


def stream_retry_message(session_id: str, message_id: str, user_id: int, model: str):
    """
    Setzt alte Antworten zurück und generiert eine neue Antwort für eine bestehende User-Nachricht.
    """
    session = _verify_session_access(session_id, user_id)
    user_message_to_retry = session.messages.filter_by(id=message_id, role='user').one_or_none()

    if not user_message_to_retry:
        raise ValueError("Message to retry not found or is not a user message.")

    # --- Schritt 1: Alle nachfolgenden, aktiven Nachrichten auf 'retried' setzen ---
    subsequent_messages = session.messages.filter(
        ChatMessage.timestamp > user_message_to_retry.timestamp,
        ChatMessage.status == 'active'
    ).all()
    for msg in subsequent_messages:
        msg.status = 'retried'
    db.session.commit()

    # --- Schritt 2: Den Stream mit dem aktualisierten Verlauf neu starten ---
    # Wir rufen einfach die Hauptfunktion wieder auf, da sie den korrekten Verlauf liest.
    # Wir geben die ursprüngliche Eingabe und die Kontext-Nodes der "retry"-Nachricht weiter.
    original_input = user_message_to_retry.content
    original_node_ids = [v.node_id for v in user_message_to_retry.context_versions]

    yield from stream_new_message(
        session_id=session_id,
        user_id=user_id,
        user_input=original_input,
        model=model,  # Nutze das neue Modell, falls eines übergeben wurde
        node_ids=original_node_ids
    )


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
    """
    Holt die komplette Session mit Titel und aktiven Nachrichten.
    Gibt ein Dictionary zurück, das vom Frontend direkt verarbeitet werden kann.
    """
    session = _verify_session_access(session_id, user_id)

    # Hole die Nachrichten und konvertiere sie in Dictionaries
    messages = session.messages.filter_by(status='active').order_by(ChatMessage.timestamp.asc()).all()
    message_dicts = [m.to_dict() for m in messages]

    # Baue das finale Objekt zusammen, das das Frontend erwartet
    return {
        "id": session.id,
        "title": session.title,
        "vault_id": session.vault_id,
        "created_at": session.created_at.isoformat(),
        "messages": message_dicts
    }


def soft_delete_message(session_id: str, message_id: str, user_id: int):
    session = _verify_session_access(session_id, user_id)
    message = session.messages.filter_by(id=message_id, status='active').one_or_none()
    if not message:
        raise ValueError(f"Active message with ID {message_id} not found in this session.")
    message.status = 'deleted'
    db.session.commit()


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