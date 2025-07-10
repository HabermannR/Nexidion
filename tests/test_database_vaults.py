import pytest
from backend import database
from backend.models import User, Vault

def test_create_vault_with_empty_name_fails(test_user_1_obj, db_session):
    """Testet, dass die Erstellung mit einem leeren Namen fehlschlägt."""
    with pytest.raises(ValueError, match="Vault name cannot be empty."):
        database.create_vault_with_root_node(name="  ", owner_id=test_user_1_obj.id)

def test_create_vault_with_duplicate_name_fails(test_user_1_obj, test_vault_1_obj, db_session):
    """Testet, dass die Erstellung eines Vaults mit gleichem Namen für denselben User fehlschlägt."""
    with pytest.raises(ValueError, match="You already own a vault named 'Vault For User 1'."):
        # test_vault_1_obj hat bereits einen Vault mit diesem Namen erstellt
        database.create_vault_with_root_node(name="Vault For User 1", owner_id=test_user_1_obj.id)

def test_create_vault_with_nonexistent_owner_fails(db_session):
    """Testet, dass die Erstellung mit einer ungültigen owner_id fehlschlägt."""
    with pytest.raises(ValueError, match="Owner with ID 999 not found."):
        database.create_vault_with_root_node(name="Some Vault", owner_id=999)

def test_rename_vault_success(test_user_1_obj, test_vault_1_obj, db_session):
    """Testet das erfolgreiche Umbenennen eines Vaults."""
    renamed_vault = database.rename_vault(
        vault_id=test_vault_1_obj.id,
        new_name="Renamed Vault",
        user_id=test_user_1_obj.id
    )
    assert renamed_vault.name == "Renamed Vault"

def test_rename_vault_to_empty_name_fails(test_user_1_obj, test_vault_1_obj, db_session):
    """Testet, dass das Umbenennen zu einem leeren Namen fehlschlägt."""
    with pytest.raises(ValueError, match="New vault name cannot be empty."):
        database.rename_vault(test_vault_1_obj.id, "   ", test_user_1_obj.id)

def test_delete_last_vault_fails(test_user_1_obj, test_vault_1_obj, db_session):
    """Testet, dass das Löschen des letzten Vaults fehlschlägt."""
    with pytest.raises(ValueError, match="You cannot delete your last remaining vault."):
        database.delete_vault(test_vault_1_obj.id, test_user_1_obj.id)

def test_delete_vault_success(test_user_1_obj, db_session):
    """Testet das erfolgreiche Löschen eines Vaults (wenn es nicht der letzte ist)."""
    # Erstelle zwei Vaults
    vault1 = database.create_vault_with_root_node("Vault 1", test_user_1_obj.id)
    vault2 = database.create_vault_with_root_node("Vault 2", test_user_1_obj.id)
    assert db_session.session.get(Vault, vault1.id) is not None

    # Lösche einen davon
    database.delete_vault(vault1.id, test_user_1_obj.id)
    assert db_session.session.get(Vault, vault1.id) is None
    assert db_session.session.get(Vault, vault2.id) is not None

# tests/test_database_vaults.py
import pytest
from backend import database

def test_rename_vault_to_existing_name_fails(test_user_1_obj, db_session):
    """
    Testet, dass das Umbenennen eines Vaults zu einem bereits existierenden
    Namen für denselben Benutzer fehlschlägt.
    """
    # 1. ARRANGE: Erstelle ZWEI Vaults für denselben Benutzer.
    # Der erste Vault wird in der Fixture `test_vault_1_obj` erstellt.
    # Wir brauchen aber explizite Objekte.
    vault1 = database.create_vault_with_root_node("Vault One", test_user_1_obj.id)
    vault2 = database.create_vault_with_root_node("Vault Two", test_user_1_obj.id)

    # 2. ACT & ASSERT: Versuche, vault2 in "Vault One" umzubenennen.
    # Dies muss fehlschlagen, da der Name "Vault One" bereits für diesen Benutzer vergeben ist.
    with pytest.raises(ValueError, match="You already own another vault named 'Vault One'."):
        database.rename_vault(
            vault_id=vault2.id,
            new_name="Vault One", # Dieser Name existiert bereits für User 1
            user_id=test_user_1_obj.id
        )

    # Gegenprobe: Stelle sicher, dass nichts umbenannt wurde
    refreshed_vault2 = db_session.session.get(Vault, vault2.id)
    assert refreshed_vault2.name == "Vault Two"