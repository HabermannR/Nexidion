import pytest
from backend.services import auth_service
from backend.models import User

def test_login_user_success(test_user_1_obj):
    """
    Testet die auth_service.login_user Funktion mit korrekten Daten.
    Die Fixture 'test_user_1_obj' stellt sicher, dass der User in der DB ist.
    """
    # Direkter Aufruf der Python-Funktion
    user = auth_service.login_user(username='user1', password='password123')

    # Wir prüfen das Ergebnis direkt
    assert user is not None
    assert isinstance(user, User)
    assert user.id == test_user_1_obj.id
    assert user.username == 'user1'

def test_login_user_failure_wrong_password(test_user_1_obj):
    """
    Testet die auth_service.login_user Funktion mit falschem Passwort.
    """
    user = auth_service.login_user(username='user1', password='wrongpassword')

    # Der Service sollte None zurückgeben
    assert user is None

def test_login_user_failure_unknown_user(db_session):
    """
    Testet die auth_service.login_user Funktion mit einem unbekannten User.
    """
    user = auth_service.login_user(username='unknown_user', password='password123')

    # Der Service sollte None zurückgeben
    assert user is None

def test_login_user_failure_no_user(db_session):
    """
    Testet die auth_service.login_user Funktion mit einem unbekannten User.
    """
    user = auth_service.login_user(username='', password='password123')

    # Der Service sollte None zurückgeben
    assert user is None

def test_change_password_user_not_found(db_session):
    """Testet, dass die Passwortänderung für einen nicht existierenden User fehlschlägt."""
    with pytest.raises(ValueError, match="User not found."):
        auth_service.change_password(
            user_id=999,
            old_password="any_password",
            new_password="any_new_password"
        )

def test_change_password_new_password_too_short(test_user_1_obj):
    """Testet, dass die Passwortänderung bei einem zu kurzen neuen Passwort fehlschlägt."""
    with pytest.raises(ValueError, match="New password must be at least 8 characters long."):
        auth_service.change_password(
            user_id=test_user_1_obj.id,
            old_password="password123",
            new_password="short"  # Weniger als 8 Zeichen
        )

