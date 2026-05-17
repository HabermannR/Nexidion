# tests/services/test_import_service.py

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from backend.services.import_service import import_vault
from backend.services import vault_service
from backend.models import db, Vault, Node, Version, DemoState
from backend.exceptions import DemoLockError


@pytest.fixture
def valid_export_data():
    """Generates a mock .nexidion export dictionary for testing."""
    return {
        "nexidion_export_version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vault": {
            "name": "Exported Vault"
        },
        "nodes": [
            {
                "id": "old-root-uuid",
                "parent_id": None,
                "icon": "bxs-folder",
                "title": "Root Node",
                "content": "Check out [[old-child-uuid]]!",
                "versions": [
                    {
                        "version": 1,
                        "title": "Root Node",
                        "content": "Check out [[old-child-uuid]]!",
                        "created_at": "2024-01-01T12:00:00Z",
                        "author_display_name": "Test Author"
                    }
                ]
            },
            {
                "id": "old-child-uuid",
                "parent_id": "old-root-uuid",
                "icon": "bxs-file-doc",
                "title": "Child Node",
                "content": "This is a child node.",
                "versions": [
                    {
                        "version": 1,
                        "title": "Child Node",
                        "content": "This is a child node.",
                        "created_at": "2024-01-01T12:05:00Z",
                        "author_display_name": "Test Author"
                    }
                ]
            }
        ]
    }


def test_import_vault_success(db_session, test_user_1_obj, valid_export_data):
    """
    Tests successfully importing a vault from a dictionary.
    Verifies that nodes are created, tree structure is maintained,
    and internal links are rewritten with fresh UUIDs.
    """
    # Act: Import the data as a new vault
    vault_id, remap = import_vault(
        path=valid_export_data,
        owner_id=test_user_1_obj.id,
        vault_name_override="Imported Vault Override Name"
    )

    # Assert: Vault creation
    vault = db.session.get(Vault, vault_id)
    assert vault is not None
    assert vault.name == "Imported Vault Override Name"
    assert vault.owner_id == test_user_1_obj.id

    # Assert: Remap dictionary contains both nodes
    assert "old-root-uuid" in remap
    assert "old-child-uuid" in remap

    new_root_id = remap["old-root-uuid"]
    new_child_id = remap["old-child-uuid"]

    # Assert: Nodes exist and structure is maintained
    root_node = db.session.get(Node, new_root_id)
    child_node = db.session.get(Node, new_child_id)

    assert root_node is not None
    assert child_node is not None
    assert root_node.parent_id is None
    assert child_node.parent_id == new_root_id

    # Assert: Content was imported and links were rewritten correctly
    root_version = root_node.current_version_object
    assert root_version.title == "Root Node"
    # The old [[old-child-uuid]] should now point to [[new_child_id]]
    assert f"[[{new_child_id}]]" in root_version.content
    assert "old-child-uuid" not in root_version.content


def test_import_vault_from_file_path(db_session, test_user_1_obj, valid_export_data, tmp_path):
    """
    Tests that the import service can read directly from a file path.
    """
    # Arrange: Write mock data to a temp file
    export_file = tmp_path / "test_export.nexidion"
    export_file.write_text(json.dumps(valid_export_data))

    # Act
    vault_id, remap = import_vault(
        path=export_file,
        owner_id=test_user_1_obj.id
    )

    # Assert
    vault = db.session.get(Vault, vault_id)
    assert vault is not None
    assert vault.name == "Exported Vault"  # Uses fallback since no override provided
    assert len(remap) == 2


def test_import_vault_invalid_version(db_session, test_user_1_obj):
    """Tests that missing or unsupported export format versions are rejected."""
    invalid_data = {
        "nexidion_export_version": 999,  # Unsupported
        "vault": {"name": "Test"},
        "nodes": []
    }

    with pytest.raises(ValueError, match="Unsupported or missing export format version"):
        import_vault(invalid_data, test_user_1_obj.id)


def test_import_vault_missing_keys(db_session, test_user_1_obj):
    """Tests that malformed JSON structures are rejected."""
    invalid_data = {
        "nexidion_export_version": 1,
        # Missing 'vault' and 'nodes'
    }

    with pytest.raises(ValueError, match="Invalid export format: missing 'vault' or 'nodes'"):
        import_vault(invalid_data, test_user_1_obj.id)


def test_import_vault_name_collision(db_session, test_user_1_obj, valid_export_data):
    """Tests that importing a vault with a name the user already uses throws an error."""
    # Arrange: Create a vault first
    vault_service.create_vault(name="Exported Vault", owner_id=test_user_1_obj.id)

    # Act & Assert
    with pytest.raises(ValueError, match="You already own a vault named 'Exported Vault'"):
        import_vault(valid_export_data, test_user_1_obj.id)


def test_import_vault_demo_lock(db_session, test_user_1_obj, valid_export_data):
    """Tests that guest users in READ_ONLY demo state cannot import vaults."""
    # Arrange: Set user to locked guest
    test_user_1_obj.is_guest = True
    test_user_1_obj.demo_state = DemoState.READ_ONLY
    db.session.commit()

    # Act & Assert
    with pytest.raises(DemoLockError, match="Complete the demo task to unlock importing"):
        import_vault(valid_export_data, test_user_1_obj.id)