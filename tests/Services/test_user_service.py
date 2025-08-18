# tests/services/test_user_service.py

import pytest
from backend.services import user_service
from backend.models import User


# --- Tests für get_all_users ---

def test_get_all_users_empty(db_session):
    """Testet, dass eine leere Liste zurückgegeben wird, wenn keine Benutzer existieren."""
    users = user_service.get_all_users()
    assert users == []


def test_get_all_users_returns_list_sorted(db_session, test_user_1_obj, test_user_2_obj, test_admin_obj):
    """Testet, dass alle Benutzer in alphabetischer Reihenfolge zurückgegeben werden."""
    # Fixtures erstellen Benutzer 'user1', 'user2', 'admin_user'
    users = user_service.get_all_users()
    assert len(users) == 3
    assert users[0].username == 'admin_user'
    assert users[1].username == 'user1'
    assert users[2].username == 'user2'


# --- Tests für create_user ---

def test_create_user_success(db_session):
    """Testet die erfolgreiche Erstellung eines Standardbenutzers."""
    new_user = user_service.create_user(
        username="newbie",
        password="password1234",
        display_name="New Bie"
    )

    # Aus der DB holen, um Persistenz zu prüfen
    user_in_db = User.query.filter_by(username="newbie").one()

    assert user_in_db is not None
    assert user_in_db.id == new_user.id
    assert user_in_db.display_name == "New Bie"
    assert user_in_db.is_admin is False
    assert user_in_db.check_password("password1234") is True
    assert user_in_db.check_password("wrongpassword") is False


def test_create_user_as_admin_success(db_session):
    """Testet die erfolgreiche Erstellung eines Administrators."""
    admin_user = user_service.create_user(
        username="boss",
        password="supersecurepassword",
        is_admin=True
    )
    assert admin_user.is_admin is True


def test_create_user_fails_on_duplicate_username(db_session, test_user_1_obj):
    """Testet, dass die Erstellung mit einem bereits vergebenen Benutzernamen fehlschlägt."""
    with pytest.raises(ValueError, match="'user1' already exists"):
        user_service.create_user(username="user1", password="password123")


def test_create_user_fails_on_empty_username(db_session):
    """Testet, dass die Erstellung mit einem leeren Benutzernamen fehlschlägt."""
    with pytest.raises(ValueError, match="Username cannot be empty"):
        user_service.create_user(username="  ", password="password123")


def test_create_user_fails_on_short_password(db_session):
    """Testet, dass die Erstellung mit einem zu kurzen Passwort fehlschlägt."""
    with pytest.raises(ValueError, match="Password must be at least 8 characters long"):
        user_service.create_user(username="someuser", password="short")


# --- Tests für delete_user ---

def test_delete_user_success(db_session, test_admin_obj, test_user_1_obj):
    """Testet das erfolgreiche Löschen eines Benutzers durch einen Admin."""
    user_id_to_delete = test_user_1_obj.id
    admin_id = test_admin_obj.id

    user_service.delete_user(user_id_to_delete, acting_user_id=admin_id)

    deleted_user = db_session.session.get(User, user_id_to_delete)
    assert deleted_user is None


def test_delete_user_fails_on_self_delete(db_session, test_admin_obj):
    """Testet, dass ein Admin sich nicht selbst löschen kann."""
    admin_id = test_admin_obj.id
    with pytest.raises(PermissionError, match="You cannot delete your own account."):
        user_service.delete_user(user_id_to_delete=admin_id, acting_user_id=admin_id)


def test_delete_user_fails_on_last_admin(db_session, test_admin_obj):
    """Testet, dass der letzte verbleibende Admin nicht gelöscht werden kann."""
    # Die Fixture 'test_admin_obj' ist der einzige Admin in der DB.
    with pytest.raises(PermissionError, match="Cannot delete the last remaining administrator."):
        user_service.delete_user(user_id_to_delete=test_admin_obj.id,
                                 acting_user_id=999)  # acting_user_id ist irrelevant hier


def test_delete_user_fails_on_not_found(db_session, test_admin_obj):
    """Testet, dass das Löschen eines nicht existierenden Benutzers fehlschlägt."""
    with pytest.raises(ValueError, match="User with ID 999 not found."):
        user_service.delete_user(user_id_to_delete=999, acting_user_id=test_admin_obj.id)


# --- Tests für set_user_password ---

def test_set_user_password_success(db_session, test_user_1_obj):
    """Testet das erfolgreiche Zurücksetzen eines Passworts durch einen Admin."""
    user_id = test_user_1_obj.id

    # Überprüfen, ob das alte Passwort funktioniert
    assert test_user_1_obj.check_password("password123") is True

    result = user_service.set_user_password(user_id, "a-brand-new-password")

    assert result is True

    # Benutzer neu aus der DB laden, um die Änderung zu bestätigen
    updated_user = db_session.session.get(User, user_id)
    assert updated_user.check_password("a-brand-new-password") is True
    assert updated_user.check_password("password123") is False


def test_set_user_password_fails_user_not_found(db_session):
    """Testet das Setzen eines Passworts für einen nicht existierenden Benutzer."""
    with pytest.raises(ValueError, match="User with ID 999 not found."):
        user_service.set_user_password(999, "any_password")


def test_set_user_password_fails_new_password_too_short(db_session, test_user_1_obj):
    """Testet das Setzen eines zu kurzen Passworts."""
    with pytest.raises(ValueError, match="New password must be at least 8 characters long."):
        user_service.set_user_password(test_user_1_obj.id, "short")


# --- Tests für update_user_details ---

def test_update_user_details_success(db_session, test_user_1_obj):
    """Testet die erfolgreiche Aktualisierung von Benutzerdetails."""
    user_id = test_user_1_obj.id
    updates = {
        "display_name": "User One (Updated)",
        "is_admin": True
    }
    updated_user = user_service.update_user_details(user_id, updates)

    assert updated_user.display_name == "User One (Updated)"
    assert updated_user.is_admin is True


def test_update_user_details_fails_username_conflict(db_session, test_user_1_obj, test_user_2_obj):
    """Testet, dass die Aktualisierung fehlschlägt, wenn ein Benutzername bereits vergeben ist."""
    with pytest.raises(ValueError, match="Username 'user2' is already taken."):
        user_service.update_user_details(test_user_1_obj.id, {"username": "user2"})


def test_update_user_details_fails_remove_last_admin(db_session, test_admin_obj):
    """Testet, dass der Admin-Status des letzten Admins nicht entfernt werden kann."""
    with pytest.raises(PermissionError, match="Cannot remove admin status from the last administrator."):
        user_service.update_user_details(test_admin_obj.id, {"is_admin": False})


def test_update_user_details_fails_disallowed_field(db_session, test_user_1_obj):
    """Testet, dass das Aktualisieren eines nicht erlaubten Feldes fehlschlägt."""
    with pytest.raises(ValueError, match="Field 'password_hash' cannot be updated."):
        user_service.update_user_details(test_user_1_obj.id, {"password_hash": "some_hash"})


def test_update_user_details_fails_empty_username(db_session, test_user_1_obj):
    """Testet, dass der Benutzername nicht auf einen leeren String gesetzt werden kann."""
    with pytest.raises(ValueError, match="Username cannot be empty."):
        user_service.update_user_details(test_user_1_obj.id, {"username": "  "})


def test_get_all_users_returns_only_humans_sorted(db_session, test_user_1_obj, test_user_2_obj, test_admin_obj,
                                                  test_llm_user_obj):
    """
    Testet, dass get_all_users NUR menschliche Benutzer zurückgibt,
    korrekt sortiert. Der LLM-Benutzer muss ignoriert werden.
    """
    # Arrange: Die Fixtures erstellen 3 menschliche Benutzer und 1 LLM-Benutzer.

    # Act
    users = user_service.get_all_users()

    # Assert
    assert len(users) == 3  # Prüft, dass der LLM-Benutzer NICHT dabei ist.

    # Prüft die korrekte Sortierung und Zusammensetzung
    assert users[0].username == 'admin_user'
    assert users[1].username == 'user1'
    assert users[2].username == 'user2'

    # Explizite Prüfung, dass der LLM-Benutzer nicht in der Liste ist
    usernames = {u.username for u in users}
    assert test_llm_user_obj.username not in usernames