from pathlib import Path

from PIL import Image

from backend.models import Node, Version, ImageAsset
from backend.services.legacy_image_conversion import convert_legacy_images


def test_conversion_is_dry_run_by_default_and_idempotent(
        app, db_session, test_node_obj, test_vault_1_obj, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    Image.new('RGB', (4, 3), 'blue').save(legacy / 'Old Image.png')
    current = test_node_obj.current_version_object
    current.content = 'Before\n\n![Diagram](/api/image/Old%20Image.png)'
    db_session.session.commit()

    dry = convert_legacy_images(legacy)
    assert dry['converted'] == 1
    assert ImageAsset.query.count() == 0
    assert test_node_obj.current_version == 1

    applied = convert_legacy_images(legacy, apply=True)
    db_session.session.refresh(test_node_obj)
    assert applied['converted'] == 1
    assert ImageAsset.query.count() == 1
    assert test_node_obj.current_version == 2
    assert f'/api/vaults/{test_vault_1_obj.id}/assets/' in test_node_obj.current_version_object.content

    repeated = convert_legacy_images(legacy, apply=True)
    db_session.session.refresh(test_node_obj)
    assert repeated['references'] == 0
    assert test_node_obj.current_version == 2


def test_conversion_rasterizes_legacy_svg_before_storage(
        app, db_session, test_node_obj, tmp_path):
    app.config['ASSET_STORAGE_FOLDER'] = str(tmp_path / 'assets')
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    (legacy / 'diagram.svg').write_text(
        '<div xmlns="http://www.w3.org/1999/xhtml"><svg '
        'xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
        '<script>alert(1)</script><rect width="20" height="10" fill="blue"/></svg></div>',
        encoding='utf-8',
    )
    test_node_obj.current_version_object.content = '![Diagram](/api/image/diagram.svg)'
    db_session.session.commit()

    report = convert_legacy_images(legacy, apply=True)

    asset = ImageAsset.query.one()
    assert report['missing'] == []
    assert report['converted'] == 1
    assert asset.media_type == 'image/png'
    assert asset.original_filename == 'diagram.png'
    stored = Path(app.config['ASSET_STORAGE_FOLDER']) / asset.storage_key
    assert stored.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
