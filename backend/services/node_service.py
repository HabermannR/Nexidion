# backend/services/node_service.py

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import joinedload, subqueryload, contains_eager, with_parent
from sqlalchemy import case, func, select

# Importiere die Services und Modelle
from .vault_service import _verify_vault_access
from ..models import db, Node, Version


# ========================================================================
# PRIVATE HELPER FUNCTIONS
# ========================================================================

def _is_descendant(ancestor_id: str, descendant_id: str, vault_id: int) -> bool:
    """Prüft, ob ein Node ein Nachkomme eines anderen ist, um Zyklen zu verhindern."""
    if not descendant_id or not ancestor_id:
        return False
    # Rekursive CTE (Common Table Expression) zur Ermittlung aller Vorfahren
    cte = db.session.query(Node.id, Node.parent_id).filter(Node.id == descendant_id, Node.vault_id == vault_id).cte(
        name="ancestors", recursive=True)
    parent_alias, cte_alias = db.aliased(Node), db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id).filter(parent_alias.vault_id == vault_id).join(
            cte_alias, parent_alias.id == cte_alias.c.parent_id))
    # Prüfen, ob der potentielle Vorfahre in der Ahnentafel vorkommt
    return db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar() is not None


def _get_nodes_by_ids_and_verify_access(node_ids: list[str], vault_id: int, user_id: int) -> List[Node]:
    """
    Zentrale, strikte Hilfsfunktion: Holt eine Liste von Nodes anhand ihrer IDs, lädt
    deren aktuelle Versionen und Autoren effizient vor und validiert den Zugriff.

    Löst einen Fehler aus, wenn ein Node nicht gefunden wird oder die Berechtigung fehlt.
    """
    # Schritt 1: Allgemeine Vault-Berechtigung prüfen
    _verify_vault_access(vault_id, user_id)
    if not node_ids:
        return []

    # Schritt 2: Alle angeforderten Nodes und zugehörige Daten effizient laden.
    nodes = (
        Node.query
        .options(
            # Lade die aktuelle Version und dessen Autor mit einem einzigen Join.
            joinedload(Node.current_version_object).joinedload(Version.author)
        )
        .filter(Node.id.in_(node_ids))
        .all()
    )

    # Schritt 3: Strikte "Alles-oder-nichts"-Validierung
    found_nodes_map = {node.id: node for node in nodes}
    requested_ids_set = set(node_ids)

    # Prüfen, ob alle angeforderten IDs überhaupt existieren
    if len(found_nodes_map) != len(requested_ids_set):
        missing_ids = requested_ids_set - found_nodes_map.keys()
        raise ValueError(f"Node(s) with ID(s) not found: {', '.join(missing_ids)}")

    # Prüfen, ob alle existierenden Nodes zum richtigen Vault gehören
    for node in nodes:
        if node.vault_id != vault_id:
            raise PermissionError(f"Permission denied to access node with ID: {node.id}")

    # Schritt 4: Wenn alle Prüfungen bestanden wurden, die Liste der Nodes zurückgeben
    return nodes


# ========================================================================
# READ OPERATIONS
# ========================================================================

def get_nodes_as_tree(vault_id: int, user_id: int, v3_mode: bool = False) -> list[dict]:
    """
    Holt die komplette Node-Hierarchie als Baumstruktur.
    """
    _verify_vault_access(vault_id, user_id)
    root_nodes = (
        Node.query
        .options(
            subqueryload(Node.children).subqueryload(Node.children),
            contains_eager(Node.current_version_object)
        )
        .join(Node.current_version_object, isouter=True)
        .filter(Node.vault_id == vault_id, Node.parent_id.is_(None))
        .order_by(Node.title)
        .all()
    )
    return [node.to_dict(include_children=True, include_content=False) for node in root_nodes]


def get_nodes_as_list(vault_id: int, user_id: int, v3_mode: bool = False) -> list[dict]:
    """Holt alle Nodes als flache Liste."""
    _verify_vault_access(vault_id, user_id)
    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(vault_id=vault_id)
        .order_by(Node.title)
        .all()
    )
    return [node.to_dict(include_content=True) for node in nodes]


def find_node_by_title(title: str, vault_id: int, user_id: int) -> dict | None:
    """Findet den besten Treffer für einen Node-Titel."""
    _verify_vault_access(vault_id, user_id)
    if not title or not title.strip():
        raise ValueError("Search title cannot be empty")
    search_term = f"%{title}%"
    relevance = case((Node.title.ilike(title), 0), else_=1)
    node = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter(Node.vault_id == vault_id, Node.title.ilike(search_term))
        .order_by(relevance, Node.title)
        .first()
    )
    return node.to_dict(include_content=True) if node else None


def get_node_by_id(node_id: str, vault_id: int, user_id: int, v3_mode: bool = False) -> dict | None:
    """Holt einen einzelnen Node nach ID, schnell und ohne Versionsverlauf."""
    _verify_vault_access(vault_id, user_id)
    node = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(id=node_id, vault_id=vault_id)
        .first()
    )
    if not node:
        return None

    node_dict = node.to_dict(include_content=True)
    count_stmt = select(func.count()).select_from(Version).where(with_parent(node, Node.versions))
    version_count = db.session.execute(count_stmt).scalar_one()

    node_dict['has_versions'] = version_count > 1
    node_dict['version_count'] = version_count
    return node_dict


def get_node_versions(node_id: str, vault_id: int, user_id: int) -> list[dict] | None:
    """Holt ausschließlich den Versionsverlauf für einen gegebenen Node."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        return None

    stmt = (
        select(Version)
        .where(with_parent(node, Node.versions))
        .options(joinedload(Version.author))
        .order_by(Version.version.desc())
    )
    versions = db.session.execute(stmt).scalars().all()
    return [v.to_dict(include_content=True) for v in versions]


def get_nodes_by_ids(node_ids: list[str], vault_id: int, user_id: int) -> list[dict]:
    """Holt mehrere Nodes nach IDs und prüft den Zugriff."""
    nodes = _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)
    return [node.to_dict(include_content=True) for node in nodes]


def get_nodes_by_ids_for_user(node_ids: List[str], vault_id: int, user_id: int) -> List[Node]:
    """Holt die vollständigen Node-Objekte für eine Liste von IDs."""
    return _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)


def get_content_for_nodes(node_ids: List[str], vault_id: int, user_id: int) -> Dict[str, Any]:
    """Holt und formatiert Inhalte für mehrere Nodes, nachdem der Zugriff verifiziert wurde."""
    if not node_ids:
        raise ValueError("Es muss mindestens eine Node-ID angegeben werden.")

    nodes = _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)

    if not nodes:
        return {"titles": [], "content": ""}

    nodes_by_id = {node.id: node for node in nodes}
    ordered_titles, ordered_contents = [], []
    for node_id in node_ids:
        if node_id in nodes_by_id:
            node = nodes_by_id[node_id]
            ordered_titles.append(node.title)
            content = node.current_version_object.content if node.current_version_object else ""
            ordered_contents.append(
                f"--- START OF DOCUMENT: {node.title} ---\n{content}\n--- END OF DOCUMENT: {node.title} ---"
            )

    full_content = "\n\n".join(ordered_contents)
    return {"titles": ordered_titles, "content": full_content}


# ========================================================================
# WRITE OPERATIONS
# ========================================================================

def create_node(title: str, content: str, parent_id: str | None, vault_id: int, author_id: int) -> Node:
    """Erstellt einen neuen Node und seine initiale Version."""
    _verify_vault_access(vault_id, author_id)
    if parent_id:
        parent_node = Node.query.filter_by(id=parent_id, vault_id=vault_id).first()
        if not parent_node:
            raise ValueError("Parent node not found in the specified vault.")

    new_node = Node(title=title, parent_id=parent_id, current_version=1, vault_id=vault_id)
    db.session.add(new_node)
    db.session.flush()  # We need the new_node.id for the version

    initial_version = Version(node_id=new_node.id, version=1, content=content, author_id=author_id)
    db.session.add(initial_version)

    db.session.commit()
    return new_node


def update_node(node_id: str, vault_id: int, user_id: int, title: Optional[str] = None,
                content: Optional[str] = None) -> Node:
    """Aktualisiert Titel und/oder Inhalt eines Nodes und erstellt eine neue Version."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).options(joinedload(Node.current_version_object)).first()
    if not node:
        raise ValueError("Node not found in the specified vault")

    current_title = node.title
    current_content = node.current_version_object.content if node.current_version_object else ""
    new_title = title if title is not None else current_title
    new_content = content if content is not None else current_content

    if new_title == current_title and new_content == current_content:
        return node  # Keine Änderung, keine neue Version

    next_version_number = (db.session.query(func.max(Version.version)).filter(
        Version.node_id == node.id).scalar() or 0) + 1
    new_version = Version(node_id=node.id, version=next_version_number, content=new_content, author_id=user_id)
    db.session.add(new_version)

    node.title = new_title
    node.current_version = next_version_number
    db.session.commit()
    db.session.refresh(node)
    return node


def move_node(node_id: str, new_parent_id: str | None, vault_id: int, user_id: int) -> Node:
    """Bewegt einen Node zu einem neuen Parent (keine neue Version)."""
    _verify_vault_access(vault_id, user_id)
    if str(node_id) == str(new_parent_id):
        raise ValueError("Cannot move a node into itself.")
    node_to_move = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_move:
        raise ValueError("Node to move not found in the specified vault.")
    if new_parent_id:
        new_parent = Node.query.filter_by(id=new_parent_id, vault_id=vault_id).first()
        if not new_parent:
            raise ValueError("Target parent node not found in the specified vault.")
        if _is_descendant(node_id, new_parent_id, vault_id):
            raise ValueError("Cannot move a node into one of its own children.")

    node_to_move.parent_id = new_parent_id
    db.session.commit()
    return node_to_move


def update_node_icon(node_id: str, vault_id: int, user_id: int, icon: Optional[str]) -> Node:
    """Aktualisiert das Icon eines Nodes (keine neue Version)."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault.")

    # Setzt das Icon. Wenn der neue Wert `None` oder ein leerer String ist, wird es in der DB als NULL gespeichert.
    node.icon = icon if icon else None

    db.session.commit()
    return node


def delete_node(node_id: str, vault_id: int, user_id: int):
    """Löscht einen Node. Kind-Nodes werden dabei zu Waisen (Top-Level)."""
    _verify_vault_access(vault_id, user_id)
    node_to_delete = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_delete:
        raise ValueError("Node not found in the specified vault")

    # Optional: Verhindere das Löschen von Top-Level-Nodes, um die Baumstruktur zu erhalten.
    # if node_to_delete.parent_id is None:
    #     raise ValueError("Cannot delete a top-level node.")

    # Kind-Nodes zu Top-Level Nodes machen (parent_id auf NULL setzen)
    Node.query.filter_by(parent_id=node_id, vault_id=vault_id).update({"parent_id": None})

    # Den Node selbst löschen. Versionen werden durch 'cascade' automatisch mitgelöscht.
    db.session.delete(node_to_delete)
    db.session.commit()