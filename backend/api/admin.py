from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps

from backend.services import user_service, vault_service
from backend.models import db, User, VaultRole

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def admin_required(fn):
    """Ensures the logged-in user has admin privileges. Use after @jwt_required()."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user_id = int(get_jwt_identity())
        user = db.session.get(User, current_user_id)
        if not user:
            return jsonify({"error": "User not found"}), 401
        if not user.is_admin:
            return jsonify({"error": "Admin privileges required"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def list_users():
    """[ADMIN] List all human users."""
    users = user_service.get_all_users()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route('/users/all', methods=['GET'])
@jwt_required()
@admin_required
def list_all_users():
    """[ADMIN] List all users including llm_assistant accounts."""
    users = user_service.get_all_users_including_llm()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route('/users', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    """[ADMIN] Create a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    display_name = data.get('display_name')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    try:
        new_user = user_service.create_user(username, password, display_name, is_admin)
        return jsonify(new_user.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """[ADMIN] Delete a user."""
    acting_user_id = int(get_jwt_identity())
    try:
        user_service.delete_user(user_id_to_delete=user_id, acting_user_id=acting_user_id)
        return jsonify({"message": f"User {user_id} deleted successfully."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@admin_bp.route('/users/<int:user_id>/password', methods=['PUT'])
@jwt_required()
@admin_required
def set_user_password(user_id):
    """[ADMIN] Set or change a user's password."""
    data = request.get_json(silent=True) or {}
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({"error": "Field 'new_password' is required"}), 400

    try:
        user_service.set_user_password(user_id, new_password)
        return jsonify({"message": "Password updated successfully."}), 200
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        return jsonify({"error": str(e)}), status_code


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user_details(user_id):
    """[ADMIN] Update user details (display_name, is_admin, etc.)."""
    updates = request.get_json(silent=True) or {}
    if not updates:
        return jsonify({"error": "Request body cannot be empty."}), 400

    try:
        updated_user = user_service.update_user_details(user_id, updates)
        return jsonify(updated_user.to_dict()), 200
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 409
        return jsonify({"error": str(e)}), status_code
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


# ---------------------------------------------------------------------------
# Vault access management
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Vault access management
# ---------------------------------------------------------------------------

@admin_bp.route('/vaults', methods=['GET'])
@jwt_required()
@admin_required
def list_all_vaults():
    """[ADMIN] List all vaults in the system with owner info and access count."""
    try:
        vaults = vault_service.get_all_vaults()
        return jsonify(vaults), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ADDED '/vaults' TO THE ROUTE BELOW
@admin_bp.route('/vaults/<int:vault_id>/access', methods=['GET'])
@jwt_required()
@admin_required
def get_vault_access(vault_id):
    """Get vault metadata, current access list, and grantable users."""
    try:
        data = vault_service.get_vault_access_list(vault_id)
        return jsonify(data), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

# ADDED '/vaults' TO THE ROUTE BELOW
@admin_bp.route('/vaults/<int:vault_id>/access', methods=['POST'])
@jwt_required()
@admin_required
def grant_vault_access(vault_id):
    """Grant a user or LLM agent access to a vault."""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    raw_role = data.get('role', VaultRole.EDITOR.value)

    if raw_role == 'viewer':
        role = VaultRole.VIEWER.value
    elif raw_role == 'editor':
        role = VaultRole.EDITOR.value
    else:
        role = raw_role

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if role not in (VaultRole.VIEWER.value, VaultRole.EDITOR.value):
        return jsonify({"error": "Invalid role. Must be 1 (viewer) or 2 (editor)."}), 400

    try:
        vault_service.grant_vault_access(vault_id, int(user_id), role)
        return jsonify({"message": "Access granted."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

# ADDED '/vaults' TO THE ROUTE BELOW
@admin_bp.route('/vaults/<int:vault_id>/access/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def revoke_vault_access(vault_id, user_id):
    """Revoke a user's/agent's access to a vault."""
    try:
        vault_service.revoke_vault_access(vault_id, user_id)
        return jsonify({"message": "Access revoked."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400