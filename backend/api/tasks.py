# backend/api/tasks.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.extensions import limiter
from backend.services import task_service

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


@tasks_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
def list_tasks():
    """
    Gibt eine Liste von Tasks für einen Vault zurück.

    Query Parameters:
        vault_id (int, required): ID des Vaults.
        status   (str, optional): Filtert nach Status ('pending', 'processing', 'completed', 'failed').
        limit    (int, optional): Maximale Anzahl zurückgegebener Tasks (neueste zuerst).

    Example:
        GET /api/tasks?vault_id=1
        GET /api/tasks?vault_id=1&status=pending
        GET /api/tasks?vault_id=1&status=completed&limit=5
    """
    user_id = int(get_jwt_identity())

    # --- Query-Parameter auslesen ---
    vault_id_str = request.args.get('vault_id')
    status       = request.args.get('status')       # optional
    limit_str    = request.args.get('limit')         # optional

    if not vault_id_str:
        return jsonify({'error': 'vault_id query parameter is required'}), 400

    try:
        vault_id = int(vault_id_str)
    except ValueError:
        return jsonify({'error': 'vault_id must be an integer'}), 400

    # Set default limit to 20 if not provided
    limit_str = request.args.get('limit')
    limit = 20
    if limit_str is not None:
        try:
            limit = int(limit_str)
            if limit < 1:
                raise ValueError()
        except ValueError:
            return jsonify({'error': 'limit must be a positive integer'}), 400

    try:
        tasks = task_service.get_tasks(
            vault_id=vault_id,
            user_id=user_id,
            status=status,
            limit=limit,
        )
        # Use short=True for the List API
        return jsonify([t.to_dict(short=True) for t in tasks])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403


@tasks_bp.route('/<string:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """
    Gibt einen einzelnen Task anhand seiner ID zurück.

    Example:
        GET /api/tasks/550e8400-e29b-41d4-a716-446655440000
    """
    user_id = int(get_jwt_identity())

    try:
        task = task_service.get_task_by_id(task_id=task_id, user_id=user_id)
        return jsonify(task.to_dict())
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403


@tasks_bp.route('', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("10 per minute; 50 per hour")
def create_task():
    """
    Erstellt einen neuen Task.

    Body (JSON):
        vault_id         (int,  required): ID des Ziel-Vaults.
        instruction      (str,  required): Die Aufgabenbeschreibung.
        context_node_ids (list, optional): Liste von Node-IDs als Kontext.

    Example:
        POST /api/tasks
        { "vault_id": 1, "instruction": "Summarize all nodes", "context_node_ids": ["abc", "def"] }
    """
    user_id = int(get_jwt_identity())
    data = request.get_json()

    vault_id         = data.get('vault_id')
    instruction      = data.get('instruction', '')
    context_node_ids = data.get('context_node_ids', [])

    if not vault_id:
        return jsonify({'error': 'vault_id is required'}), 400

    try:
        task = task_service.create_task(
            vault_id=vault_id,
            instruction=instruction,
            context_node_ids=context_node_ids,
            user_id=user_id,
        )
        return jsonify(task.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
