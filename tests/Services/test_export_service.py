# tests/services/test_export_service.py

import json
import pytest
from backend.services.export_service import export_vault
from backend.services import vault_service, node_service
from backend.models import Node, VaultRole


def test_export_vault_success(db_session, test_user_1_obj):
    """
    Testet den erfolgreichen Export eines Vaults.
    Erstellt eine Node-Hierarchie über den node_service, um
    das BFS-Traversal (insbesondere queue.append) sauber abzudecken.
    """
    # 1. Vault erstellen (erzeugt Root-Node automatisch)
    vault = vault_service.create_vault(name="Export Test Vault", owner_id=test_user_1_obj.id)
    root_node = Node.query.filter_by(vault_id=vault.id, parent_id=None).one()

    # 2. Hierarchie ordnungsgemäß über den Service aufbauen (korrekte Usage)
    # Signature: create_node(title, content, parent_id, vault_id, user_id)
    child1 = node_service.create_node(
        "Child 1", "C1", root_node.id, vault.id, test_user_1_obj.id
    )
    child2 = node_service.create_node(
        "Child 2", "C2", root_node.id, vault.id, test_user_1_obj.id
    )

    # 3. Zweite Ebene an Child 1 hängen
    grandchild = node_service.create_node(
        "Grandchild", "GC", child1.id, vault.id, test_user_1_obj.id
    )

    # Act: Vault exportieren
    json_str = export_vault(vault.id, test_user_1_obj.id)
    data = json.loads(json_str)

    # Assert: Basic Export Properties
    assert data["nexidion_export_version"] == 1
    assert "exported_at" in data
    assert data["vault"]["name"] == "Export Test Vault"

    # Assert: BFS Sort Order (Root -> Child 1 & Child 2 -> Grandchild)
    nodes = data["nodes"]
    assert len(nodes) == 4

    # Node 0: Root (muss als erstes kommen, weil parent_id=None)
    assert nodes[0]["id"] == root_node.id
    assert nodes[0]["parent_id"] is None

    # Nodes 1 & 2: Children (müssen vor dem Grandchild in der Queue abgebaut werden)
    child_ids = {child1.id, child2.id}
    assert nodes[1]["id"] in child_ids
    assert nodes[2]["id"] in child_ids
    assert nodes[1]["parent_id"] == root_node.id
    assert nodes[2]["parent_id"] == root_node.id

    # Node 3: Grandchild (wurde von Child 1 der Queue hinzugefügt, kommt also zuletzt)
    assert nodes[3]["id"] == grandchild.id
    assert nodes[3]["parent_id"] == child1.id
    assert nodes[3]["title"] == "Grandchild"
    assert len(nodes[3]["versions"]) == 1


def test_export_vault_not_found(test_user_1_obj):
    """Testet, dass ein Fehler geworfen wird, wenn ein Vault nicht existiert."""
    with pytest.raises(ValueError, match="not found"):
        export_vault(9999, test_user_1_obj.id)


def test_export_vault_permission_denied(db_session, test_user_1_obj, test_user_2_obj):
    """Testet, dass nur der Besitzer den Vault exportieren kann, selbst wenn andere Zugriff haben."""
    from backend.services import vault_service

    # Vault für User 1 erstellen und User 2 als Editor hinzufügen
    vault = vault_service.create_vault(name="Owner Vault", owner_id=test_user_1_obj.id)
    vault_service.grant_vault_access(vault.id, test_user_2_obj.id, role=VaultRole.EDITOR.value)

    # Act & Assert: User 2 versucht den Vault von User 1 zu exportieren
    with pytest.raises(PermissionError, match="Only the vault owner may export this vault."):
        export_vault(vault.id, test_user_2_obj.id)