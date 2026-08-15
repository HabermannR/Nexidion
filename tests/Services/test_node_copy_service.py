from unittest.mock import patch

import pytest

from backend.exceptions import InsufficientVaultRoleError
from backend.models import db, Node, User, UserType, VaultAccess, VaultRole, Version
from backend.services.node_copy_service import copy_node_to_vault


def _node(vault_id, author_id, title, content='', parent_id=None, **kwargs):
    node = Node(vault_id=vault_id, parent_id=parent_id, current_version=1, **kwargs)
    db.session.add(node)
    db.session.flush()
    db.session.add(Version(node_id=node.id, version=1, title=title,
                           content=content, author_id=author_id))
    db.session.flush()
    return node


def _grant(user_id, vault_id, role=VaultRole.EDITOR):
    db.session.add(VaultAccess(user_id=user_id, vault_id=vault_id, role=role))
    db.session.commit()


def test_copy_subtree_preserves_fields_and_rewrites_only_internal_strong_links(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    external = '11111111-2222-3333-4444-555555555555'
    root = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Root', '',
                 icon='bxs-folder', ai_summary='summary', summary_is_current=True,
                 content_kind='document', authority='imported', language='de',
                 tags=['a'], metadata_json={'source': 'manual'})
    child = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Child', 'body', root.id)
    root.current_version_object.content = f'[[Child|{child.id}]] [[External|{external}]]'
    db.session.commit()

    result = copy_node_to_vault(root.id, test_vault_1_obj.id, test_vault_2_obj.id,
                                test_user_1_obj.id)

    copied_root = db.session.get(Node, result['root_node_id'])
    copied_child = db.session.get(Node, result['uuid_map'][child.id])
    assert result['copied_count'] == 2
    assert copied_child.parent_id == copied_root.id
    assert copied_root.id != root.id
    assert copied_root.current_version == 1
    assert copied_root.current_version_object.content == (
        f'[[Child|{copied_child.id}]] [[External|{external}]]')
    assert copied_root.ai_summary == 'summary'
    assert copied_root.summary_is_current is True
    assert (copied_root.icon, copied_root.content_kind, copied_root.authority,
            copied_root.language, copied_root.tags, copied_root.metadata_json) == (
        'bxs-folder', 'document', 'imported', 'de', ['a'], {'source': 'manual'})
    assert copied_root.current_version_object.author_id == test_user_1_obj.id
    assert result['connector_bindings_copied'] is False


def test_non_recursive_copy_and_destination_parent(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Source')
    _node(test_vault_1_obj.id, test_user_1_obj.id, 'Child', parent_id=source.id)
    parent = _node(test_vault_2_obj.id, test_user_1_obj.id, 'Destination')
    db.session.commit()

    result = copy_node_to_vault(source.id, test_vault_1_obj.id, test_vault_2_obj.id,
                                test_user_1_obj.id, recursive=False,
                                destination_parent_id=parent.id)
    assert result['copied_count'] == 1
    assert db.session.get(Node, result['root_node_id']).parent_id == parent.id


def test_copy_requires_destination_write_access(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id, VaultRole.VIEWER)
    source = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Source')
    db.session.commit()
    with pytest.raises(InsufficientVaultRoleError, match='read-only'):
        copy_node_to_vault(source.id, test_vault_1_obj.id, test_vault_2_obj.id,
                           test_user_1_obj.id)


def test_machine_actor_cannot_copy_private_descendant(
        db_session, test_user_1_obj, test_llm_agent_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_llm_agent_obj.id, test_vault_1_obj.id)
    _grant(test_llm_agent_obj.id, test_vault_2_obj.id)
    root = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Root')
    _node(test_vault_1_obj.id, test_user_1_obj.id, 'Private', parent_id=root.id,
          icon='bxs-no-entry', ai_read_policy='deny', ai_write_locked=True)
    db.session.commit()
    with pytest.raises(PermissionError, match='unavailable'):
        copy_node_to_vault(root.id, test_vault_1_obj.id, test_vault_2_obj.id,
                           test_llm_agent_obj.id)


def test_copy_preserves_access_policy_metadata(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(
        test_vault_1_obj.id, test_user_1_obj.id, 'Protected',
        ai_read_policy='deny', ai_write_locked=True, human_write_locked=True,
        policy_note='Reviewed reference')
    db.session.commit()

    result = copy_node_to_vault(
        source.id, test_vault_1_obj.id, test_vault_2_obj.id, test_user_1_obj.id)
    copied = db.session.get(Node, result['root_node_id'])

    assert copied.ai_read_policy == 'deny'
    assert copied.ai_write_locked is True
    assert copied.human_write_locked is True
    assert copied.policy_note == 'Reviewed reference'


def test_copy_rejects_locked_destination_parent(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Source')
    parent = _node(
        test_vault_2_obj.id, test_user_1_obj.id, 'Locked destination',
        human_write_locked=True, ai_write_locked=True)
    db.session.commit()

    with pytest.raises(PermissionError, match='write-locked'):
        copy_node_to_vault(
            source.id, test_vault_1_obj.id, test_vault_2_obj.id,
            test_user_1_obj.id, destination_parent_id=parent.id)


def test_copy_into_quarantine_stamps_copied_subtree(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Source')
    child = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Child', parent_id=source.id)
    parent = _node(
        test_vault_2_obj.id, test_user_1_obj.id, 'Quarantine',
        ai_read_policy='explicit_only', ai_write_locked=True)
    db.session.commit()

    result = copy_node_to_vault(
        source.id, test_vault_1_obj.id, test_vault_2_obj.id,
        test_user_1_obj.id, destination_parent_id=parent.id)

    copied_root = db.session.get(Node, result['root_node_id'])
    copied_child = db.session.get(Node, result['uuid_map'][child.id])
    assert copied_root.ai_read_policy == 'explicit_only'
    assert copied_child.ai_read_policy == 'explicit_only'
    assert copied_root.ai_write_locked is True
    assert copied_child.ai_write_locked is True


def test_copy_rejects_managed_image_and_leaves_destination_unchanged(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(
        test_vault_1_obj.id, test_user_1_obj.id, 'Image',
        f'![x](/api/vaults/{test_vault_1_obj.id}/assets/'
        '11111111-2222-3333-4444-555555555555)')
    db.session.commit()
    before = Node.query.filter_by(vault_id=test_vault_2_obj.id).count()
    with pytest.raises(ValueError, match='managed image'):
        copy_node_to_vault(source.id, test_vault_1_obj.id, test_vault_2_obj.id,
                           test_user_1_obj.id)
    assert Node.query.filter_by(vault_id=test_vault_2_obj.id).count() == before


def test_copy_rolls_back_on_commit_failure(
        db_session, test_user_1_obj, test_vault_1_obj, test_vault_2_obj):
    _grant(test_user_1_obj.id, test_vault_2_obj.id)
    source = _node(test_vault_1_obj.id, test_user_1_obj.id, 'Source')
    db.session.commit()
    before = Node.query.filter_by(vault_id=test_vault_2_obj.id).count()
    with patch.object(db.session, 'commit', side_effect=RuntimeError('database failure')):
        with pytest.raises(RuntimeError, match='database failure'):
            copy_node_to_vault(source.id, test_vault_1_obj.id, test_vault_2_obj.id,
                               test_user_1_obj.id)
    assert Node.query.filter_by(vault_id=test_vault_2_obj.id).count() == before
