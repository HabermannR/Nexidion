# backend/api/vaults.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.services import vault_service  # Importiere den neuen Service

# Wir passen den Blueprint an, um die Routen aus app.py zu spiegeln.
vaults_bp = Blueprint('vaults', __name__, url_prefix='/api/vaults')


@vaults_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def list_vaults():
    current_user_id = int(get_jwt_identity())
    # Rufe den Service auf
    vaults = vault_service.get_vaults_for_user(user_id=current_user_id)
    return jsonify([v.to_dict() for v in vaults])


# =================================================================
# === ADD THIS NEW ENDPOINT ===
# This is the missing piece that your frontend's useVaultQuery(vaultId) hook needs.
# =================================================================
@vaults_bp.route('/<int:vault_id>', methods=['GET'])
@jwt_required()
def get_vault_details(vault_id):
    current_user_id = int(get_jwt_identity())
    try:
        # We assume a service function exists to get a single vault and check permissions.
        vault = vault_service.get_vault_by_id(vault_id, user_id=current_user_id)
        return jsonify(vault.to_dict())
    except ValueError as e:
        # This typically means "not found" in your service layer.
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        # This means the user is not authorized for this vault.
        return jsonify({"error": str(e)}), 403
# =================================================================


@vaults_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_vault():
    current_user_id = int(get_jwt_identity())
    vault_name = request.json.get('name')
    if not vault_name:
        return jsonify({"error": "Vault name is required"}), 400

    try:
        # Rufe den Service auf
        new_vault = vault_service.create_vault(name=vault_name, owner_id=current_user_id)
        return jsonify(new_vault.to_dict()), 201
    except ValueError as e:
        # Fange spezifische Fehler vom Service ab und wandle sie in HTTP-Statuscodes um
        return jsonify({"error": str(e)}), 409  # 409 Conflict für "existiert bereits"


@vaults_bp.route('/<int:vault_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def rename_vault(vault_id):
    current_user_id = int(get_jwt_identity())
    new_name = request.json.get('name')
    if not new_name:
        return jsonify({"error": "New name is required"}), 400

    try:
        # Rufe den Service auf
        updated_vault = vault_service.rename_vault(vault_id, new_name, user_id=current_user_id)
        return jsonify(updated_vault.to_dict())
    except ValueError as e:
        # Kann "not found" oder "already exists" sein
        return jsonify({"error": str(e)}), 404  # Oder 409, je nach Fehlertext
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@vaults_bp.route('/<int:vault_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_vault(vault_id):
    current_user_id = int(get_jwt_identity())
    try:
        vault_service.delete_vault(vault_id, user_id=current_user_id)
        return jsonify({"message": f"Vault with ID {vault_id} deleted."}), 200
    except ValueError as e:
        # PRÜFE JETZT DIE FEHLERNACHRICHT
        error_message = str(e)
        if "not found" in error_message.lower():
            # Wenn der Vault nicht gefunden wurde, ist 404 korrekt.
            return jsonify({"error": error_message}), 404
        else:
            # Für alle anderen ValueErrors (z.B. "cannot delete last vault"),
            # ist 400 (Bad Request) eine bessere Wahl.
            return jsonify({"error": error_message}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403