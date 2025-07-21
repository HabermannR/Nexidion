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

def test_user_set_password_for_human():
    """Testet, ob für einen 'human' User ein Passwort-Hash erstellt wird."""
    user = User(username="human_user", display_name="Human", user_type="human")
    user.set_password("a-strong-password")
    assert user.password_hash is not None
    assert user.password_hash != "a-strong-password" # Sicherstellen, dass es gehasht wurde

def test_user_set_password_for_llm_assistant_does_nothing():
    """Testet, dass für einen 'llm_assistant' KEIN Passwort-Hash erstellt wird."""
    llm_user = User(username="llm_user", display_name="LLM", user_type="llm_assistant")
    llm_user.set_password("some-password")
    assert llm_user.password_hash is None # Hier darf kein Hash gesetzt werden

def test_user_check_password_with_correct_password():
    """Testet die erfolgreiche Passwortprüfung."""
    user = User(username="testuser", display_name="Test", user_type="human")
    user.set_password("correct-password")
    assert user.check_password("correct-password") is True

def test_user_check_password_with_incorrect_password():
    """Testet die fehlgeschlagene Passwortprüfung."""
    user = User(username="testuser", display_name="Test", user_type="human")
    user.set_password("correct-password")
    assert user.check_password("wrong-password") is False

def test_user_check_password_on_user_with_no_hash():
    """
    Testet den Fall, dass check_password für einen Benutzer ohne Passwort-Hash aufgerufen wird.
    Dies deckt den `return False`-Zweig ab.
    """
    # ARRANGE: Erstelle einen Benutzer, der keinen Passwort-Hash hat (z.B. ein LLM-Assistent)
    user_without_password = User(
        username="no_pass_user",
        display_name="No Password User",
        user_type="llm_assistant"
    )
    # Sicherstellen, dass der Hash wirklich None ist
    assert user_without_password.password_hash is None

    # ACT & ASSERT: Rufe check_password auf. Es muss False zurückgeben.
    assert user_without_password.check_password("any-password") is False