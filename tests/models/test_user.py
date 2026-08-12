from backend.models import User, UserType

def test_user_set_password_for_human():
    """Testet, ob für einen 'human' User ein Passwort-Hash erstellt wird."""
    user = User(username="human_user", display_name="Human", user_type=UserType.HUMAN)
    user.set_password("a-strong-password")
    assert user.password_hash is not None
    assert user.password_hash != "a-strong-password"  # Sicherstellen, dass es gehasht wurde


def test_user_set_password_for_llm_assistant_does_nothing():
    """Testet, dass für einen 'llm_assistant' KEIN Passwort-Hash erstellt wird."""
    llm_user = User(username="llm_user", display_name="LLM", user_type=UserType.LLM_ASSISTANT)

    # If set_password raises a ValueError (as suggested previously), we catch it.
    # If it silently returns, it just skips this block.
    try:
        llm_user.set_password("some-password")
    except ValueError:
        pass

    assert llm_user.password_hash is None  # Hier darf kein Hash gesetzt werden


def test_user_check_password_with_correct_password():
    """Testet die erfolgreiche Passwortprüfung."""
    user = User(username="testuser", display_name="Test", user_type=UserType.HUMAN)
    user.set_password("correct-password")
    assert user.check_password("correct-password") is True


def test_user_check_password_with_incorrect_password():
    """Testet die fehlgeschlagene Passwortprüfung."""
    user = User(username="testuser", display_name="Test", user_type=UserType.HUMAN)
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
        user_type=UserType.LLM_ASSISTANT
    )
    # Sicherstellen, dass der Hash wirklich None ist
    assert user_without_password.password_hash is None

    # ACT & ASSERT: Rufe check_password auf. Es muss False zurückgeben.
    assert user_without_password.check_password("any-password") is False
