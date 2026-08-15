import pytest

from backend.models import db
from backend.services import node_policy_service, node_service, vault_service


def _tree(db_session, user):
    vault = vault_service.create_vault("Policy vault", user.id)
    root = node_service.create_node("Root", "root", None, vault.id, user.id)
    child = node_service.create_node("Child", "secret", root.id, vault.id, user.id)
    return vault, root, child


def test_human_lock_always_implies_ai_lock(db_session, test_user_1_obj):
    _, root, _ = _tree(db_session, test_user_1_obj)
    node_policy_service.set_local_policy(
        root, ai_read="allow", ai_write_locked=False,
        human_write_locked=True, note=None,
    )
    db.session.commit()
    assert root.human_write_locked is True
    assert root.ai_write_locked is True


def test_child_inherits_quarantine_and_explicit_opt_in(db_session, test_user_1_obj):
    vault, root, child = _tree(db_session, test_user_1_obj)
    node_policy_service.set_local_policy(
        root, ai_read="explicit_only", ai_write_locked=False,
        human_write_locked=False, note="review first",
    )
    db.session.commit()

    with pytest.raises(PermissionError, match="quarantined"):
        node_service.get_node_by_id(
            child.id, vault.id, test_user_1_obj.id, actor_type="mcp"
        )
    result = node_service.get_node_by_id(
        child.id, vault.id, test_user_1_obj.id, actor_type="mcp",
        include_quarantined=True,
    )
    assert result["content"] == "secret"
    assert result["effective_access_policy"]["ai_read"] == "explicit_only"


def test_ai_invisible_cannot_be_overridden(db_session, test_user_1_obj):
    vault, root, child = _tree(db_session, test_user_1_obj)
    node_policy_service.set_local_policy(
        root, ai_read="deny", ai_write_locked=True,
        human_write_locked=False, note=None,
    )
    db.session.commit()
    with pytest.raises(PermissionError, match="unavailable"):
        node_service.get_node_by_id(
            child.id, vault.id, test_user_1_obj.id, actor_type="mcp",
            include_quarantined=True,
        )


def test_ai_write_lock_blocks_mcp_but_not_human(db_session, test_user_1_obj):
    vault, root, _ = _tree(db_session, test_user_1_obj)
    node_policy_service.set_local_policy(
        root, ai_read="allow", ai_write_locked=True,
        human_write_locked=False, note=None,
    )
    db.session.commit()
    with pytest.raises(PermissionError, match="AI write-locked"):
        node_service.update_node(
            root.id, vault.id, test_user_1_obj.id, content="mcp edit",
            actor_type="mcp",
        )
    updated = node_service.update_node(
        root.id, vault.id, test_user_1_obj.id, content="human edit"
    )
    assert updated.current_version_object.content == "human edit"


def test_human_write_lock_blocks_human_and_ai(db_session, test_user_1_obj):
    vault, root, _ = _tree(db_session, test_user_1_obj)
    node_policy_service.set_local_policy(
        root, ai_read="allow", ai_write_locked=False,
        human_write_locked=True, note=None,
    )
    db.session.commit()
    for actor_type in (None, "mcp"):
        with pytest.raises(PermissionError, match="write-locked"):
            node_service.update_node(
                root.id, vault.id, test_user_1_obj.id, content="blocked",
                actor_type=actor_type,
            )


def test_clearing_parent_quarantine_does_not_clear_child(db_session, test_user_1_obj):
    vault, root, child = _tree(db_session, test_user_1_obj)
    node_service.update_node_access_policy(
        root.id, vault.id, test_user_1_obj.id, ai_read="explicit_only",
        ai_write_locked=True, human_write_locked=False,
    )
    db.session.refresh(child)
    assert child.ai_read_policy == "explicit_only"

    node_service.update_node_access_policy(
        root.id, vault.id, test_user_1_obj.id, ai_read="allow",
        ai_write_locked=False, human_write_locked=False,
    )
    db.session.refresh(child)
    assert root.ai_read_policy == "allow"
    assert child.ai_read_policy == "explicit_only"
    assert node_policy_service.effective_policy(child).ai_read == "explicit_only"


def test_new_child_under_quarantine_is_stamped_locally(db_session, test_user_1_obj):
    vault, root, _ = _tree(db_session, test_user_1_obj)
    node_service.update_node_access_policy(
        root.id, vault.id, test_user_1_obj.id, ai_read="explicit_only",
        ai_write_locked=True, human_write_locked=False,
    )
    child = node_service.create_node("Later child", "later", root.id, vault.id, test_user_1_obj.id)
    assert child.ai_read_policy == "explicit_only"


def test_move_into_quarantine_is_sticky_after_move_out(db_session, test_user_1_obj):
    vault, root, _ = _tree(db_session, test_user_1_obj)
    quarantine = node_service.create_node("Quarantine", "", None, vault.id, test_user_1_obj.id)
    moving = node_service.create_node("Moving", "", None, vault.id, test_user_1_obj.id)
    descendant = node_service.create_node("Moving child", "", moving.id, vault.id, test_user_1_obj.id)
    node_service.update_node_access_policy(
        quarantine.id, vault.id, test_user_1_obj.id, ai_read="explicit_only",
        ai_write_locked=True, human_write_locked=False,
    )

    node_service.move_node(moving.id, quarantine.id, vault.id, test_user_1_obj.id)
    db.session.refresh(moving)
    db.session.refresh(descendant)
    assert moving.ai_read_policy == "explicit_only"
    assert descendant.ai_read_policy == "explicit_only"

    node_service.move_node(moving.id, None, vault.id, test_user_1_obj.id)
    assert node_policy_service.effective_policy(moving).ai_read == "explicit_only"
