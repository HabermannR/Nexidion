import logging
import hashlib
import json

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from backend.extensions import limiter
# Import the services and the new exceptions +++
from backend.services import node_service
from backend.exceptions import InsufficientVaultRoleError

# The blueprint contains the vault_id as a dynamic part of the prefix.
# All routes are relative to this prefix.
nodes_bp = Blueprint('nodes_v2', __name__, url_prefix='/api/vaults/<int:vault_id>/nodes')


def _actor_type() -> str | None:
    return get_jwt().get('actor_type')


def _include_quarantined() -> bool:
    return request.args.get('include_quarantined', 'false').lower() == 'true'


# ========================================================================
# HELPER FUNCTIONS FOR ETAG CACHING
# ========================================================================

def generate_etag(data: dict | list) -> str:
    """Generates a stable MD5 hash for a Python data object."""
    encoded_data = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.md5(encoded_data).hexdigest()


def cached_jsonify(data: dict | list) -> 'Response':
    """
    Creates a JSON response, sets the ETag, and makes it conditional.
    Automatically returns a 304 Not Modified response on a cache hit.
    """
    response = jsonify(data)
    response.set_etag(generate_etag(data))
    return response.make_conditional(request)


# ========================================================================
# API ROUTES (READ OPERATIONS)
# ========================================================================

@nodes_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_nodes(vault_id: int):
    """
    Fetches nodes of a vault. Supports tree format (UI/Agent),
    list format, and title search.
    """
    user_id = int(get_jwt_identity())
    format_type = request.args.get('format', 'tree').lower()

    try:
        # 1. Title Search
        if 'title' in request.args:
            search_title = request.args.get('title')
            node = node_service.find_node_by_title(
                search_title, vault_id, user_id, actor_type=_actor_type(),
                include_quarantined=_include_quarantined())
            return jsonify([node] if node else [])

        # 2. List Format
        if format_type == 'list':
            nodes = node_service.get_nodes_as_list(
                vault_id, user_id, actor_type=_actor_type(),
                include_quarantined=_include_quarantined())
            return jsonify(nodes)

        # 3. TREE OR AGENT TREE (Via Service Layer)
        if format_type in ['tree', 'agent_tree']:
            client_etag = request.headers.get('If-None-Match')

            # Ask the service for the tree!
            tree_data, etag, is_not_modified = node_service.get_nodes_as_tree(
                vault_id, user_id, format_type, client_etag,
                actor_type=_actor_type(), include_quarantined=_include_quarantined()
            )

            if is_not_modified:
                return Response(status=304)

            response = jsonify(tree_data)
            if etag:
                response.set_etag(etag)

            return response

        return jsonify({"error": "Invalid format requested."}), 400

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error fetching tree: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500


@nodes_bp.route('/search', methods=['GET'], strict_slashes=False)
@jwt_required()
def search_nodes_by_title(vault_id: int):
    """
    Searches for nodes based on a title fragment for an autocomplete UI.
    Returns a lean list of up to 10 matching nodes.

    Query parameters:
        q (str): The search term to look for in the title.
    """
    user_id = int(get_jwt_identity())
    # Fetch the search term from the query parameters. 'q' is a common convention.
    query = request.args.get('q', '').strip()

    # Optional: Only start a search if the user has typed at least 2 characters.
    # This saves database resources and prevents too many unspecific results.
    if len(query) < 2:
        return jsonify([])

    try:
        # Call the dedicated service function containing the logic.
        nodes = node_service.search_nodes_for_autocomplete(
            query, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=_include_quarantined())
        return jsonify(nodes)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error during node search in vault {vault_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during search"}), 500


@nodes_bp.route('/full-search', methods=['GET'], strict_slashes=False)
@jwt_required()
@limiter.limit("60 per minute")
def full_text_search(vault_id: int):
    """
    Full-text search specifically for LLM agents.
    Searches within title, content, and the AI summary.

    Query parameters:
        q (str): The search term.
        limit (int): Maximum number of results (default: 20).
    """
    user_id = int(get_jwt_identity())
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)

    if not query:
        return jsonify({"error": "Missing search query parameter 'q'."}), 400
    if limit < 1 or limit > 100:
        return jsonify({"error": "Parameter 'limit' must be between 1 and 100."}), 400

    try:
        results = node_service.search_nodes_fulltext(
            query, vault_id, user_id, limit, actor_type=_actor_type(),
            include_quarantined=_include_quarantined())
        return jsonify({
            "query": query,
            "limit": limit,
            "count": len(results),
            "results": results
        }), 200
    except PermissionError:
        return jsonify({"error": "Access to this vault is not permitted."}), 403
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500


@nodes_bp.route('/resolve-links', methods=['POST'], strict_slashes=False)
@jwt_required()
def resolve_internal_links(vault_id: int):
    """
    Takes a list of link targets (UUIDs or titles) and attempts
    to resolve them. Returns the status for each target.
    """
    user_id = int(get_jwt_identity())
    data = request.json
    targets = data.get('targets')

    if not isinstance(targets, list):
        return jsonify({"error": "Request body must contain a list of 'targets'."}), 400

    try:
        results = node_service.resolve_link_targets(
            targets, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=bool(data.get('include_quarantined', False)))
        return jsonify({"results": results})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error resolving links in vault {vault_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


@nodes_bp.route('/bulk-get', methods=['POST'], strict_slashes=False)
@jwt_required()
def get_multiple_nodes(vault_id: int):
    """
    Fetches the details for a list of node IDs all at once.
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
        nodes = node_service.get_nodes_by_ids_for_user(
            node_ids, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=bool(data.get('include_quarantined', False)))
        response_data = []
        for node in nodes:
            version = node.current_version_object
            if version:
                response_data.append(version.to_dict())
        return jsonify(response_data)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@nodes_bp.route('/<string:node_id>', methods=['GET'])
@jwt_required()
def get_single_node(vault_id: int, node_id: str):
    """
    Fetches the details of a single node.
    Optionally accepts a ?version= parameter.
    """
    user_id = int(get_jwt_identity())
    version_param = request.args.get('version')
    target_version = None
    if version_param is not None:
        try:
            target_version = int(version_param)
            if target_version <= 0:
                raise ValueError()
        except ValueError:
            return jsonify({"error": "Invalid version parameter"}), 400

    try:
        node = node_service.get_node_by_id(
            node_id, vault_id, user_id, target_version=target_version,
            actor_type=_actor_type(), include_quarantined=_include_quarantined())
        if node is None:
            return jsonify({"error": "Node not found"}), 404
        return cached_jsonify(node)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@nodes_bp.route('/<string:node_id>/versions', methods=['GET'])
@jwt_required()
def get_node_versions_route(vault_id: int, node_id: str):
    """
    Returns the version history for a node.
    The current version is a full payload; older versions are lightweight stubs.
    """
    user_id = int(get_jwt_identity())
    try:
        versions = node_service.get_node_versions(
            node_id, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=_include_quarantined())
        if versions is None:
            return jsonify({"error": "Node not found"}), 404
        return cached_jsonify(versions)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>/versions/<int:version_id>', methods=['GET'])
@jwt_required()
def get_single_version_route(vault_id: int, node_id: str, version_id: int):
    """
    Lazy-loads the full content of a single historical version.
    Called by the frontend when the user clicks a stub version entry.
    """
    user_id = int(get_jwt_identity())
    try:
        version = node_service.get_version_by_id(
            version_id, node_id, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=_include_quarantined())
        if version is None:
            return jsonify({"error": "Version not found"}), 404
        return cached_jsonify(version)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        logging.error(f"Error fetching version {version_id} for node {node_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


# ========================================================================
# API ROUTES (WRITE OPERATIONS)
# ========================================================================

@nodes_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("60 per minute; 500 per hour")
def create_node(vault_id: int):
    user_id = int(get_jwt_identity())
    data = request.json
    title = data.get('title')
    if not title or not title.strip():
        return jsonify({"error": "title is required and cannot be empty"}), 400

    try:
        new_node = node_service.create_node(
            title=title.strip(),
            content=data.get('content', ''),
            parent_id=data.get('parent_id'),
            vault_id=vault_id,
            author_id=user_id,
            actor_type=_actor_type(),
        )
        return jsonify(new_node.to_dict()), 201

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error creating node in vault {vault_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


@nodes_bp.route('/<string:node_id>/copy', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("30 per minute; 200 per hour")
def copy_node_to_vault(vault_id: int, node_id: str):
    """Copy a node/subtree into another writable vault using fresh UUIDs."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    destination_vault_id = data.get('destination_vault_id')
    if not isinstance(destination_vault_id, int) or isinstance(destination_vault_id, bool):
        return jsonify({"error": "destination_vault_id must be an integer."}), 400
    recursive = data.get('recursive', True)
    if not isinstance(recursive, bool):
        return jsonify({"error": "recursive must be a boolean."}), 400
    destination_parent_id = data.get('destination_parent_id')
    if destination_parent_id is not None and not isinstance(destination_parent_id, str):
        return jsonify({"error": "destination_parent_id must be a string or null."}), 400

    try:
        from backend.services.node_copy_service import copy_node_to_vault as copy_service
        result = copy_service(
            node_id, vault_id, destination_vault_id, user_id,
            recursive=recursive, destination_parent_id=destination_parent_id,
            actor_type=_actor_type(),
        )
        return jsonify(result), 201
    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error("Cross-vault node copy failed", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


@nodes_bp.route('/<string:node_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
@limiter.limit("60 per minute; 500 per hour")
def update_node(vault_id: int, node_id: str):
    """
    Updates a node (title and/or content) and ALWAYS creates a new version.
    """
    user_id = int(get_jwt_identity())
    data = request.json

    if 'title' not in data and 'content' not in data:
        return jsonify({"error": "Request body must contain 'title' or 'content' for an update."}), 400

    try:
        updated_node = node_service.update_node(
            node_id=node_id,
            vault_id=vault_id,
            user_id=user_id,
            title=data.get('title'),
            content=data.get('content'),
            actor_type=_actor_type(),
        )
        return jsonify(updated_node.to_dict())

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@nodes_bp.route('/<string:node_id>/move', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def move_node_route(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    data = request.json

    if 'parent_id' not in data:
        return jsonify({"error": "Request body must contain 'parent_id' (can be null)."}), 400

    try:
        updated_node = node_service.move_node(
            node_id, data['parent_id'], vault_id, user_id, actor_type=_actor_type())
        return jsonify(updated_node.to_dict())

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@nodes_bp.route('/<string:node_id>/icon', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def set_node_icon_route(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    data = request.json

    if 'icon' not in data:
        return jsonify({"error": "Request body must contain 'icon' (can be a string or null)."}), 400
    try:
        updated_node = node_service.update_node_icon(
            node_id, vault_id, user_id, data['icon'], actor_type=_actor_type())
        return jsonify(updated_node.to_dict())

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@nodes_bp.route('/<string:node_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
@limiter.limit("30 per minute; 200 per hour")
def delete_node(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    try:
        node_service.delete_node(node_id, vault_id, user_id, actor_type=_actor_type())
        return jsonify({"message": "Node deleted successfully"}), 200

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@nodes_bp.route('/<string:node_id>/summary', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def update_ai_summary(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    data = request.json

    if 'ai_summary' not in data:
        return jsonify({"error": "Request body must contain 'ai_summary'."}), 400

    try:
        updated_node = node_service.update_node_ai_summary(
            node_id, vault_id, user_id, data['ai_summary'], actor_type=_actor_type())
        return jsonify(updated_node.to_dict())

    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@nodes_bp.route('/<string:node_id>/summary/generate', methods=['POST'], strict_slashes=False)
@jwt_required()
def generate_ai_summary(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    try:
        from backend.models import User
        from backend.services.vault_service import get_vault_access, assert_write_allowed
        _, role = get_vault_access(vault_id, user_id)
        assert_write_allowed(role, db.session.get(User, user_id))
        node_data = node_service.get_node_by_id(node_id, vault_id, user_id)
        if not node_data:
            return jsonify({"error": "Node not found"}), 404
        from backend.models import Node
        from backend.services.summary_service import request_summary
        from backend.services.node_policy_service import assert_readable, assert_writable
        target = db.session.get(Node, node_id)
        assert_readable(target, user_id, actor_type='ai')
        assert_writable(target, user_id, actor_type='ai')
        artifact = request_summary(
            target, data.get('provider', 'local'),
            data.get('model'), user_id, visual_mode=data.get('visual_mode', 'off')
        )
        return jsonify({"id": artifact.id, "status": artifact.status,
                        "provider": artifact.provider, "model": artifact.model}), 202
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@nodes_bp.route('/<string:node_id>/access-policy', methods=['PATCH'], strict_slashes=False)
@jwt_required()
def set_node_access_policy_route(vault_id: int, node_id: str):
    if _actor_type() in {'mcp', 'ai', 'agent'}:
        return jsonify({"error": "AI-mediated requests cannot change node access policy."}), 403
    data = request.get_json(silent=True) or {}
    required = {'ai_read', 'ai_write_locked', 'human_write_locked'}
    if not required.issubset(data):
        return jsonify({"error": "ai_read, ai_write_locked and human_write_locked are required."}), 400
    if not isinstance(data['ai_write_locked'], bool) or not isinstance(data['human_write_locked'], bool):
        return jsonify({"error": "Lock values must be booleans."}), 400
    try:
        node = node_service.update_node_access_policy(
            node_id, vault_id, int(get_jwt_identity()), ai_read=data['ai_read'],
            ai_write_locked=data['ai_write_locked'],
            human_write_locked=data['human_write_locked'], note=data.get('note'),
        )
        payload = node.to_dict()
        from backend.services.node_policy_service import effective_policy
        payload['effective_access_policy'] = effective_policy(node).to_dict()
        return jsonify(payload)
    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@nodes_bp.route('/<string:node_id>/summary/history', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_ai_summary_history(vault_id: int, node_id: str):
    user_id = int(get_jwt_identity())
    try:
        if not node_service.get_node_by_id(
            node_id, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=_include_quarantined()
        ):
            return jsonify({"error": "Node not found"}), 404
        from backend.models import SummaryArtifact
        rows = SummaryArtifact.query.filter_by(node_id=node_id).order_by(SummaryArtifact.created_at.desc()).all()
        return jsonify([{
            "id": row.id, "source_content_hash": row.source_content_hash,
            "summary": row.summary, "provider": row.provider, "model": row.model,
            "prompt_version": row.prompt_version, "visual_mode": row.visual_mode,
            "used_vision": row.used_vision, "status": row.status, "error": row.error,
            "requested_by_id": row.requested_by_id, "executed_by_id": row.executed_by_id,
            "created_at": row.created_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        } for row in rows])
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


# ========================================================================
# API ROUTES (SPECIAL ENDPOINTS)
# ========================================================================

@nodes_bp.route('/content', methods=['POST'], strict_slashes=False)
@jwt_required()
def post_nodes_content(vault_id: int):
    user_id = int(get_jwt_identity())
    data = request.json
    if not data or 'node_ids' not in data:
        return jsonify({"error": "Request body must contain 'node_ids'."}), 400

    node_ids = data['node_ids']
    if not isinstance(node_ids, list):
        return jsonify({"error": "'node_ids' must be a list."}), 400

    try:
        result = node_service.get_content_for_nodes(
            node_ids, vault_id, user_id, actor_type=_actor_type(),
            include_quarantined=bool(data.get('include_quarantined', False)))
        return jsonify(result)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
