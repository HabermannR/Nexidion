# services/auth_service.py

from backend.models import db, User

def login_user(username: str, password: str) -> User | None:
    """
    Authenticates a user based on username and password.

    This service handles the core business logic of finding a user
    and verifying their password. It is decoupled from the HTTP layer.

    Args:
        username: The user's username.
        password: The user's password.

    Returns:
        The User object if authentication is successful, otherwise None.
    """
    if not username or not password:
        return None

    # Wir suchen nur nach menschlichen Benutzern, die sich einloggen können.
    user = User.query.filter_by(username=username, user_type='human').first()

    if user and user.check_password(password):
        return user

    return None

def get_user_by_id(user_id: int) -> User | None:
    """
    Holt einen Benutzer anhand seiner ID aus der Datenbank.
    """
    return db.session.get(User, user_id)


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """
    Ändert das Passwort eines Benutzers nach Überprüfung des alten Passworts.

    Args:
        user_id: Die ID des Benutzers.
        old_password: Das aktuelle Passwort zur Verifizierung.
        new_password: Das neue zu setzende Passwort.

    Returns:
        True bei Erfolg, False wenn das alte Passwort falsch war.

    Raises:
        ValueError: Wenn der Benutzer nicht gefunden wird.
    """
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found.")

    if not user.check_password(old_password):
        return False  # Altes Passwort stimmt nicht überein

    # Validierungsregeln für das neue Passwort (Beispiel)
    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters long.")

    user.set_password(new_password)
    db.session.commit()
    return True