# backend/services/vault_service.py

"""
Service-Schicht für Vault-Operationen.

Diese Schicht enthält die Geschäftslogik für die Verwaltung von Vaults.
Sie wird von der API-Schicht (Blueprints) aufgerufen und interagiert
direkt mit den Datenbank-Models.
"""
from backend.models import db, Vault, User, Node, Version


# Diese Helper-Funktion ist perfekt für die Service-Schicht.
def _verify_vault_access(vault_id: int, user_id: int) -> Vault:
    """
    Überprüft, ob ein Benutzer Zugriff auf einen Vault hat.
    Gibt das Vault-Objekt zurück oder wirft einen Fehler.
    """
    vault = db.session.get(Vault, vault_id)
    if not vault:
        # Fehler für die API-Schicht, um einen 404 zu erzeugen
        raise ValueError(f"Vault with ID {vault_id} not found.")
    if vault.owner_id != user_id:
        # Fehler für die API-Schicht, um einen 403 zu erzeugen
        raise PermissionError("You do not have permission to access this vault.")
    return vault


def get_vaults_for_user(user_id: int) -> list[Vault]:
    """Ruft alle Vaults ab, die einem bestimmten Benutzer gehören."""
    return Vault.query.filter_by(owner_id=user_id).order_by(Vault.name).all()


def create_vault(name: str, owner_id: int) -> Vault:
    """
    Erstellt einen neuen Vault mit einem Root-Node für einen Besitzer.
    Wirft Fehler bei Duplikaten oder ungültigen Daten.
    """
    # === UNTERSCHIED 1: explizite Validierung am Anfang ===
    name_stripped = name.strip()
    if not name_stripped:
        raise ValueError("Vault name cannot be empty.")

    # === UNTERSCHIED 2: explizite Prüfung, ob der Besitzer existiert ===
    if not db.session.get(User, owner_id):
        raise ValueError(f"Owner with ID {owner_id} not found.")

    # === UNTERSCHIED 3: explizite Prüfung auf Duplikate FÜR DIESEN USER ===
    if db.session.execute(db.select(Vault).filter_by(name=name_stripped, owner_id=owner_id)).first():
        raise ValueError(f"You already own a vault named '{name_stripped}'.")

    # === UNTERSCHIED 4: Robuster Transaktions-Block ===
    try:
        # Die eigentliche Logik zum Erstellen
        new_vault = Vault(name=name_stripped, owner_id=owner_id)
        db.session.add(new_vault)
        db.session.flush()

        root_node = Node(vault_id=new_vault.id, parent_id=None, current_version=1)
        db.session.add(root_node)
        db.session.flush()

        initial_version = Version(
            node_id=root_node.id,
            version=1,
            title="Summary",
            content=f"This is the root node for the '{name_stripped}' vault.",
            author_id=owner_id
        )
        db.session.add(initial_version)

        db.session.commit()
        return new_vault
    except Exception as e:
        db.session.rollback() # Stellt sicher, dass die DB bei Fehlern sauber bleibt
        raise e # Gibt den Fehler weiter


def rename_vault(vault_id: int, new_name: str, user_id: int) -> Vault:
    """Benennt einen Vault um, nachdem der Besitz überprüft wurde."""
    vault = _verify_vault_access(vault_id, user_id)
    new_name_stripped = new_name.strip()
    if not new_name_stripped:
        raise ValueError("New vault name cannot be empty.")

    # Prüfe, ob der Benutzer bereits einen anderen Vault mit diesem Namen hat
    existing = Vault.query.filter(
        Vault.id != vault_id,
        Vault.name == new_name_stripped,
        Vault.owner_id == user_id
    ).first()
    if existing:
        raise ValueError(f"You already own another vault named '{new_name_stripped}'.")  # Führt zu 409 Conflict

    vault.name = new_name_stripped
    db.session.commit()
    return vault


def delete_vault(vault_id: int, user_id: int):
    """Löscht einen Vault, nachdem der Besitz überprüft wurde."""
    vault = _verify_vault_access(vault_id, user_id)
    if Vault.query.filter_by(owner_id=user_id).count() <= 1:
        raise ValueError("You cannot delete your last remaining vault.")  # Führt zu 400 Bad Request

    # Die eigentliche Löschoperation
    db.session.delete(vault)
    db.session.commit()