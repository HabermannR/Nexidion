# backend/services/user_service.py
"""
Service-Schicht für die Benutzerverwaltung.

Diese Schicht implementiert die Geschäftslogik für Operationen, die typischerweise
von einem Administrator ausgeführt werden, wie das Erstellen, Auflisten, Löschen
und Verwalten von Benutzern. Sie interagiert direkt mit dem User-Model.
"""

import logging

from backend.models import db, User, UserType, Vault, Version, VaultAccess


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
    Deletes a user with safety guards. Reassigns their Vaults and Versions
    to an administrator to prevent data loss.

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

    # --- DATA REASSIGNMENT (Inheritance) ---
    
    # 1. Determine which Admin inherits the data (prefer the acting admin)
    acting_user = db.session.get(User, acting_user_id)
    if acting_user and acting_user.is_admin:
        heir_admin_id = acting_user_id
    else:
        # Fallback in case the actor isn't an admin, find the first available admin
        fallback_admin = User.query.filter_by(is_admin=True).filter(User.id != user_id_to_delete).first()
        if not fallback_admin:
            raise PermissionError("Cannot delete user: No admin available to inherit their data.")
        heir_admin_id = fallback_admin.id

    # 2. Reassign their owned Vaults — rename on collision with heir's existing vaults
    guest_vaults = Vault.query.filter_by(owner_id=user_id_to_delete).all()
    heir_existing_names = {
        v.name for v in Vault.query.filter_by(owner_id=heir_admin_id).all()
    }
    for vault in guest_vaults:
        target_name = vault.name
        if target_name in heir_existing_names:
            # Append the original owner username to avoid the unique constraint violation
            target_name = f"{vault.name} (from {user_to_delete.username})"
            # If that still collides, append the vault id as a last resort
            if target_name in heir_existing_names:
                target_name = f"{vault.name} (from {user_to_delete.username}, vault {vault.id})"
        vault.owner_id = heir_admin_id
        vault.name = target_name
        heir_existing_names.add(target_name)

    # 3. Reassign their authored Versions
    Version.query.filter_by(author_id=user_id_to_delete).update(
        {"author_id": heir_admin_id}, synchronize_session='fetch'
    )

    # 4. Delete their Vault Access rules (No inheritance needed here)
    VaultAccess.query.filter_by(user_id=user_id_to_delete).delete(synchronize_session='fetch')

    # 5. Delete the User
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


def delete_guest_user(guest_user_id: int) -> dict:
    """
    Hard-deletes an expired guest user and ALL their data.

    Unlike delete_user(), which is designed for permanent human accounts and
    reassigns vaults and versions to a heir admin, this function is a clean
    wipe — guest data has no value after expiry and must not pollute the
    admin's workspace.

    Deletion order and rationale:
      1. Version.author_id reassignment — author_id is nullable=False with no
         ON DELETE clause. The vault→node→version DB cascade will wipe the rows
         anyway, but we reassign first as a safety net against any version that
         has somehow become detached from its node (e.g. data inconsistency).
      2. Vault deletion — cascades at the DB level to:
             nodes (vault_id FK ondelete=CASCADE)
             → versions (node_id FK ondelete=CASCADE)
             tasks (vault_id FK ondelete=CASCADE)
             access_rules / VaultAccess (vault_id FK ondelete=CASCADE)
      3. Orphan VaultAccess cleanup — belt-and-suspenders for any access row
         keyed on user_id rather than vault_id (e.g. agent's cross-vault entry).
      4. User deletion.

    Args:
        guest_user_id: ID of the guest user to delete.

    Returns:
        A summary dict for logging:
        {"deleted_user": username, "vault_count": n, "version_count": n}

    Raises:
        ValueError: If the user is not found or is not flagged as a guest.
    """
    user = db.session.get(User, guest_user_id)
    if not user:
        raise ValueError(f"Guest user {guest_user_id} not found.")
    if not user.is_guest:
        raise ValueError(
            f"User {guest_user_id} ('{user.username}') is not a guest account. "
            "Use delete_user() for permanent accounts."
        )

    username = user.username
    vault_ids = [v.id for v in Vault.query.filter_by(owner_id=guest_user_id).all()]

    # Step 1: Reassign any authored versions so the nullable=False FK doesn't
    # block the user delete if the cascade chain above ever fails to reach them.
    fallback_admin = User.query.filter_by(is_admin=True).first()
    if fallback_admin:
        version_count = Version.query.filter_by(author_id=guest_user_id).update(
            {"author_id": fallback_admin.id}, synchronize_session="fetch"
        )
    else:
        # No admin exists (should never happen in production, but be safe).
        version_count = Version.query.filter_by(author_id=guest_user_id).count()
        logging.warning(
            f"[guest-cleanup] No admin found to reassign versions for guest "
            f"'{username}' ({guest_user_id}). Versions will be wiped by cascade."
        )

    # Step 2: Delete vaults — triggers DB-level cascade to nodes, versions,
    # tasks, and access_rules (see models.py for ondelete='CASCADE' declarations).
    for vault_id in vault_ids:
        vault = db.session.get(Vault, vault_id)
        if vault:
            db.session.delete(vault)

    # Step 3: Belt-and-suspenders — remove any VaultAccess rows still keyed on
    # this user_id that the vault cascade didn't reach (e.g. access on another
    # user's vault granted to this guest, which is not standard but possible).
    VaultAccess.query.filter_by(user_id=guest_user_id).delete(synchronize_session="fetch")

    # Step 4: Delete the user record itself.
    db.session.delete(user)
    db.session.commit()

    logging.info(
        f"[guest-cleanup] Deleted guest '{username}' (id={guest_user_id}), "
        f"{len(vault_ids)} vault(s), ~{version_count} version(s) reassigned."
    )

    return {
        "deleted_user": username,
        "vault_count": len(vault_ids),
        "version_count": version_count,
    }
