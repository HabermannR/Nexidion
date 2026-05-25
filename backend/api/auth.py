# api/auth.py
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from backend.extensions import limiter
from backend.models import db, User, UserType, VaultAccess, VaultRole, DemoState
from backend.services import auth_service
from backend.services.import_service import import_vault

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


@auth_bp.route('/guest', methods=['POST'], strict_slashes=False)
@limiter.limit("3 per hour")
def guest_login():
    if not current_app.config["DEMO_MODE_ENABLED"]:
        return jsonify({"error": "Demo mode is not enabled."}), 403

    agent = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
    if not agent:
        return jsonify({"error": "Agent not configured."}), 503

    guest = User(
        username     = f"guest-{uuid.uuid4().hex[:8]}",
        display_name = "Guest",
        user_type    = UserType.HUMAN,
        is_guest     = True,
        demo_state   = DemoState.READ_ONLY,
        expires_at   = datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.session.add(guest)
    db.session.flush()

    vault_id, remap = import_vault(
        path=current_app.config["DEMO_VAULT_PATH"],
        owner_id=guest.id,
        vault_name_override="Demo Vault",
    )
    guest.demo_remap = remap

    db.session.add(VaultAccess(
        vault_id=vault_id,
        user_id=agent.id,
        role=VaultRole.EDITOR,
    ))
    db.session.commit()

    token = create_access_token(
        identity=str(guest.id),
        expires_delta=timedelta(hours=2),
    )
    return jsonify(access_token=token, user=guest.to_dict()), 201
