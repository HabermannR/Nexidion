# api/auth.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from backend.services import auth_service
from datetime import timedelta


# Erstelle einen Blueprint. Der erste Parameter ist der Name des Blueprints.
# Der zweite ist __name__, damit Flask weiß, wo er definiert wurde.
# url_prefix sorgt dafür, dass alle Routen in diesem Blueprint mit /api/auth beginnen.
auth_bp = Blueprint('auth_v2', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'], strict_slashes=False)
def login():
    """
    API endpoint for user login.
    Handles HTTP request/response and uses the auth_service for logic.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Rufe den Service auf, um die Authentifizierung durchzuführen
    user = auth_service.login_user(username, password)

    if user:
        # Erfolgsfall bleibt gleich
        identity_as_string = str(user.id)
        expires = timedelta(hours=8)  # 8 Stunden für einen normalen Arbeitstag
        access_token = create_access_token(identity=identity_as_string, expires_delta=expires)

        return jsonify(access_token=access_token, user=user.to_dict())
    return jsonify({"error": "Invalid credentials"}), 401

@auth_bp.route('/me', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_current_user_profile():
    current_user_id = int(get_jwt_identity())
    user = auth_service.get_user_by_id(current_user_id) # Ruft den Service auf
    if user:
        return jsonify(user=user.to_dict()), 200
    return jsonify({"error": "User not found"}), 404

@auth_bp.route('/change-password', methods=['POST'], strict_slashes=False)
@jwt_required()
def change_user_password():
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({"error": "Old and new password are required"}), 400

    try:
        success = auth_service.change_password(current_user_id, old_password, new_password)
        if success:
            return jsonify({"msg": "Password updated successfully"}), 200
        else:
            return jsonify({"error": "Invalid old password"}), 401
    except ValueError as e:
        # Fängt Fehler aus dem Service ab (z.B. User nicht gefunden, Passwort zu kurz)
        return jsonify({"error": str(e)}), 400