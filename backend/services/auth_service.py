# services/auth_service.py

from backend.models import db, User, UserType


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

    # Query using the IntEnum's integer value
    user = User.query.filter_by(username=username, user_type=UserType.HUMAN.value).first()

    if not user:
        # Debugging: Did the user type get stored weirdly?
        debug_user = User.query.filter_by(username=username).first()
        if debug_user:
            print(f"\n[DEBUG] Found '{username}' but user_type is {debug_user.user_type} (Expected: {UserType.HUMAN.value})")
        else:
            print(f"\n[DEBUG] User '{username}' not found in DB at all.")
        return None

    if not user.check_password(password):
        print(f"\n[DEBUG] Password check failed for '{username}'.")
        return None

    return user


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """
    Changes a user's password after verifying the old one.

    Args:
        user_id: The user's ID.
        old_password: The current password for verification.
        new_password: The new password to set.

    Returns:
        True on success, False if the old password was wrong.

    Raises:
        ValueError: If the user is not found or the new password is too short.
    """
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found.")

    # Validate the new password before doing the expensive bcrypt compare.
    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters long.")

    if not user.check_password(old_password):
        return False

    user.set_password(new_password)
    db.session.commit()
    return True
