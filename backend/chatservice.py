# chat_service.py

import logging

import database
import llm
from models import db, ChatSession, ChatMessage, Node


# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

def list_sessions(vault_id: int) -> list[dict]:
    """
    Retrieves a list of all chat sessions for a specific vault.
    """
    sessions = (
        ChatSession.query
        .filter_by(vault_id=vault_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "llm_model": session.llm_model,
            "vault_id": session.vault_id
        } for session in sessions
    ]


def get_session_history(session_id: str) -> dict | None:
    """
    Retrieves the complete history of a single chat session.
    The session_id is globally unique, so no vault_id filter is needed here.
    """
    session = ChatSession.query.get(session_id)
    if not session:
        return None

    messages = [
        {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
        for msg in session.messages
    ]
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "llm_model": session.llm_model,
        "vault_id": session.vault_id,
        "messages": messages
    }


# ==============================================================================
# CORE CHAT LOGIC
# ==============================================================================

def create_new_chat_session(user_input: str, node_ids: list, model: str, vault_id: int) -> dict:
    """
    Creates a new chat session within a specific vault.
    """
    try:
        # Create a concise title from the user's first message.
        title = (user_input[:77] + '...') if len(user_input) > 80 else user_input

        new_session = ChatSession(llm_model=model, title=title, vault_id=vault_id)
        db.session.add(new_session)
        db.session.flush()  # Flush to get the new_session.id

        # Delegate to the core processing function to get the first response.
        assistant_response = _process_message_and_get_response(
            session_id=new_session.id,
            user_input=user_input,
            node_ids=node_ids,
            vault_id=vault_id
        )

        db.session.commit()

        return {
            "session_id": new_session.id,
            "content": assistant_response["content"],
            "role": "assistant"
        }
    except Exception as e:
        logging.error(f"Error creating new chat session: {e}")
        db.session.rollback()
        raise  # Re-raise the exception to be handled by the API layer.


def add_message_to_session(session_id: str, user_input: str, node_ids: list) -> dict:
    """
    Adds a new message from a user to an existing chat session.
    """
    try:
        session = ChatSession.query.get(session_id)
        if not session:
            raise ValueError(f"Session with id {session_id} not found.")

        # The vault_id is determined by the session itself, ensuring context integrity.
        vault_id_from_session = session.vault_id

        assistant_response = _process_message_and_get_response(
            session_id=session_id,
            user_input=user_input,
            node_ids=node_ids,
            vault_id=vault_id_from_session
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


def _process_message_and_get_response(session_id: str, user_input: str, node_ids: list, vault_id: int) -> dict:
    """
    Private core logic: gets context, calls LLM, and stores messages.
    This function is now the single point of contact with the LLM for chat responses.
    """
    session = ChatSession.query.get(session_id)
    chat_history = [{'role': msg.role, 'content': msg.content} for msg in session.messages]

    # --- CONTEXT FETCHING (CLEANED UP) ---
    context_content = ""
    context_versions = []
    if node_ids:
        # Use the single, reliable function from the database layer.
        context_data = database.get_content_for_nodes(node_ids, vault_id=vault_id)
        context_content = context_data.get('content', '')

        # Also get the node objects to link their versions to the chat message.
        nodes_for_version_linking = Node.query.filter(Node.id.in_(node_ids), Node.vault_id == vault_id).all()
        context_versions = [node.current_version_object for node in nodes_for_version_linking if
                            node.current_version_object]

    # --- MESSAGE STORING ---
    user_message = ChatMessage(
        session_id=session.id,
        role='user',
        content=user_input,
        context_versions=context_versions  # Link the context used for this message
    )
    db.session.add(user_message)

    # --- LLM CALL ---
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

    assistant_message = ChatMessage(
        session_id=session.id,
        role='assistant',
        content=assistant_response_text
    )
    db.session.add(assistant_message)

    return {"content": assistant_response_text}


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
            Now, please analyze all the information, follow all rules (especially the language rule), and provide the updated content for the node '{target_title}' in the required JSON format.
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