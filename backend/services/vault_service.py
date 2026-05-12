# backend/services/vault_service.py

"""
Service-Schicht für Vault-Operationen.

Enthält:
  - Zugriffsprüfung & CRUD für Vaults
  - Admin-Funktionen: get_all_vaults, grant/revoke vault access
  - Vault-List-Cache (MD5-ETag, stored on User row)
"""

import hashlib
import json

from backend.models import db, Vault, VaultAccess, User, Node, Version


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _verify_vault_access(vault_id: int, user_id: int) -> Vault:
    """
    Verifies that a user has access to a vault.
    Access is granted if the user is the owner OR has a row in the VaultAccess table.
    Returns the Vault object or raises an error.
    """
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")

    if vault.owner_id == user_id:
        return vault

    access_row = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id, user_id=user_id)
    ).scalar_one_or_none()

    if access_row is not None:
        return vault

    raise PermissionError("You do not have permission to access this vault.")


def _build_vault_list(user_id: int) -> list:
    """Raw query — owned + granted vaults, no cache. Returns list of dicts."""
    granted_vault_ids = db.session.execute(
        db.select(VaultAccess.vault_id).filter_by(user_id=user_id)
    ).scalars().all()

    vaults = Vault.query.filter(
        db.or_(
            Vault.owner_id == user_id,
            Vault.id.in_(granted_vault_ids) if granted_vault_ids else False
        )
    ).order_by(Vault.name).all()

    return [v.to_dict() for v in vaults]


def _vault_list_etag(vaults_data: list) -> str:
    """Deterministic MD5 over the id+name pairs."""
    summary = [{"id": v["id"], "name": v["name"]} for v in vaults_data]
    return hashlib.md5(json.dumps(summary, sort_keys=True).encode()).hexdigest()


def _collect_affected_user_ids(vault_id: int) -> set:
    """Owner + all users with a VaultAccess row for this vault."""
    vault = db.session.get(Vault, vault_id)
    ids = {vault.owner_id} if vault else set()
    rows = db.session.execute(
        db.select(VaultAccess.user_id).filter_by(vault_id=vault_id)
    ).scalars().all()
    ids.update(rows)
    return ids


def _invalidate_vault_cache_for_all_affected(vault_id: int) -> None:
    for uid in _collect_affected_user_ids(vault_id):
        invalidate_vault_list_cache(uid)


# ---------------------------------------------------------------------------
# Public: vault list cache
# ---------------------------------------------------------------------------

def invalidate_vault_list_cache(user_id: int) -> None:
    """
    Clears cached vault list for a user.
    Caller must commit after calling this (to allow batching).
    """
    user = db.session.get(User, user_id)
    if user:
        user.cached_vault_list = None
        user.cached_vault_list_etag = None


def get_vaults_for_user_cached(user_id: int, client_etag=None):
    """
    Returns (data_or_None, etag, is_not_modified).

    - Cache miss: rebuilds, stores, returns (data, etag, False).
    - Hit + matching ETag: returns (None, etag, True) → caller sends 304.
    - Hit + different ETag: returns (data, etag, False).
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found.")

    if user.cached_vault_list is None:
        data = _build_vault_list(user_id)
        etag = _vault_list_etag(data)
        user.cached_vault_list = data
        user.cached_vault_list_etag = etag
        db.session.commit()
    else:
        data = user.cached_vault_list
        etag = user.cached_vault_list_etag or _vault_list_etag(data)

    if client_etag and client_etag.strip('"') == etag:
        return None, etag, True

    return data, etag, False


# ---------------------------------------------------------------------------
# Public: basic vault queries
# ---------------------------------------------------------------------------

def get_vault_by_id(vault_id: int, user_id: int) -> Vault:
    return _verify_vault_access(vault_id, user_id)


def get_vaults_for_user(user_id: int) -> list:
    """Legacy (non-cached) helper, kept for internal callers."""
    granted_vault_ids = db.session.execute(
        db.select(VaultAccess.vault_id).filter_by(user_id=user_id)
    ).scalars().all()

    return Vault.query.filter(
        db.or_(
            Vault.owner_id == user_id,
            Vault.id.in_(granted_vault_ids) if granted_vault_ids else False
        )
    ).order_by(Vault.name).all()


# ---------------------------------------------------------------------------
# Public: vault CRUD
# ---------------------------------------------------------------------------

def create_vault(name: str, owner_id: int) -> Vault:
    name_stripped = name.strip()
    if not name_stripped:
        raise ValueError("Vault name cannot be empty.")

    if not db.session.get(User, owner_id):
        raise ValueError(f"Owner with ID {owner_id} not found.")

    if db.session.execute(
        db.select(Vault).filter_by(name=name_stripped, owner_id=owner_id)
    ).first():
        raise ValueError(f"You already own a vault named '{name_stripped}'.")

    try:
        new_vault = Vault(name=name_stripped, owner_id=owner_id)
        db.session.add(new_vault)
        db.session.flush()

        root_node = Node(
            vault_id=new_vault.id,
            parent_id=None,
            current_version=1,
            icon='bxs-folder'
        )
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

        invalidate_vault_list_cache(owner_id)
        db.session.commit()
        return new_vault
    except Exception as e:
        db.session.rollback()
        raise e


def rename_vault(vault_id: int, new_name: str, user_id: int) -> Vault:
    vault = _verify_vault_access(vault_id, user_id)
    new_name_stripped = new_name.strip()
    if not new_name_stripped:
        raise ValueError("New vault name cannot be empty.")

    existing = Vault.query.filter(
        Vault.id != vault_id,
        Vault.name == new_name_stripped,
        Vault.owner_id == user_id
    ).first()
    if existing:
        raise ValueError(f"You already own another vault named '{new_name_stripped}'.")

    vault.name = new_name_stripped
    _invalidate_vault_cache_for_all_affected(vault_id)
    db.session.commit()
    return vault


def delete_vault(vault_id: int, user_id: int):
    vault = _verify_vault_access(vault_id, user_id)
    if Vault.query.filter_by(owner_id=user_id).count() <= 1:
        raise ValueError("You cannot delete your last remaining vault.")

    affected_ids = _collect_affected_user_ids(vault_id)
    db.session.delete(vault)
    db.session.flush()

    for uid in affected_ids:
        invalidate_vault_list_cache(uid)
    db.session.commit()


# ---------------------------------------------------------------------------
# Admin: vault access management
# ---------------------------------------------------------------------------

def get_all_vaults() -> list:
    """[Admin] All vaults with owner info and access count."""
    vaults = Vault.query.order_by(Vault.name).all()
    result = []
    for v in vaults:
        access_count = db.session.execute(
            db.select(db.func.count()).select_from(VaultAccess).filter_by(vault_id=v.id)
        ).scalar()
        owner = db.session.get(User, v.owner_id)
        result.append({
            "id": v.id,
            "name": v.name,
            "created_at": v.created_at.isoformat(),
            "owner_id": v.owner_id,
            "owner_display_name": owner.display_name if owner else "Unknown",
            "owner_username": owner.username if owner else "unknown",
            "access_count": access_count,
        })
    return result


def get_vault_access_list(vault_id: int) -> dict:
    """[Admin] Vault metadata + current access list + available users to grant."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault {vault_id} not found.")

    owner = db.session.get(User, vault.owner_id)

    access_rows = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id)
    ).scalars().all()

    access_user_ids = {row.user_id for row in access_rows}
    access_list = []
    for row in access_rows:
        u = db.session.get(User, row.user_id)
        if u:
            access_list.append({
                "user_id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "user_type": u.user_type,
                "role": row.role,
            })

    excluded_ids = access_user_ids | {vault.owner_id}
    all_users = User.query.filter(User.id.notin_(excluded_ids)).order_by(User.display_name).all()
    available_users = [
        {
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "user_type": u.user_type,
        }
        for u in all_users
    ]

    return {
        "vault": {
            "id": vault.id,
            "name": vault.name,
            "owner_id": vault.owner_id,
            "owner_display_name": owner.display_name if owner else "Unknown",
            "owner_username": owner.username if owner else "unknown",
        },
        "access_list": access_list,
        "available_users": available_users,
    }


def grant_vault_access(vault_id: int, user_id: int, role: str = "editor") -> None:
    """[Admin] Idempotent upsert. Raises if target is the vault owner."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault {vault_id} not found.")
    if vault.owner_id == user_id:
        raise ValueError("Cannot grant explicit access to the vault owner — they already have full access.")
    if not db.session.get(User, user_id):
        raise ValueError(f"User {user_id} not found.")

    existing = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id, user_id=user_id)
    ).scalar_one_or_none()

    if existing:
        existing.role = role
    else:
        db.session.add(VaultAccess(vault_id=vault_id, user_id=user_id, role=role))

    invalidate_vault_list_cache(user_id)
    db.session.commit()


def revoke_vault_access(vault_id: int, user_id: int) -> None:
    """[Admin] Delete the access row. Raises if target is the vault owner."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault {vault_id} not found.")
    if vault.owner_id == user_id:
        raise ValueError("Cannot revoke access from the vault owner.")

    row = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id, user_id=user_id)
    ).scalar_one_or_none()

    if not row:
        raise ValueError(f"User {user_id} does not have explicit access to vault {vault_id}.")

    db.session.delete(row)
    invalidate_vault_list_cache(user_id)
    db.session.commit()
