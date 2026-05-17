# tests/services/test_vault_service.py

import pytest
from unittest.mock import patch
from backend.services import vault_service
from backend.models import Vault, Node, Version, User, VaultRole


def test_create_vault_success(db_session, test_user_1_obj):
    """Testet die erfolgreiche Erstellung eines Vaults und seiner abhängigen Objekte."""
    # Act
    vault = vault_service.create_vault(name="My First Service Vault", owner_id=test_user_1_obj.id)

    # Assert - Wir prüfen detailliert, ob alles korrekt in der DB gelandet ist
    assert vault is not None
    assert vault.name == "My First Service Vault"
    assert vault.owner_id == test_user_1_obj.id

    # Prüfe, ob der Root-Node erstellt wurde
    root_node = Node.query.filter_by(vault_id=vault.id, parent_id=None).one_or_none()
    assert root_node is not None
    assert root_node.title == "Summary"

    # Prüfe, ob die initiale Version erstellt wurde
    initial_version = Version.query.filter_by(node_id=root_node.id).one_or_none()
    assert initial_version is not None
    assert initial_version.version == 1
    assert "root node for the 'My First Service Vault' vault" in initial_version.content
    assert initial_version.author_id == test_user_1_obj.id


def test_create_vault_with_empty_name_fails(test_user_1_obj):
    """Testet, dass die Erstellung mit einem leeren Namen fehlschlägt."""
    with pytest.raises(ValueError, match="Vault name cannot be empty."):
        vault_service.create_vault(name="  ", owner_id=test_user_1_obj.id)


def test_create_vault_with_duplicate_name_fails(test_user_1_obj, test_vault_1_obj):
    """Testet, dass die Erstellung eines Vaults mit gleichem Namen für denselben User fehlschlägt."""
    # Arrange: Die Fixture 'test_vault_1_obj' hat bereits einen Vault 'Vault For User 1' erstellt.
    with pytest.raises(ValueError, match="You already own a vault named 'Vault For User 1'."):
        vault_service.create_vault(name="Vault For User 1", owner_id=test_user_1_obj.id)


def test_create_vault_with_nonexistent_owner_fails(db_session):
    """Testet, dass die Erstellung mit einer ungültigen owner_id fehlschlägt."""
    with pytest.raises(ValueError, match="Owner with ID 999 not found."):
        vault_service.create_vault(name="Some Vault", owner_id=999)


def test_rename_vault_success(test_user_1_obj, test_vault_1_obj):
    """Testet das erfolgreiche Umbenennen eines Vaults."""
    # Act
    renamed_vault = vault_service.rename_vault(
        vault_id=test_vault_1_obj.id,
        new_name="Renamed Vault",
        user_id=test_user_1_obj.id
    )
    # Assert
    assert renamed_vault.name == "Renamed Vault"


def test_rename_vault_to_empty_name_fails(test_user_1_obj, test_vault_1_obj):
    """Testet, dass das Umbenennen zu einem leeren Namen fehlschlägt."""
    with pytest.raises(ValueError, match="New vault name cannot be empty."):
        vault_service.rename_vault(test_vault_1_obj.id, "   ", test_user_1_obj.id)


def test_rename_vault_to_existing_name_fails(test_user_1_obj):
    """Testet, dass das Umbenennen eines Vaults zu einem bereits existierenden Namen fehlschlägt."""
    # Arrange: Erstelle zwei Vaults
    vault1 = vault_service.create_vault("Vault One", test_user_1_obj.id)
    vault2 = vault_service.create_vault("Vault Two", test_user_1_obj.id)

    # Act & Assert
    with pytest.raises(ValueError, match="You already own another vault named 'Vault One'."):
        vault_service.rename_vault(
            vault_id=vault2.id,
            new_name="Vault One",
            user_id=test_user_1_obj.id
        )


def test_rename_vault_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_1_obj):
    """Testet, dass User 2 nicht den Vault von User 1 umbenennen kann."""
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        vault_service.rename_vault(
            vault_id=test_vault_1_obj.id,
            new_name="Hacked Vault",
            user_id=test_user_2_obj.id  # Falscher User
        )


def test_delete_last_vault_fails(test_user_1_obj, test_vault_1_obj):
    """Testet, dass das Löschen des letzten Vaults fehlschlägt."""
    with pytest.raises(ValueError, match="You cannot delete your last remaining vault."):
        vault_service.delete_vault(test_vault_1_obj.id, test_user_1_obj.id)


def test_delete_vault_success(test_user_1_obj, db_session):
    """Happy Path: Erfolgreiches Löschen eines Vaults, wenn es nicht der letzte ist."""
    # Arrange: Erstelle zwei Vaults über den Service, damit es schnell geht.
    from backend.services import vault_service
    vault1 = vault_service.create_vault("Vault to be deleted", test_user_1_obj.id)
    vault2 = vault_service.create_vault("Vault to keep", test_user_1_obj.id)

    # Überprüfen, ob sie vor dem Löschen existieren
    assert db_session.session.get(Vault, vault1.id) is not None

    # Act
    vault_service.delete_vault(vault1.id, test_user_1_obj.id)

    # Assert
    assert db_session.session.get(Vault, vault1.id) is None
    assert db_session.session.get(Vault, vault2.id) is not None

def test_delete_vault_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_1_obj):
    """Testet, dass User 2 nicht den Vault von User 1 löschen kann."""
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        vault_service.delete_vault(
            vault_id=test_vault_1_obj.id,
            user_id=test_user_2_obj.id  # Falscher User
        )

def test_rename_vault_to_same_name_does_nothing(test_user_1_obj, test_vault_1_obj):
    """Testet, dass das Umbenennen zum selben Namen keine Fehler wirft und nichts ändert."""
    # Act
    renamed_vault = vault_service.rename_vault(
        vault_id=test_vault_1_obj.id,
        new_name="Vault For User 1",  # Der ursprüngliche Name
        user_id=test_user_1_obj.id
    )
    # Assert
    assert renamed_vault.name == "Vault For User 1"

def test_rename_vault_not_found(test_user_1_obj):
    """Testet, dass das Umbenennen eines nicht existierenden Vaults fehlschlägt."""
    with pytest.raises(ValueError, match="Vault with ID 999 not found."):
        vault_service.rename_vault(
            vault_id=999,
            new_name="Doesn't Matter",
            user_id=test_user_1_obj.id
        )

def test_delete_vault_not_found(test_user_1_obj):
    """Testet, dass das Löschen eines nicht existierenden Vaults fehlschlägt."""
    with pytest.raises(ValueError, match="Vault with ID 999 not found."):
        vault_service.delete_vault(vault_id=999, user_id=test_user_1_obj.id)


from backend.models import VaultAccess


# --- Tests für get_vaults_for_user ---

def test_get_vaults_for_user(db_session, test_user_1_obj, test_user_2_obj, test_vault_1_obj, test_vault_2_obj):
    """Testet, dass die Funktion eigene Vaults und Vaults mit expliziten Zugriffsrechten zurückgibt."""
    # User 1 Zugriff auf den Vault von User 2 geben
    vault_service.grant_vault_access(test_vault_2_obj.id, test_user_1_obj.id, role=VaultRole.VIEWER.value )

    vaults = vault_service.get_vaults_for_user(test_user_1_obj.id)

    # User 1 sollte nun seinen eigenen Vault (1) und den Vault von User 2 (2) sehen
    vault_ids = {v.id for v in vaults}
    assert test_vault_1_obj.id in vault_ids
    assert test_vault_2_obj.id in vault_ids


# --- Tests für Admin Vault-Management (get_all_vaults, get_vault_access_list) ---

def test_get_all_vaults_success(db_session, test_user_1_obj, test_vault_1_obj):
    """[Admin] Testet den Abruf aller Vaults inklusive Metadaten (Besitzer, Zugriffsanzahl)."""
    vaults = vault_service.get_all_vaults()
    assert isinstance(vaults, list)
    assert len(vaults) >= 1

    v1_data = next((v for v in vaults if v["id"] == test_vault_1_obj.id), None)
    assert v1_data is not None
    assert v1_data["owner_id"] == test_user_1_obj.id
    assert v1_data["owner_username"] == test_user_1_obj.username
    assert "access_count" in v1_data


def test_get_all_vaults_missing_owner(db_session, test_vault_1_obj):
    """[Admin] Testet das Fallback, falls der Vault-Besitzer nicht gefunden wird."""

    original_get = db_session.session.get

    # Wir blockieren get() NUR für das User-Model. Alles andere funktioniert normal.
    def mock_get(entity, ident, **kwargs):
        if entity == User:
            return None
        return original_get(entity, ident, **kwargs)

    with patch('backend.services.vault_service.db.session.get', side_effect=mock_get):
        vaults = vault_service.get_all_vaults()
        v1_data = next((v for v in vaults if v["id"] == test_vault_1_obj.id), None)

        assert v1_data["owner_display_name"] == "Unknown"
        assert v1_data["owner_username"] == "unknown"


def test_get_vault_access_list_success(db_session, test_user_1_obj, test_user_2_obj, test_vault_1_obj):
    """[Admin] Testet den erfolgreichen Abruf der Zugriffsliste eines Vaults."""
    # User 2 Zugriff geben, damit er in access_list auftaucht
    vault_service.grant_vault_access(test_vault_1_obj.id, test_user_2_obj.id, role=VaultRole.VIEWER.value )

    data = vault_service.get_vault_access_list(test_vault_1_obj.id)

    assert data["vault"]["id"] == test_vault_1_obj.id
    assert data["vault"]["owner_id"] == test_user_1_obj.id

    # Prüfe die Zugriffsliste
    access_user_ids = {a["user_id"] for a in data["access_list"]}
    assert test_user_2_obj.id in access_user_ids

    # Prüfe die verfügbaren Nutzer (User 2 und Owner User 1 sollten fehlen)
    available_user_ids = {u["user_id"] for u in data["available_users"]}
    assert test_user_2_obj.id not in available_user_ids
    assert test_user_1_obj.id not in available_user_ids


def test_get_vault_access_list_not_found(db_session):  # <--- HIER FEHLTE DAS 'db_session' !
    """[Admin] Testet, dass bei einem ungültigen Vault ein Fehler geworfen wird."""
    with pytest.raises(ValueError, match="Vault 9999 not found."):
        vault_service.get_vault_access_list(9999)


# --- Tests für Admin Access Modifiers (grant_vault_access, revoke_vault_access) ---

def test_grant_vault_access_success(db_session, test_user_2_obj, test_vault_1_obj):
    """[Admin] Testet das Hinzufügen (und Updaten von Berechtigungen."""
    # 1. Access gewähren (Insert)
    vault_service.grant_vault_access(
        test_vault_1_obj.id,
        test_user_2_obj.id,
        role=VaultRole.VIEWER.value  # Changed from "viewer"
    )

    access = VaultAccess.query.filter_by(vault_id=test_vault_1_obj.id, user_id=test_user_2_obj.id).first()
    assert access is not None
    assert access.role == VaultRole.VIEWER.value  # Changed from "viewer"

    # 2. Access updaten (Update/Idempotenz)
    vault_service.grant_vault_access(
        test_vault_1_obj.id,
        test_user_2_obj.id,
        role=VaultRole.EDITOR.value  # Changed from "editor"
    )
    db_session.session.refresh(access)
    assert access.role == VaultRole.EDITOR.value  # Changed from "editor"


def test_grant_vault_access_fails_on_owner(test_user_1_obj, test_vault_1_obj):
    """[Admin] Testet, dass dem Vault-Besitzer keine expliziten Rechte gegeben werden dürfen."""
    with pytest.raises(ValueError, match="Cannot grant explicit access to the vault owner"):
        vault_service.grant_vault_access(test_vault_1_obj.id, test_user_1_obj.id)


def test_grant_vault_access_fails_invalid_entities(test_user_2_obj, test_vault_1_obj):
    """[Admin] Testet fehlerhafte IDs beim Gewähren von Rechten."""
    with pytest.raises(ValueError, match="Vault 9999 not found"):
        vault_service.grant_vault_access(9999, test_user_2_obj.id)

    with pytest.raises(ValueError, match="User 9999 not found"):
        vault_service.grant_vault_access(test_vault_1_obj.id, 9999)


def test_revoke_vault_access_success(db_session, test_user_2_obj, test_vault_1_obj):
    """[Admin] Testet das erfolgreiche Entziehen von Rechten."""
    # Erst gewähren, dann entziehen
    vault_service.grant_vault_access(test_vault_1_obj.id, test_user_2_obj.id)
    vault_service.revoke_vault_access(test_vault_1_obj.id, test_user_2_obj.id)

    access = VaultAccess.query.filter_by(vault_id=test_vault_1_obj.id, user_id=test_user_2_obj.id).first()
    assert access is None


def test_revoke_vault_access_fails_on_owner(test_user_1_obj, test_vault_1_obj):
    """[Admin] Testet, dass dem Vault-Besitzer nicht die Rechte entzogen werden können."""
    with pytest.raises(ValueError, match="Cannot revoke access from the vault owner"):
        vault_service.revoke_vault_access(test_vault_1_obj.id, test_user_1_obj.id)


def test_revoke_vault_access_fails_no_access(db_session, test_user_2_obj, test_vault_1_obj):
    """[Admin] Testet den Fall, wenn ein User gar keine Rechte hat, die entzogen werden könnten."""
    # Sicherstellen, dass keine Rechte vorhanden sind
    db_session.session.query(VaultAccess).filter_by(vault_id=test_vault_1_obj.id, user_id=test_user_2_obj.id).delete()
    db_session.session.commit()

    with pytest.raises(ValueError, match="does not have explicit access"):
        vault_service.revoke_vault_access(test_vault_1_obj.id, test_user_2_obj.id)


def test_revoke_vault_access_fails_invalid_vault(test_user_2_obj):
    """[Admin] Testet fehlerhafte Vault-IDs beim Entziehen."""
    with pytest.raises(ValueError, match="not found"):
        vault_service.revoke_vault_access(9999, test_user_2_obj.id)