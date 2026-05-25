from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps

from backend.services import user_service, vault_service
from backend.models import db, User, VaultRole, DemoEvent

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ---------------------------------------------------------------------------
# Auth decorators
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


def demo_required(fn):
    """Guards demo-only endpoints. Returns 404 when DEMO_MODE_ENABLED is false.

    Stacks after @admin_required. Returning 404 (not 403) keeps these endpoints
    invisible to non-demo installs — they look like they simply don't exist.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("DEMO_MODE_ENABLED", False):
            return jsonify({"error": "Not found"}), 404
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


@admin_bp.route('/vaults/<int:vault_id>', methods=['PUT'])
@jwt_required()
@admin_required
def admin_rename_vault(vault_id):
    """[ADMIN] Rename any vault, bypassing owner check."""
    new_name = (request.get_json(silent=True) or {}).get('name', '').strip()
    if not new_name:
        return jsonify({"error": "New name is required."}), 400
    try:
        vault = vault_service.admin_rename_vault(vault_id, new_name)
        return jsonify(vault), 200
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 409
        return jsonify({"error": str(e)}), status_code


@admin_bp.route('/vaults/<int:vault_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def admin_delete_vault(vault_id):
    """[ADMIN] Delete any vault, bypassing owner check."""
    try:
        vault_service.admin_delete_vault(vault_id)
        return jsonify({"message": f"Vault {vault_id} deleted."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


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


# ---------------------------------------------------------------------------
# Demo Studio endpoints (DEMO_MODE_ENABLED=true only)
# ---------------------------------------------------------------------------

@admin_bp.route('/demo-stats', methods=['GET'])
@jwt_required()
@admin_required
def get_demo_stats():
    """[ADMIN] Cumulative demo analytics drawn from the DemoEvent table.

    DemoEvent rows persist after guest accounts are deleted, so these numbers
    are historically accurate even after the 2-hour cleanup cycle runs.
    """
    from sqlalchemy import func
    from datetime import datetime, timezone

    def count_event(event_type: str) -> int:
        return db.session.query(func.count(DemoEvent.id)).filter(
            DemoEvent.event_type == event_type
        ).scalar() or 0

    total_logins     = count_event('guest_login')
    phase2_unlocks   = count_event('phase2_unlock')
    node_creates     = count_event('node_created')

    # Active guests still alive in the DB (not yet cleaned up)
    active_guests = db.session.query(func.count(User.id)).filter(
        User.is_guest == True,
        User.expires_at > datetime.now(timezone.utc),
    ).scalar() or 0

    return jsonify({
        "total_guest_logins":      total_logins,
        "phase2_completions":      phase2_unlocks,
        "node_creates_by_guests":  node_creates,
        "active_guests_now":       active_guests,
        "conversion_rate_pct":     round(phase2_unlocks / total_logins * 100, 1) if total_logins else 0,
    }), 200


@admin_bp.route('/guests', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_all_guests():
    """[ADMIN] Hard-delete all guest accounts immediately, regardless of expiry."""
    from datetime import datetime, timezone

    guests = User.query.filter(User.is_guest == True).all()
    if not guests:
        return jsonify({"message": "No guest accounts found.", "deleted": 0}), 200

    deleted = 0
    errors = []
    for guest in guests:
        try:
            user_service.delete_guest_user(guest.id)
            deleted += 1
        except Exception as exc:
            errors.append({"user_id": guest.id, "error": str(exc)})

    response = {"deleted": deleted}
    if errors:
        response["errors"] = errors
    return jsonify(response), 200


@admin_bp.route('/replay-test', methods=['POST'])
@jwt_required()
@admin_required
@demo_required
def trigger_replay_test():
    """[DEMO] Queue a pending_demo task on any vault to smoke-test the replay engine."""
    from backend.models import Task, Vault

    data = request.get_json(silent=True) or {}
    vault_id = data.get('vault_id')
    if not vault_id:
        return jsonify({"error": "vault_id is required"}), 400
    try:
        vault_id = int(vault_id)
    except (TypeError, ValueError):
        return jsonify({"error": "vault_id must be an integer"}), 400

    vault = db.session.get(Vault, vault_id)
    if not vault:
        return jsonify({"error": f"Vault {vault_id} not found"}), 404

    task = Task(
        vault_id=vault_id,
        instruction="[admin replay test] Replay the demo recording.",
        context_node_ids=[],
        status='pending_demo',
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({
        "message": "pending_demo task queued. The runner will pick it up on its next tick.",
        "task_id": task.id,
        "vault_id": vault_id,
    }), 201


@admin_bp.route('/vaults/<int:vault_id>/reset-to-snapshot', methods=['POST'])
@jwt_required()
@admin_required
@demo_required
def reset_vault_to_snapshot(vault_id):
    """[DEMO] Wipe a vault's nodes and reimport from a .nexidion snapshot.

    Body (JSON):
        snapshot (dict): a parsed .nexidion export payload

    The "undo" step after a real agent run: resets the vault back to the clean
    demo baseline so it's ready for the next guest replay. The vault's owner
    and access grants are preserved — only nodes are replaced.
    """
    from backend.models import Node, Vault
    from backend.services.import_service import _create_node_from_export, _rewrite_internal_links
    from backend.services.node_service import rebuild_vault_tree_cache
    from backend.services.vault_service import invalidate_vault_list_cache

    data = request.get_json(silent=True) or {}
    snapshot = data.get("snapshot")
    if not snapshot:
        return jsonify({"error": "'snapshot' field (parsed .nexidion JSON) is required."}), 400

    vault = db.session.get(Vault, vault_id)
    if not vault:
        return jsonify({"error": f"Vault {vault_id} not found."}), 404

    # Delete all existing nodes (cascade deletes versions)
    db.session.execute(db.delete(Node).where(Node.vault_id == vault_id))
    db.session.flush()

    # Reimport in BFS order (the export already guarantees this)
    remap: dict[str, str] = {}
    for node_data in snapshot.get("nodes", []):
        new_id = _create_node_from_export(
            node_data=node_data,
            vault_id=vault_id,
            owner_id=vault.owner_id,
            remap=remap,
        )
        remap[node_data["id"]] = new_id

    _rewrite_internal_links(vault_id, remap)
    owner = db.session.get(User, vault.owner_id)
    owner.demo_remap = remap

    # Invalidate the vault-list cache before committing so the null
    # is written in the same transaction as the new nodes.
    invalidate_vault_list_cache(vault.owner_id)
    db.session.commit()

    # Tree cache rebuild reads committed data, so it must come after commit.
    rebuild_vault_tree_cache(vault_id)

    return jsonify({
        "message": f"Vault {vault_id} reset to snapshot state.",
        "vault_id": vault_id,
        "node_count": len(snapshot.get("nodes", [])),
    }), 200
