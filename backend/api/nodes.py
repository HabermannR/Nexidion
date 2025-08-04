import logging
import hashlib
import json

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

# Importiere die Services
from backend.services import node_service, chat_service

# Der Blueprint enthält die vault_id als dynamischen Teil des Präfixes.
# Alle Routen sind relativ zu diesem Prefix.
nodes_bp = Blueprint('nodes_v2', __name__, url_prefix='/api/vaults/<int:vault_id>/nodes')


# ========================================================================
# HILFSFUNKTIONEN FÜR ETAG-CACHING
# ========================================================================

def generate_etag(data: dict | list) -> str:
    """Generiert einen stabilen MD5-Hash für ein Python-Datenobjekt."""
    encoded_data = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.md5(encoded_data).hexdigest()


def cached_jsonify(data: dict | list) -> 'Response':
    """
    Erstellt eine JSON-Response, setzt den ETag und macht sie konditional.
    Gibt bei einem Cache-Hit automatisch eine 304 Not Modified Antwort zurück.
    """
    response = jsonify(data)
    response.set_etag(generate_etag(data))
    return response.make_conditional(request)


# ========================================================================
# API-ROUTEN (LESENDE OPERATIONEN)
# ========================================================================

@nodes_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_nodes(vault_id: int):
    """
    Holt Nodes eines Vaults. Unterstützt Baum-Format (mit Caching),
    Listen-Format und Titelsuche (ohne Caching).
    """
    user_id = int(get_jwt_identity())
    format_type = request.args.get('format', 'tree').lower()

    try:
        if 'title' in request.args:
            search_title = request.args.get('title')
            node = node_service.find_node_by_title(search_title, vault_id, user_id)
            return jsonify([node] if node else [])

        if format_type == 'list':
            nodes = node_service.get_nodes_as_list(vault_id, user_id)
            return jsonify(nodes)

        # Baum-Struktur (Standardfall)
        tree_data = node_service.get_nodes_as_tree(vault_id, user_id)
        return cached_jsonify(tree_data)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": f"An internal error occurred: {e}"}), 500


@nodes_bp.route('/bulk-get', methods=['POST'], strict_slashes=False)
@jwt_required()
def get_multiple_nodes(vault_id: int):
    """
    Holt die Details für eine Liste von Node-IDs auf einmal.
    """
    user_id = int(get_jwt_identity())
    data = request.json
    node_ids = data.get('node_ids')

    if node_ids is None or not isinstance(node_ids, list):
        return jsonify({"error": "A list of 'node_ids' is required in the request body."}), 400
    if not all(isinstance(nid, str) for nid in node_ids):
        return jsonify({"error": "All items in 'node_ids' must be strings."}), 400
    if not node_ids:
        return jsonify([])

    try:
        nodes = node_service.get_nodes_by_ids_for_user(node_ids, vault_id, user_id)
        response_data = []
        for node in nodes:
            version = node.current_version_object
            if version:
                response_data.append({
                    'id': version.id,
                    'node_id': version.node_id,
                    'version': version.version,
                    'content': version.content,
                    'timestamp': version.timestamp.isoformat(),
                    'author_id': version.author_id,
                    'author_name': version.author.display_name if version.author else "Unknown",
                    'title': node.title
                })
        return jsonify(response_data)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@nodes_bp.route('/<string:node_id>', methods=['GET'])
@jwt_required()
def get_single_node(vault_id: int, node_id: str):
    """
    Holt die Details eines einzelnen Nodes (ohne kompletten Versionsverlauf).
    Diese Antwort wird mittels ETag gecacht.
    """
    user_id = int(get_jwt_identity())
    try:
        node = node_service.get_node_by_id(node_id, vault_id, user_id)
        if node is None:
            return jsonify({"error": "Node not found"}), 404
        return cached_jsonify(node)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>/versions', methods=['GET'])
@jwt_required()
def get_node_versions_route(vault_id: int, node_id: str):
    """
    Holt den kompletten Versionsverlauf für einen Node.
    Diese Antwort wird mittels ETag gecacht.
    """
    user_id = int(get_jwt_identity())
    try:
        versions = node_service.get_node_versions(node_id, vault_id, user_id)
        if versions is None:
            return jsonify({"error": "Node not found"}), 404
        return cached_jsonify(versions)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


# ========================================================================
# API-ROUTEN (SCHREIBENDE OPERATIONEN)
# ========================================================================

@nodes_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_node(vault_id: int):
    """Erstellt einen neuen Node im angegebenen Vault."""
    user_id = int(get_jwt_identity())
    data = request.json
    title = data.get('title')
    if not title or not title.strip():
        return jsonify({"error": "title is required and cannot be empty"}), 400

    try:
        # +++ GEÄNDERT +++
        # Ruft die neue Service-Funktion auf, die jetzt ein Dictionary zurückgibt.
        new_node_dict = node_service.create_node(
            title=title.strip(),
            content=data.get('content', ''),
            parent_id=data.get('parent_id'),
            vault_id=vault_id,
            author_id=user_id
        )
        # Wir geben das zurückgegebene Dictionary direkt weiter.
        return jsonify(new_node_dict), 201

    except (PermissionError, ValueError) as e:
        return jsonify({"error": str(e)}), 403 if isinstance(e, PermissionError) else 400
    except Exception as e:
        logging.error(f"Error creating node in vault {vault_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


@nodes_bp.route('/<string:node_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_node(vault_id: int, node_id: str):
    """
    Aktualisiert einen Node (Titel und/oder Inhalt) und erstellt IMMER eine neue Version.
    """
    user_id = int(get_jwt_identity())
    data = request.json

    if 'title' not in data and 'content' not in data:
        return jsonify({"error": "Request body must contain 'title' or 'content' for an update."}), 400

    try:
        # +++ GEÄNDERT +++
        # Ruft die neue Service-Funktion auf, die ein Dictionary zurückgibt.
        updated_node_dict = node_service.update_node(
            node_id=node_id,
            vault_id=vault_id,
            user_id=user_id,
            title=data.get('title'),
            content=data.get('content')
        )
        # Wir geben das zurückgegebene Dictionary direkt weiter.
        return jsonify(updated_node_dict)

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>/move', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def move_node_route(vault_id: int, node_id: str):
    """Verschiebt einen Node zu einem neuen Parent."""
    user_id = int(get_jwt_identity())
    data = request.json

    if 'parent_id' not in data:
        return jsonify({"error": "Request body must contain 'parent_id' (can be null)."}), 400

    try:
        # +++ GEÄNDERT +++
        # Die Service-Funktion gibt jetzt ein Node-Objekt zurück. Wir müssen es konvertieren.
        updated_node = node_service.move_node(node_id, data['parent_id'], vault_id, user_id)
        return jsonify(updated_node.to_dict())

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>/icon', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def set_node_icon_route(vault_id: int, node_id: str):
    """Ändert das Icon eines Nodes."""
    user_id = int(get_jwt_identity())
    data = request.json

    if 'icon' not in data:
        return jsonify({"error": "Request body must contain 'icon' (can be a string or null)."}), 400
    try:
        # +++ GEÄNDERT +++
        # Die Service-Funktion gibt jetzt ein Node-Objekt zurück. Wir müssen es konvertieren.
        updated_node = node_service.update_node_icon(node_id, vault_id, user_id, data['icon'])
        return jsonify(updated_node.to_dict())

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_node(vault_id: int, node_id: str):
    """Löscht einen Node."""
    user_id = int(get_jwt_identity())
    try:
        node_service.delete_node(node_id, vault_id, user_id)
        return jsonify({"message": "Node deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


# ========================================================================
# API-ROUTEN (SPEZIAL-ENDPUNKTE)
# ========================================================================

@nodes_bp.route('/content', methods=['POST'], strict_slashes=False)
@jwt_required()
def post_nodes_content(vault_id: int):
    """Holt den zusammengefassten Inhalt für eine Liste von Node-IDs."""
    user_id = int(get_jwt_identity())
    data = request.json
    if not data or 'node_ids' not in data:
        return jsonify({"error": "Request body must contain 'node_ids'."}), 400

    node_ids = data['node_ids']
    if not isinstance(node_ids, list):
        return jsonify({"error": "'node_ids' must be a list."}), 400

    try:
        result = node_service.get_content_for_nodes(node_ids, vault_id, user_id)
        return jsonify(result)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@nodes_bp.route('/<string:node_id>/propose-update', methods=['POST'], strict_slashes=False)
@jwt_required()
def propose_node_update(vault_id: int, node_id: str):
    """
    Generiert einen Update-Vorschlag für einen Node basierend auf einem Chat-Verlauf.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json()

    session_id = data.get('session_id')
    model = data.get('model')
    if not session_id or not model:
        return jsonify({"error": "A 'session_id' and 'model' are required in the request body."}), 400

    try:
        proposal = chat_service.propose_node_update_from_chat(
            target_node_id=node_id,
            session_id=session_id,
            context_node_ids=data.get('context_node_ids', []),
            model=model,
            user_id=user_id
        )
        return jsonify(proposal)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error in propose_node_update for node {node_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred while generating the proposal."}), 500