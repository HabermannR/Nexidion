from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from backend.models import db, ImageAsset
from backend.services.image_asset_service import create_asset, asset_path, delete_asset
from backend.services.vault_service import get_vault_access


image_bp = Blueprint('images', __name__, url_prefix='/api/vaults/<int:vault_id>/assets')


@image_bp.post('')
@jwt_required()
def upload_asset(vault_id):
    upload = request.files.get('file')
    if not upload:
        return jsonify({'error': "Image is required in multipart field 'file'."}), 400
    try:
        asset = create_asset(vault_id, int(get_jwt_identity()), upload.read(), upload.filename,
                             declared_type=upload.mimetype)
        return jsonify({'id': asset.id, 'url': f'/api/vaults/{vault_id}/assets/{asset.id}',
                        'media_type': asset.media_type, 'width': asset.width, 'height': asset.height}), 201
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403


@image_bp.get('/<string:asset_id>')
@jwt_required()
def serve_asset(vault_id, asset_id):
    try:
        get_vault_access(vault_id, int(get_jwt_identity()))
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    asset = db.session.get(ImageAsset, asset_id)
    if not asset or asset.vault_id != vault_id:
        return jsonify({'error': 'Image asset not found.'}), 404
    path = asset_path(asset)
    if not path.is_file():
        return jsonify({'error': 'Image asset file is missing.'}), 404
    return send_file(path, mimetype=asset.media_type, conditional=True, etag=asset.content_hash,
                     download_name=asset.original_filename)


@image_bp.delete('/<string:asset_id>')
@jwt_required()
def remove_asset(vault_id, asset_id):
    asset = db.session.get(ImageAsset, asset_id)
    if not asset or asset.vault_id != vault_id:
        return jsonify({'error': 'Image asset not found.'}), 404
    try:
        delete_asset(asset, int(get_jwt_identity()))
        return '', 204
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 409
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
