"""
Service-Schicht für die Benutzerverwaltung.

Diese Schicht implementiert die Geschäftslogik für Operationen, die typischerweise
von einem Administrator ausgeführt werden, wie das Erstellen, Auflisten, Löschen
und Verwalten von Benutzern. Sie interagiert direkt mit dem User-Model.
"""

from backend.models import db, User


def get_all_users() -> list[User]:
    """
    Ruft eine Liste aller Benutzer aus der Datenbank ab.
    Die Benutzer werden alphabetisch nach ihrem Benutzernamen sortiert.
    """
    return User.query.filter_by(user_type='human').order_by(User.username).all()


def create_user(username: str, password: str, display_name: str | None = None, is_admin: bool = False) -> User:
    """
    Erstellt einen neuen Benutzer im System.

    Args:
        username: Der eindeutige Benutzername für den Login.
        password: Das initiale Passwort des Benutzers.
        display_name: Der Anzeigename. Wenn nicht angegeben, wird der Username verwendet.
        is_admin: Legt fest, ob der Benutzer Administratorrechte hat.

    Returns:
        Das neu erstellte User-Objekt.

    Raises:
        ValueError: Wenn der Benutzername leer ist, bereits existiert oder das Passwort
                    die Sicherheitsanforderungen nicht erfüllt.
    """
    # --- Validierung ---
    stripped_username = username.strip()
    if not stripped_username:
        raise ValueError("Username cannot be empty.")

    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    if User.query.filter_by(username=stripped_username).first():
        raise ValueError(f"Username '{stripped_username}' already exists.")  # Führt zu 409 Conflict

    # --- Erstellung ---
    new_user = User(
        username=stripped_username,
        display_name=display_name.strip() if display_name else stripped_username,
        is_admin=is_admin,
        user_type='human'  # Admin-Panel erstellt nur menschliche Benutzer
    )
    new_user.set_password(password)  # Hash-Generierung im Model gekapselt

    db.session.add(new_user)
    db.session.commit()

    return new_user


def delete_user(user_id_to_delete: int, acting_user_id: int):
    """
    Löscht einen Benutzer aus dem System mit wichtigen Sicherheitsprüfungen.

    Args:
        user_id_to_delete: Die ID des zu löschenden Benutzers.
        acting_user_id: Die ID des Admins, der die Aktion ausführt.

    Raises:
        ValueError: Wenn der zu löschende Benutzer nicht gefunden wird.
        PermissionError: Wenn versucht wird, sich selbst oder den letzten Admin zu löschen.
    """
    # Sicherheitsprüfung 1: Ein Admin kann sich nicht selbst löschen.
    if user_id_to_delete == acting_user_id:
        raise PermissionError("You cannot delete your own account.")

    user_to_delete = db.session.get(User, user_id_to_delete)
    if not user_to_delete:
        raise ValueError(f"User with ID {user_id_to_delete} not found.")

    # Sicherheitsprüfung 2: Der letzte verbleibende Administrator kann nicht gelöscht werden.
    if user_to_delete.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            raise PermissionError("Cannot delete the last remaining administrator.")

    db.session.delete(user_to_delete)
    db.session.commit()


def set_user_password(user_id: int, new_password: str) -> bool:
    """
    Setzt das Passwort für einen bestimmten Benutzer (Admin-Aktion).
    Diese Funktion benötigt im Gegensatz zu `change_password` nicht das alte Passwort.

    Args:
        user_id: Die ID des Benutzers, dessen Passwort geändert wird.
        new_password: Das neue, unverschlüsselte Passwort.

    Returns:
        True bei Erfolg.

    Raises:
        ValueError: Wenn der Benutzer nicht gefunden wird oder das neue Passwort
                    die Sicherheitsanforderungen nicht erfüllt.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    if not new_password or len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters long.")

    # Die Funktion ist nur für menschliche Benutzer sinnvoll.
    if user.user_type != 'human':
        raise ValueError("Cannot set a password for a non-human user account.")

    user.set_password(new_password)
    db.session.commit()
    return True


def update_user_details(user_id: int, updates: dict) -> User:
    """
    Aktualisiert bestimmte Felder eines Benutzers.
    Schützt kritische Felder vor der Änderung.

    Args:
        user_id: Die ID des zu aktualisierenden Benutzers.
        updates: Ein Dictionary mit den zu ändernden Feldern, z.B. {'is_admin': True}.

    Returns:
        Das aktualisierte User-Objekt.

    Raises:
        ValueError: Wenn der Benutzer nicht gefunden wird oder ein ungültiges Feld
                    aktualisiert werden soll.
        PermissionError: Wenn der letzte Admin versucht, sich selbst die Adminrechte
                         zu entziehen.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    # Whitelist der Felder, die ein Admin ändern darf.
    allowed_fields = {'username', 'display_name', 'is_admin'}

    for field, value in updates.items():
        if field not in allowed_fields:
            raise ValueError(f"Field '{field}' cannot be updated.")

        # Sicherheitsprüfung für Admin-Status-Änderung
        if field == 'is_admin' and user.is_admin and not value:
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count <= 1:
                raise PermissionError("Cannot remove admin status from the last administrator.")

        # Prüfung auf Duplikate bei Namensänderung
        if field == 'username':
            stripped_value = value.strip()
            if not stripped_value:
                raise ValueError("Username cannot be empty.")

            existing_user = User.query.filter(User.username == stripped_value, User.id != user_id).first()
            if existing_user:
                raise ValueError(f"Username '{stripped_value}' is already taken.")

            setattr(user, field, stripped_value)
        else:
            setattr(user, field, value)

    db.session.commit()
    return user