from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps

# Passe die Importe an deine Projektstruktur an
from backend.services import user_service
from backend.models import db, User

# Erstelle den Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# --- Custom Decorator für Admin-Autorisierung ---

def admin_required(fn):
    """
    Ein Decorator, der sicherstellt, dass der eingeloggte Benutzer Admin-Rechte hat.
    Muss NACH @jwt_required() verwendet werden.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user_id = int(get_jwt_identity())
        user = db.session.get(User, current_user_id)
        if user and user.is_admin:
            return fn(*args, **kwargs)
        else:
            return jsonify({"error": "Admin privileges required"}), 403
    return wrapper


# --- API Endpunkte für die Benutzerverwaltung ---

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def list_users():
    """
    [ADMIN] Listet alle Benutzer im System auf.
    """
    users = user_service.get_all_users()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route('/users', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    """
    [ADMIN] Erstellt einen neuen Benutzer.
    """
    data = request.get_json()
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
        # Fängt Fehler wie "username exists" oder "password too short" ab
        # 409 Conflict ist passend für "already exists"
        return jsonify({"error": str(e)}), 409


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """
    [ADMIN] Löscht einen Benutzer.
    """
    acting_user_id = int(get_jwt_identity())
    try:
        user_service.delete_user(user_id_to_delete=user_id, acting_user_id=acting_user_id)
        return jsonify({"message": f"User with ID {user_id} deleted successfully."}), 200
    except ValueError as e:
        # Fängt "User not found"
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        # Fängt "Cannot delete self" oder "Cannot delete last admin"
        return jsonify({"error": str(e)}), 403


@admin_bp.route('/users/<int:user_id>/password', methods=['PUT'])
@jwt_required()
@admin_required
def set_user_password(user_id):
    """
    [ADMIN] Setzt oder ändert das Passwort für einen Benutzer.
    """
    data = request.get_json()
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({"error": "Field 'new_password' is required"}), 400

    try:
        user_service.set_user_password(user_id, new_password)
        return jsonify({"message": "Password updated successfully."}), 200
    except ValueError as e:
        # Fängt "User not found" oder "password too short"
        status_code = 404 if "not found" in str(e).lower() else 400
        return jsonify({"error": str(e)}), status_code


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user_details(user_id):
    """
    [ADMIN] Aktualisiert Benutzerdetails wie display_name oder is_admin.
    """
    updates = request.get_json()
    if not updates:
        return jsonify({"error": "Request body cannot be empty."}), 400

    try:
        updated_user = user_service.update_user_details(user_id, updates)
        return jsonify(updated_user.to_dict()), 200
    except ValueError as e:
        # Fängt "User not found", "username taken", etc.
        status_code = 404 if "not found" in str(e).lower() else 409
        return jsonify({"error": str(e)}), status_code
    except PermissionError as e:
        # Fängt "Cannot remove admin status from last admin"
        return jsonify({"error": str(e)}), 403