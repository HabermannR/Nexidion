"""
Service-Schicht für die Benutzerverwaltung.

Diese Schicht implementiert die Geschäftslogik für Operationen, die typischerweise
von einem Administrator ausgeführt werden, wie das Erstellen, Auflisten, Löschen
und Verwalten von Benutzern. Sie interagiert direkt mit dem User-Model.
"""

from backend.models import db, User, UserType


def get_all_users() -> list[User]:
    """Returns all human users, sorted alphabetically by username."""
    return User.query.filter_by(user_type=UserType.HUMAN).order_by(User.username).all()


def get_all_users_including_llm() -> list[User]:
    """Returns all users including llm_assistant accounts, sorted by display name."""
    return User.query.order_by(User.display_name).all()


def create_user(username: str, password: str, display_name: str | None = None, is_admin: bool = False) -> User:
    """
    Creates a new human user in the system.

    Args:
        username: Unique login username.
        password: Initial password (must be >= 8 characters).
        display_name: Display name; falls back to username if omitted.
        is_admin: Whether the user has administrator privileges.

    Returns:
        The newly created User object.

    Raises:
        ValueError: If the username is empty/taken or the password is too short.
    """
    stripped_username = username.strip()
    if not stripped_username:
        raise ValueError("Username cannot be empty.")

    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    if User.query.filter_by(username=stripped_username).first():
        raise ValueError(f"Username '{stripped_username}' already exists.")

    new_user = User(
        username=stripped_username,
        display_name=display_name.strip() if display_name else stripped_username,
        is_admin=bool(is_admin),
        user_type=UserType.HUMAN,
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return new_user


def delete_user(user_id_to_delete: int, acting_user_id: int):
    """
    Deletes a user with safety guards.

    Args:
        user_id_to_delete: ID of the user to delete.
        acting_user_id: ID of the admin performing the action.

    Raises:
        ValueError: If the target user is not found.
        PermissionError: If the admin tries to delete themselves or the last admin.
    """
    if user_id_to_delete == acting_user_id:
        raise PermissionError("You cannot delete your own account.")

    user_to_delete = db.session.get(User, user_id_to_delete)
    if not user_to_delete:
        raise ValueError(f"User with ID {user_id_to_delete} not found.")

    if user_to_delete.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            raise PermissionError("Cannot delete the last remaining administrator.")

    db.session.delete(user_to_delete)
    db.session.commit()


def set_user_password(user_id: int, new_password: str) -> bool:
    """
    Sets a user's password without requiring the old one (admin action).

    Args:
        user_id: ID of the user whose password should be changed.
        new_password: The new plaintext password.

    Returns:
        True on success.

    Raises:
        ValueError: If the user is not found, the password is too short,
                    or the target is a non-human account.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters long.")

    if user.user_type != UserType.HUMAN:
        raise ValueError("Cannot set a password for a non-human user account.")

    user.set_password(new_password)
    db.session.commit()
    return True


def update_user_details(user_id: int, updates: dict) -> User:
    """
    Updates specific fields of a user.

    Args:
        user_id: ID of the user to update.
        updates: Dict of fields to change, e.g. {'is_admin': True}.

    Returns:
        The updated User object.

    Raises:
        ValueError: If the user is not found, a field is not updatable,
                    or a value has the wrong type.
        PermissionError: If the update would remove the last administrator.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    # Whitelist of fields an admin may change.
    allowed_fields = {'username', 'display_name', 'is_admin'}

    for field, value in updates.items():
        if field not in allowed_fields:
            raise ValueError(f"Field '{field}' cannot be updated.")

        if field == 'is_admin':
            if not isinstance(value, bool):
                raise ValueError("'is_admin' must be a boolean.")
            # Guard: don't strip the last admin of their privileges.
            if user.is_admin and not value:
                admin_count = User.query.filter_by(is_admin=True).count()
                if admin_count <= 1:
                    raise PermissionError("Cannot remove admin status from the last administrator.")
            setattr(user, field, value)

        elif field == 'username':
            stripped_value = value.strip()
            if not stripped_value:
                raise ValueError("Username cannot be empty.")
            existing_user = User.query.filter(
                User.username == stripped_value,
                User.id != user_id
            ).first()
            if existing_user:
                raise ValueError(f"Username '{stripped_value}' is already taken.")
            setattr(user, field, stripped_value)

        else:
            setattr(user, field, value)

    db.session.commit()
    return user
