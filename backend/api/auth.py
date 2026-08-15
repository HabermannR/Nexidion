# api/auth.py
from datetime import timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from backend.extensions import limiter
from backend.models import User
from backend.services import auth_service

auth_bp = Blueprint('auth_v2', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'], strict_slashes=False)
@limiter.limit("20 per minute; 100 per hour")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = auth_service.login_user(username, password)

    if user:
        access_token = create_access_token(
            identity=str(user.id),
            expires_delta=timedelta(hours=8),
        )
        return jsonify(access_token=access_token, user=user.to_dict())

    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route('/me', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_current_user_profile():
    current_user_id = int(get_jwt_identity())
    user = auth_service.get_user_by_id(current_user_id)
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({"error": "User not found"}), 404


@auth_bp.route('/actor-token', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("30 per minute; 300 per hour")
def create_actor_token():
    """Exchange a user token for a short-lived, more restrictive actor token."""
    data = request.get_json(silent=True) or {}
    actor_type = data.get('actor_type')
    if actor_type != 'mcp':
        return jsonify({"error": "actor_type must be mcp"}), 400
    token = create_access_token(
        identity=str(get_jwt_identity()),
        additional_claims={"actor_type": "mcp"},
        expires_delta=timedelta(minutes=15),
    )
    return jsonify(access_token=token, actor_type="mcp"), 200


@auth_bp.route('/change-password', methods=['POST'], strict_slashes=False)
@jwt_required()
@limiter.limit("10 per hour")
def change_user_password():
    current_user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
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
        return jsonify({"error": str(e)}), 400
