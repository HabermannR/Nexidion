# backend/api/vaults.py
import json
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.services import vault_service
from backend.services.export_service import export_vault
from backend.services.import_service import import_vault
from backend.exceptions import DemoLockError, InsufficientVaultRoleError

vaults_bp = Blueprint('vaults', __name__, url_prefix='/api/vaults')


@vaults_bp.route('/', methods=['GET'], strict_slashes=False)
@jwt_required()
def list_vaults():
    current_user_id = int(get_jwt_identity())
    client_etag = request.headers.get('If-None-Match')

    data, etag, not_modified = vault_service.get_vaults_for_user_cached(
        current_user_id, client_etag
    )

    if not_modified:
        return Response(status=304, headers={'ETag': f'"{etag}"'})

    response = jsonify(data)
    response.headers['ETag'] = f'"{etag}"'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@vaults_bp.route('/<int:vault_id>', methods=['GET'])
@jwt_required()
def get_vault_details(vault_id):
    current_user_id = int(get_jwt_identity())
    try:
        vault = vault_service.get_vault_by_id(vault_id, user_id=current_user_id)
        return jsonify(vault.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403


@vaults_bp.route('/<int:vault_id>/export', methods=['GET'])
@jwt_required()
def export_vault_endpoint(vault_id):
    current_user_id = int(get_jwt_identity())
    try:
        json_str = export_vault(vault_id, current_user_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423

    vault = vault_service.get_vault_by_id(vault_id, user_id=current_user_id)
    safe_name = vault.name.replace('"', '').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.nexidion"

    return Response(
        json_str,
        status=200,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
    )


@vaults_bp.route('/import', methods=['POST'], strict_slashes=False)
@jwt_required()
def import_vault_endpoint():
    current_user_id = int(get_jwt_identity())

    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    try:
        data = json.load(file)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file."}), 400
    except UnicodeDecodeError:
        return jsonify({"error": "File must be valid JSON."}), 400

    vault_name_override = request.form.get('name')

    try:
        vault_id, remap = import_vault(
            path=data,
            owner_id=current_user_id,
            vault_name_override=vault_name_override
        )
        vault = vault_service.get_vault_by_id(vault_id, user_id=current_user_id)
        return jsonify(vault.to_dict()), 201
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred during import: {str(e)}"}), 500


@vaults_bp.route('/', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_vault():
    current_user_id = int(get_jwt_identity())
    vault_name = request.json.get('name')
    if not vault_name:
        return jsonify({"error": "Vault name is required"}), 400

    try:
        new_vault = vault_service.create_vault(name=vault_name, owner_id=current_user_id)
        return jsonify(new_vault.to_dict()), 201
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423
    except ValueError as e:
        return jsonify({"error": str(e)}), 409  # 409 Conflict


@vaults_bp.route('/<int:vault_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def rename_vault(vault_id):
    current_user_id = int(get_jwt_identity())
    new_name = request.json.get('name')
    if not new_name:
        return jsonify({"error": "New name is required"}), 400

    try:
        updated_vault = vault_service.rename_vault(vault_id, new_name, user_id=current_user_id)
        return jsonify(updated_vault.to_dict())
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423
    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        error_message = str(e)
        status_code = 404 if "not found" in error_message.lower() else 409
        return jsonify({"error": error_message}), status_code


@vaults_bp.route('/<int:vault_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_vault(vault_id):
    current_user_id = int(get_jwt_identity())
    try:
        vault_service.delete_vault(vault_id, user_id=current_user_id)
        return jsonify({"message": f"Vault with ID {vault_id} deleted."}), 200
    except DemoLockError as e:
        return jsonify({"error": str(e)}), 423
    except (PermissionError, InsufficientVaultRoleError) as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            return jsonify({"error": error_message}), 404
        else:
            return jsonify({"error": error_message}), 400