# backend/api/chats.py

import json
from flask import Blueprint, request, jsonify, Response, current_app, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.services import chat_service
from backend.services.chat_service import _verify_session_access
from backend.services.chat_service import update_session_title

# Neuer Blueprint mit dem korrekten URL-Präfix
chats_bp = Blueprint('chats', __name__, url_prefix='/api/vaults/<int:vault_id>/sessions')


@chats_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_sessions(vault_id):
    """Listet alle Chat-Sessions in einem Vault auf."""
    user_id = int(get_jwt_identity())
    try:
        sessions = chat_service.list_sessions(vault_id=vault_id, user_id=user_id)
        return jsonify(sessions), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@chats_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_session(vault_id):
    """Startet eine neue, leere Chat-Session."""
    user_id = int(get_jwt_identity())
    try:
        session = chat_service.create_new_session(vault_id=vault_id, user_id=user_id)
        return jsonify(session.to_dict()), 201
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@chats_bp.route('/<string:session_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_history(vault_id, session_id):
    """Holt den Nachrichtenverlauf einer Session."""
    user_id = int(get_jwt_identity())
    try:
        history = chat_service.get_session_history(session_id=session_id, user_id=user_id)
        return jsonify(history), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@chats_bp.route('/<string:session_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_session_route(vault_id, session_id):
    """Löscht eine komplette Chat-Session."""
    user_id = int(get_jwt_identity())
    try:
        chat_service.delete_session(session_id=session_id, user_id=user_id)
        return '', 204  # No Content
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@chats_bp.route('/<string:session_id>/messages', methods=['POST'], strict_slashes=False)
@jwt_required()
def add_message(vault_id, session_id):
    """Fügt eine Nachricht hinzu und streamt die Antwort."""
    user_id = int(get_jwt_identity())
    data = request.json
    user_input = data.get('user_input')

    if not user_input:
        return jsonify({"error": "user_input is required"}), 400

    client_message_id = data.get('client_message_id')
    model = data.get('model')
    node_ids = data.get('node_ids', [])

    # --- NEW: Get the user's chosen title model from the request payload. ---
    # It's optional, so we use .get() which returns None if not found.
    title_model = data.get('titleModel')
    # --- END NEW LOGIC ---

    try:
        # Die Berechtigungsprüfung bleibt gleich.
        _verify_session_access(session_id=session_id, user_id=user_id)

        # Der Generator wird jetzt mit der zusätzlichen client_message_id aufgerufen.
        response_generator = chat_service.stream_new_message(
            session_id=session_id,
            user_id=user_id,
            user_input=user_input,
            model=model,
            node_ids=node_ids,
            client_message_id=client_message_id,
            title_model=title_model
        )

        return Response(stream_with_context(response_generator), mimetype='text/event-stream')

    except (PermissionError, ValueError) as e:
        # Die Fehlerbehandlung bleibt ebenfalls gleich.
        return Response(
            f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n",
            mimetype='text/event-stream',
            status=403 if isinstance(e, PermissionError) else 404
        )

@chats_bp.route('/<string:session_id>/messages/<string:message_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_message(vault_id, session_id, message_id):
    """Löscht eine Nachricht (Soft Delete)."""
    user_id = int(get_jwt_identity())
    try:
        chat_service.soft_delete_message(session_id, message_id, user_id)
        return '', 204
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@chats_bp.route('/<string:session_id>/messages/<string:message_id>/retry', methods=['POST'], strict_slashes=False)
@jwt_required()
def retry_message(vault_id, session_id, message_id):
    """Fordert eine neue Antwort für eine User-Nachricht an."""
    user_id = int(get_jwt_identity())
    data = request.json or {}
    model = data.get('model')

    try:
        # KORREKTUR (dieselbe Logik wie oben)
        response_generator = chat_service.stream_retry_message(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            model=model
        )
        return Response(stream_with_context(response_generator), mimetype='text/event-stream')

    except (PermissionError, ValueError) as e:
        return Response(
            f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n",
            mimetype='text/event-stream',
            status=403 if isinstance(e, PermissionError) else 404
        )


@chats_bp.route('/<string:session_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_session(vault_id, session_id):
    """Aktualisiert die Daten einer Chat-Session (z.B. den Titel)."""
    user_id = int(get_jwt_identity())
    data = request.json
    new_title = data.get('title')

    if not new_title:
        return jsonify({"error": "Title is required"}), 400

    try:
        updated_session = update_session_title(
            session_id=session_id,
            user_id=user_id,
            new_title=new_title
        )
        return jsonify(updated_session.to_dict()), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404