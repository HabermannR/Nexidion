from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pymupdf
from flask import current_app

from backend.models import db, ImageAsset, User, Node, Version
from backend.services.vault_service import get_vault_access, assert_write_allowed


ALLOWED_MEDIA = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif'}
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def storage_root() -> Path:
    root = Path(current_app.config['ASSET_STORAGE_FOLDER']).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _inspect(data: bytes, declared_type: str | None):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Image must be between 1 byte and 25 MiB.')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        detected = 'png'
    elif data.startswith(b'\xff\xd8\xff'):
        detected = 'jpeg'
    elif data.startswith((b'GIF87a', b'GIF89a')):
        detected = 'gif'
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        detected = 'webp'
    else:
        detected = None
    media = {'png': 'image/png', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}.get(detected)
    if not media or media not in ALLOWED_MEDIA:
        raise ValueError('Only PNG, JPEG, GIF, and WebP images are supported.')
    try:
        pix = pymupdf.Pixmap(data)
        width, height = pix.width, pix.height
    except Exception:
        width = height = None
    return media, ALLOWED_MEDIA[media], width, height


def create_asset(vault_id: int, user_id: int, data: bytes, filename: str | None = None,
                 source_artifact_id: str | None = None, page_number: int | None = None,
                 declared_type: str | None = None) -> ImageAsset:
    _, role = get_vault_access(vault_id, user_id)
    assert_write_allowed(role, db.session.get(User, user_id))
    media, extension, width, height = _inspect(data, declared_type)
    digest = hashlib.sha256(data).hexdigest()
    existing = ImageAsset.query.filter_by(vault_id=vault_id, content_hash=digest).first()
    if existing:
        return existing
    key = f'{vault_id}/{uuid.uuid4()}.{extension}'
    target = storage_root() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, target)
    asset = ImageAsset(vault_id=vault_id, source_artifact_id=source_artifact_id,
        content_hash=digest, storage_key=key, original_filename=filename,
        media_type=media, width=width, height=height, page_number=page_number,
        created_by_id=user_id)
    db.session.add(asset)
    db.session.commit()
    return asset


def asset_path(asset: ImageAsset) -> Path:
    root = storage_root()
    path = (root / asset.storage_key).resolve()
    if root not in path.parents:
        raise ValueError('Invalid asset storage key.')
    return path


def delete_asset(asset: ImageAsset, user_id: int):
    _, role = get_vault_access(asset.vault_id, user_id)
    assert_write_allowed(role, db.session.get(User, user_id))
    reference = f'/api/vaults/{asset.vault_id}/assets/{asset.id}'
    version_refs = Version.query.join(Node).filter(Node.vault_id == asset.vault_id,
                                                   Version.content.contains(reference)).count()
    summary_refs = Node.query.filter(Node.vault_id == asset.vault_id,
                                     Node.ai_summary.contains(reference)).count()
    if version_refs or summary_refs:
        raise ValueError(f'Image asset is still referenced ({version_refs} versions, {summary_refs} summaries).')
    path = asset_path(asset)
    db.session.delete(asset)
    db.session.commit()
    path.unlink(missing_ok=True)
