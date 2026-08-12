import io

from PIL import Image

from backend.models import ImageAsset


def _png_bytes(color='red'):
    stream = io.BytesIO()
    Image.new('RGB', (8, 6), color).save(stream, format='PNG')
    return stream.getvalue()


def test_asset_is_vault_scoped_and_deduplicated(
        app, client, auth_headers_1, auth_headers_2, test_vault_1_obj, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    payload = _png_bytes()
    first = client.post(f'/api/vaults/{test_vault_1_obj.id}/assets', headers=auth_headers_1,
        data={'file': (io.BytesIO(payload), 'diagram.png')}, content_type='multipart/form-data')
    assert first.status_code == 201
    asset_id = first.get_json()['id']
    assert first.get_json()['width'] == 8

    duplicate = client.post(f'/api/vaults/{test_vault_1_obj.id}/assets', headers=auth_headers_1,
        data={'file': (io.BytesIO(payload), 'copy.png')}, content_type='multipart/form-data')
    assert duplicate.status_code == 201
    assert duplicate.get_json()['id'] == asset_id
    assert ImageAsset.query.count() == 1

    own = client.get(f'/api/vaults/{test_vault_1_obj.id}/assets/{asset_id}', headers=auth_headers_1)
    assert own.status_code == 200
    assert own.mimetype == 'image/png'
    forbidden = client.get(f'/api/vaults/{test_vault_1_obj.id}/assets/{asset_id}', headers=auth_headers_2)
    assert forbidden.status_code == 403


def test_asset_rejects_non_image(app, client, auth_headers_1, test_vault_1_obj, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/assets', headers=auth_headers_1,
        data={'file': (io.BytesIO(b'<svg onload=alert(1)>'), 'attack.svg')},
        content_type='multipart/form-data')
    assert response.status_code == 400
