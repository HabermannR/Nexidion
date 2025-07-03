# chat_service.py
import logging
from models import db, ChatSession, ChatMessage, Version, Node
import llm
import database  # Wir nutzen die bestehenden DB-Funktionen, wo es geht


def list_sessions():
    """
    Holt eine Liste aller Chat-Sitzungen, sortiert nach Erstellungsdatum.
    """
    sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "llm_model": session.llm_model
        } for session in sessions
    ]


def get_session_history(session_id: str):
    """
    Holt den kompletten Verlauf und die Metadaten einer einzelnen Chat-Sitzung.
    Gibt None zurück, wenn die Sitzung nicht existiert.
    """
    session = ChatSession.query.get(session_id)
    if not session:
        return None

    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat()
        } for msg in session.messages
    ]
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "llm_model": session.llm_model,
        "messages": messages
    }


def create_new_chat_session(user_input: str, node_ids: list, model: str):
    """
    Erstellt eine neue Chat-Sitzung UND verarbeitet die erste Nachricht.
    """
    try:
        # 1. Neue Chat-Session in der DB erstellen
        title = user_input[:80] + '...' if len(user_input) > 80 else user_input
        new_session = ChatSession(llm_model=model, title=title)
        db.session.add(new_session)
        db.session.flush()  # Wichtig, damit wir die ID für die Nachricht bekommen

        # 2. Die erste Nachricht mit der Kernlogik verarbeiten
        assistant_response = _process_message_and_get_response(
            session_id=new_session.id,
            user_input=user_input,
            node_ids=node_ids
        )

        # 3. Alles auf einmal in die Datenbank schreiben
        db.session.commit()

        # 4. Antwort für das Frontend zurückgeben
        return {
            "session_id": new_session.id,
            "content": assistant_response["content"],
            "role": "assistant"
        }
    except Exception as e:
        logging.error(f"Error creating new chat session: {e}")
        db.session.rollback()
        raise  # Fehler weitergeben, damit die API-Schicht ihn behandeln kann


def add_message_to_session(session_id: str, user_input: str, node_ids: list):
    """
    Fügt eine Nachricht zu einer bestehenden Sitzung hinzu und gibt die Antwort des Assistenten zurück.
    """
    try:
        # Session validieren (get_or_404 ist in der API-Schicht besser aufgehoben)
        if not ChatSession.query.get(session_id):
            raise ValueError(f"Session with id {session_id} not found.")

        assistant_response = _process_message_and_get_response(
            session_id=session_id,
            user_input=user_input,
            node_ids=node_ids
        )

        db.session.commit()

        return {
            "session_id": session_id,
            "content": assistant_response["content"],
            "role": "assistant"
        }
    except Exception as e:
        logging.error(f"Error adding message to session {session_id}: {e}")
        db.session.rollback()
        raise


def _process_message_and_get_response(session_id: str, user_input: str, node_ids: list):
    """
    Private Kernlogik: Speichert die User-Nachricht, ruft das LLM auf, speichert die Antwort.
    WICHTIG: Diese Funktion macht keinen db.session.commit()! Das wird von den öffentlichen Funktionen gesteuert.
    """
    session = ChatSession.query.get(session_id)

    # 1. Verlauf und Kontext aus der DB holen
    chat_history = [{'role': msg.role, 'content': msg.content} for msg in session.messages]

    # Diese Logik bleibt korrekt für die Erstellung des Text-Kontextes für das LLM
    context_data = database.get_context_from_ids(node_ids, with_titles=False)
    context_content = context_data

    # 2. User-Nachricht in der DB speichern und mit dem KORREKTEN Kontext verknüpfen

    # KORRIGIERTE LOGIK: Hole nur die aktuellen Versionen der ausgewählten Nodes
    # ========================================================================
    context_versions = []
    if node_ids:
        # Hole die Node-Objekte selbst
        selected_nodes = Node.query.filter(Node.id.in_(node_ids)).all()
        # Greife auf die Beziehung zur aktuellen Version zu
        # Dies ist effizient, da SQLAlchemy die Beziehungen intelligent lädt.
        context_versions = [node.current_version_object for node in selected_nodes if node.current_version_object]
    # ========================================================================

    user_message = ChatMessage(
        session_id=session.id,
        role='user',
        content=user_input,
        context_versions=context_versions  # Jetzt wird die korrekte Liste von Version-Objekten übergeben
    )
    db.session.add(user_message)

    # 3. LLM-Anfrage vorbereiten und senden (bleibt unverändert)
    system_prompt = (
        "You are a helpful assistant for a knowledge base. "
        "Use the following context to answer the user's question. "
        "If the context is empty, use your general knowledge.\n\n"
        f"<context>\n{context_content}\n</context>"
    )
    messages_for_llm = chat_history + [{"role": "user", "content": user_input}]

    assistant_response_text = llm.generate_response(
        messages=messages_for_llm,
        system_prompt=system_prompt,
        model=session.llm_model
    )

    # 4. Assistant-Antwort in der DB speichern (bleibt unverändert)
    assistant_message = ChatMessage(
        session_id=session.id,
        role='assistant',
        content=assistant_response_text
    )
    db.session.add(assistant_message)

    # 5. Antwort-Daten zurückgeben (bleibt unverändert)
    return {"content": assistant_response_text}


# In chatservice.py

# ... (Ihre bestehenden Funktionen list_sessions, get_session_history, etc.) ...


# ===================================================================
# NEUE FUNKTION: Service-Logik für den Update-Vorschlag
# ===================================================================
def propose_node_update_from_chat(target_node_id: int, chat_history: str, context_node_ids: list, model: str):
    """
    Generiert einen Vorschlag zur Aktualisierung eines Nodes basierend auf einem Chat.
    """
    try:
        # 1. Hole den originalen Inhalt des Ziel-Nodes
        target_node_data = database.get_node_by_id(target_node_id)

        # 2. Prüfe, ob der Node überhaupt gefunden wurde
        #    get_node_by_id gibt None zurück, wenn der Node nicht existiert.
        if target_node_data is None:
            raise ValueError(f"Target node with ID {target_node_id} not found.")

        # 3. Hole Titel und Inhalt aus dem Dictionary (mit den korrekten, kleingeschriebenen Schlüsseln)
        target_title = target_node_data['title']
        original_content = target_node_data['content']

        # 2. Hole den Inhalt der Kontext-Nodes
        # get_context_from_ids gibt ein dict zurück, wir brauchen nur den 'context'-String
        context_data = database.get_context_from_ids(context_node_ids, with_titles=True)
        context_content = context_data.get('context', '')
        context_titles = context_data.get('titles', [])



        #print("Chat:", chat_history)
        #print("context_content:", context_content)

        # 3. Der System-Prompt, der Claude anweist, ein JSON zu erstellen
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

        # 4. Der User-Prompt kann auf Englisch bleiben, da die Daten klar getrennt sind.
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

                Now, please analyze all the information, follow all rules (especially the language rule), and provide the updated content for node {target_title} in the required JSON format.
                """

        #print("system_prompt:", system_prompt)
        #print("user_prompt:", user_prompt)
        # 5. Rufe die neue LLM-Funktion auf
        proposed_content = llm.generate_structured_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model
        )
        #proposed_content = "Hallo"
        #print("original_content:", original_content)
        #print("proposed_content:", proposed_content)

        # 6. Gib ein Dictionary mit Original und Vorschlag zurück
        return {
            "original_content": original_content,
            "proposed_content": proposed_content
        }

    except Exception as e:
        logging.error(f"Error in propose_node_update_from_chat: {e}")
        # Gib den Fehler weiter, damit die API-Schicht ihn behandeln kann
        raise