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

from backend.exceptions import InsufficientVaultRoleError, DemoLockError
from backend.models import db, Vault, VaultAccess, VaultRole, User, Node, Version, DemoState, UserType


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def assert_write_allowed(role: VaultRole, user: User):
    # Support both VaultRole enum and raw int values safely
    role_val = role.value if hasattr(role, 'value') else int(role)
    editor_val = VaultRole.EDITOR.value if hasattr(VaultRole.EDITOR, 'value') else int(VaultRole.EDITOR)
    if role_val < editor_val:
        raise InsufficientVaultRoleError("You have read-only access to this vault.")
    if user.is_guest and user.demo_state == DemoState.READ_ONLY:
        raise DemoLockError("Complete the demo task to unlock editing.")


def get_vault_access(vault_id: int, user_id: int) -> tuple[Vault, VaultRole]:
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")
    if vault.owner_id == user_id:
        return vault, VaultRole.EDITOR
    row = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id, user_id=user_id)
    ).scalar_one_or_none()
    if row:
        return vault, VaultRole(row.role)
    raise PermissionError("You do not have permission to access this vault.")


def _verify_vault_access(vault_id: int, user_id: int) -> Vault:
    vault, _ = get_vault_access(vault_id, user_id)
    return vault


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
        raise ValueError(f"User with ID {user_id} not found.")

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

    user = db.session.get(User, owner_id)
    if not user:
        raise ValueError(f"Owner with ID {owner_id} not found.")

    if user.is_guest:
        limit = 1 if user.demo_state == DemoState.READ_ONLY else 3
        vault_count = Vault.query.filter_by(owner_id=owner_id).count()
        if vault_count >= limit:
            raise DemoLockError(f"Demo accounts are limited to {limit} vault(s).")

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
    vault, role = get_vault_access(vault_id, user_id)
    user = db.session.get(User, user_id)
    assert_write_allowed(role, user)

    if vault.owner_id != user_id:
        raise PermissionError("Only the vault owner can rename it.")
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
    vault, role = get_vault_access(vault_id, user_id)
    user = db.session.get(User, user_id)
    assert_write_allowed(role, user)

    if vault.owner_id != user_id:
        raise PermissionError("Only the vault owner can delete it.")

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
    """[Admin] All vaults with owner info and access count — single query."""
    access_count_subq = (
        db.select(VaultAccess.vault_id, db.func.count().label("cnt"))
        .group_by(VaultAccess.vault_id)
        .subquery()
    )
    rows = (
        db.session.execute(
            db.select(Vault, access_count_subq.c.cnt)
            .outerjoin(access_count_subq, access_count_subq.c.vault_id == Vault.id)
            .order_by(Vault.name)
        ).all()
    )

    result = []
    for v, cnt in rows:
        owner = db.session.get(User, v.owner_id)
        result.append({
            "id": v.id,
            "name": v.name,
            "created_at": v.created_at.isoformat(),
            "owner_id": v.owner_id,
            "owner_display_name": owner.display_name if owner else "Unknown",
            "owner_username": owner.username if owner else "unknown",
            "is_guest_vault": owner.is_guest if owner else False,
            "access_count": cnt or 0,
        })
    return result


def admin_rename_vault(vault_id: int, new_name: str) -> dict:
    """[Admin] Rename any vault without owner check."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("New vault name cannot be empty.")
    collision = Vault.query.filter(
        Vault.id != vault_id,
        Vault.name == new_name,
        Vault.owner_id == vault.owner_id,
    ).first()
    if collision:
        raise ValueError(f"The owner already has a vault named '{new_name}'.")
    vault.name = new_name
    _invalidate_vault_cache_for_all_affected(vault_id)
    db.session.commit()
    owner = db.session.get(User, vault.owner_id)
    return {
        "id": vault.id,
        "name": vault.name,
        "owner_id": vault.owner_id,
        "owner_username": owner.username if owner else "unknown",
        "owner_display_name": owner.display_name if owner else "Unknown",
    }


def admin_delete_vault(vault_id: int):
    """[Admin] Delete any vault without owner/last-vault check."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")
    affected_ids = _collect_affected_user_ids(vault_id)
    db.session.delete(vault)
    db.session.flush()
    for uid in affected_ids:
        invalidate_vault_list_cache(uid)
    db.session.commit()


def get_vault_access_list(vault_id: int) -> dict:
    """[Admin] Vault metadata + current access list + available users to grant."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")

    owner = db.session.get(User, vault.owner_id)

    access_rows = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id)
    ).scalars().all()

    access_user_ids = {row.user_id for row in access_rows}
    access_list = []
    for row in access_rows:
        u = db.session.get(User, row.user_id)
        if u:
            # --- TRANSLATE ENUMS TO STRINGS ---
            try:
                role_str = VaultRole(row.role).name.lower()
            except ValueError:
                role_str = "unknown"

            try:
                type_str = UserType(u.user_type).name.lower()
            except ValueError:
                type_str = "human"

            access_list.append({
                "user_id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "user_type": type_str,
                "role": role_str,
            })

    excluded_ids = access_user_ids | {vault.owner_id}
    all_users = User.query.filter(User.id.notin_(excluded_ids)).order_by(User.display_name).all()

    available_users = []
    for u in all_users:
        # --- TRANSLATE ENUMS TO STRINGS FOR DROPDOWN ---
        try:
            type_str = UserType(u.user_type).name.lower()
        except ValueError:
            type_str = "human"

        available_users.append({
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "user_type": type_str,
        })

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


def grant_vault_access(vault_id: int, user_id: int, role: int = VaultRole.EDITOR.value) -> None:
    """[Admin] Idempotent upsert. Raises if target is the vault owner."""
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")
    if vault.owner_id == user_id:
        raise ValueError("Cannot grant explicit access to the vault owner — they already have full access.")
    if not db.session.get(User, user_id):
        raise ValueError(f"User with ID {user_id} not found.")

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
        raise ValueError(f"Vault with ID {vault_id} not found.")
    if vault.owner_id == user_id:
        raise ValueError("Cannot revoke access from the vault owner.")

    row = db.session.execute(
        db.select(VaultAccess).filter_by(vault_id=vault_id, user_id=user_id)
    ).scalar_one_or_none()

    if not row:
        raise ValueError(f"User with ID {user_id} does not have explicit access to vault {vault_id}.")

    db.session.delete(row)
    invalidate_vault_list_cache(user_id)
    db.session.commit()