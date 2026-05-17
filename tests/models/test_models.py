# tests/test_models.py
from backend.models import UserType

def test_user_creation(test_user_1_obj):
    """Testet, ob die User-Fixture korrekt in die DB geschrieben wird."""
    assert test_user_1_obj.username == 'user1'
    assert test_user_1_obj.user_type == UserType.HUMAN
    assert test_user_1_obj.check_password('password123') is True

def test_vault_creation(test_vault_1_obj):
    """Testet die Vault-Fixture."""
    assert test_vault_1_obj.name == 'Vault For User 1'
    assert test_vault_1_obj.owner.username == 'user1'

def test_node_and_version(test_node_obj):
    """Testet, ob Node und Version korrekt verknüpft sind."""
    assert test_node_obj.current_version == 1
    # Prüft, ob der Title aus dem Version-Model über die Relationship geholt wird
    assert test_node_obj.current_version_object.title == "Test Node"
    assert test_node_obj.current_version_object.content == "This is the content of the test node."

def test_task_creation(test_task_obj):
    """Testet das neue Task-Modell für den Task Runner."""
    assert test_task_obj.status == "pending"
    assert test_task_obj.instruction == "Please summarize the test node."