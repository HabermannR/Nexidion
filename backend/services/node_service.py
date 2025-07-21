# backend/services/node_service.py

from typing import List, Dict, Any
from sqlalchemy.orm import joinedload, selectinload, subqueryload, contains_eager
from sqlalchemy import case, func
from .vault_service import _verify_vault_access
from ..models import db, Node, Version

def _is_descendant(ancestor_id: str, descendant_id: str, vault_id: int) -> bool:
    """Prüft, ob ein Node ein Nachkomme eines anderen ist, um Zyklen zu verhindern."""
    if not descendant_id or not ancestor_id: return False
    cte = db.session.query(Node.id, Node.parent_id).filter(Node.id == descendant_id, Node.vault_id == vault_id).cte(
        name="ancestors", recursive=True)
    parent_alias, cte_alias = db.aliased(Node), db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id).filter(parent_alias.vault_id == vault_id).join(
            cte_alias, parent_alias.id == cte_alias.c.parent_id))
    return db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar() is not None


def _get_nodes_with_content(node_ids: list[str], vault_id: int, user_id: int) -> list[Node]:
    """
    Strikte Hilfsfunktion: Holt Nodes und validiert den Besitz.
    Löst einen Fehler aus, wenn ein Node nicht gefunden wird oder die Berechtigung fehlt.
    """
    # Schritt 1: Allgemeine Vault-Berechtigung prüfen
    _verify_vault_access(vault_id, user_id)
    if not node_ids:
        return []

    # Schritt 2: Alle angeforderten Nodes aus der DB holen, *ohne* nach dem Vault zu filtern.
    # Dies ist entscheidend, um zwischen "nicht gefunden" und "keine Berechtigung" unterscheiden zu können.
    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter(Node.id.in_(node_ids))
        .all()
    )

    # Schritt 3: Strikte "Alles-oder-nichts"-Validierung
    found_nodes_map = {node.id: node for node in nodes}
    requested_ids_set = set(node_ids)

    # Prüfen, ob alle angeforderten IDs überhaupt existieren
    if len(found_nodes_map) != len(requested_ids_set):
        missing_ids = requested_ids_set - found_nodes_map.keys()
        # Dieser Fehler wird vom Controller als 404 (oder 400) behandelt
        raise ValueError(f"Node(s) with ID(s) not found: {', '.join(map(str, missing_ids))}")

    # Prüfen, ob alle existierenden Nodes zum richtigen Vault gehören
    for node in nodes:
        if node.vault_id != vault_id:
            # Dieser Fehler wird vom Controller als 403 behandelt
            raise PermissionError(f"Permission denied to access node with ID: {node.id}")

    # Schritt 4: Wenn alle Prüfungen bestanden wurden, die Liste der Nodes zurückgeben
    return nodes

def get_nodes_as_tree(vault_id: int, user_id: int) -> list[dict]:
    """
    Holt die komplette Node-Hierarchie als Baumstruktur, indem die rekursive
    Logik des Node-Modells genutzt wird.
    """
    if True:
        _verify_vault_access(vault_id, user_id)

        # 1. Finde nur die Wurzel-Nodes (die keinen Parent haben).
        # options(subqueryload(...)) kann helfen, N+1-Query-Probleme zu vermeiden.
        root_nodes = (
            Node.query
            .options(
                # Lade die Kind-Beziehungen über alle Ebenen aggressiv vor
                subqueryload(Node.children).subqueryload(Node.children),
                # Lade auch das zugehörige Version-Objekt für jeden Node vor.
                # contains_eager ist hier oft effizienter als subqueryload für eine 1-zu-1-Beziehung.
                contains_eager(Node.current_version_object)
            )
            # Wir brauchen einen expliziten JOIN, damit contains_eager weiß, was es tun soll.
            .join(Node.current_version_object, isouter=True)
            .filter(Node.vault_id == vault_id, Node.parent_id == None)
            .order_by(Node.title)
            .all()
        )

        # 2. Rufe die rekursive to_dict-Methode für jeden Wurzel-Node auf.
        # Der `include_content=False` im rekursiven Aufruf sorgt für die Performance.
        tree = [node.to_dict(include_children=True, include_content=False) for node in root_nodes]

        return tree
    else:
        spoofed_tree = [
            {
                'id': 'root-node-1',
                'title': 'Hauptthema 1',
                'parent_id': None,
                'current_version': 2,
                'vault_id': vault_id,
                'children': [
                    {
                        'id': 'child-node-1-1',
                        'title': 'Unterthema 1.1',
                        'parent_id': 'root-node-1',
                        'current_version': 1,
                        'vault_id': vault_id,
                        'children': []
                    },
                    {
                        'id': 'child-node-1-2',
                        'title': 'Unterthema 1.2 mit weiteren Details',
                        'parent_id': 'root-node-1',
                        'current_version': 4,
                        'vault_id': vault_id,
                        'children': [
                            {
                                'id': 'grandchild-node-1-2-1',
                                'title': 'Detail A',
                                'parent_id': 'child-node-1-2',
                                'current_version': 1,
                                'vault_id': vault_id,
                                'children': []
                            },
                            {
                                'id': 'grandchild-node-1-2-2',
                                'title': 'Detail B',
                                'parent_id': 'child-node-1-2',
                                'current_version': 1,
                                'vault_id': vault_id,
                                'children': []
                            }
                        ]
                    }
                ]
            },
            {
                'id': 'root-node-2',
                'title': 'Hauptthema 2 (ohne Kinder)',
                'parent_id': None,
                'current_version': 1,
                'vault_id': vault_id,
                'children': []
            },
            {
                'id': 'root-node-3',
                'title': 'Ein weiteres Hauptthema',
                'parent_id': None,
                'current_version': 5,
                'vault_id': vault_id,
                'children': [
                    {
                        'id': 'child-node-3-1',
                        'title': 'Nur ein Kind',
                        'parent_id': 'root-node-3',
                        'current_version': 1,
                        'vault_id': vault_id,
                        'children': []
                    }
                ]
            }
        ]

        return spoofed_tree


def get_nodes_as_list(vault_id: int, user_id: int) -> list[dict]:
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


def get_node_by_id(node_id: str, vault_id: int, user_id: int) -> dict | None:
    """
    Holt einen einzelnen Node nach ID - OHNE seinen Versionsverlauf (schnell).
    """
    _verify_vault_access(vault_id, user_id)

    # Die Abfrage wird "leichter", indem wir `selectinload(Node.versions)` entfernen.
    # Wir laden nur noch die *aktuelle* Version, um den Inhalt zu bekommen.
    node = (
        Node.query
        .options(
            joinedload(Node.current_version_object)  # Beibehalten, um den Inhalt zu bekommen
        )
        .filter_by(id=node_id, vault_id=vault_id)
        .first()
    )

    if not node:
        return None

    # Die to_dict() Methode sollte jetzt auch keine Versionen mehr serialisieren.
    # Du hattest es bereits auskommentiert, was perfekt ist.
    node_dict = node.to_dict(include_content=True)

    # Optional, aber SEHR empfohlen: Füge Metadaten für das Frontend hinzu.
    # Dies erfordert eine zusätzliche, aber sehr schnelle Zählabfrage.
    version_count = Version.query.with_parent(node).count()
    node_dict['has_versions'] = version_count > 1  # Wahr, wenn mehr als die initiale Version existiert
    node_dict['version_count'] = version_count

    return node_dict


def get_node_versions(node_id: str, vault_id: int, user_id: int) -> list[dict] | None:
    """
    Holt ausschließlich den Versionsverlauf für einen gegebenen Node.
    """
    _verify_vault_access(vault_id, user_id)

    # Zuerst prüfen, ob der Node überhaupt existiert und zum Vault gehört.
    # Das ist eine wichtige Sicherheits- und Integritätsprüfung.
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        # Wenn der Node nicht existiert, geben wir None zurück (oder werfen einen Fehler).
        # Das Frontend kann damit umgehen (z.B. 404 Not Found).
        return None

    # Jetzt laden wir die Versionen, die zu diesem Node gehören.
    # Wir laden auch den Autor mit, um anzuzeigen, wer die Änderung gemacht hat.
    versions = (
        Version.query
        .with_parent(node)
        .options(joinedload(Version.author))
        .order_by(Version.version.desc())  # Neueste Versionen zuerst
        .all()
    )

    # Serialisiere jede Version in ein Dictionary.
    versions_list = [v.to_dict(include_content=True) for v in versions]

    return versions_list

# === WRITE OPERATIONS ===

def create_node(title: str, content: str, parent_id: str | None, vault_id: int, author_id: int) -> Node:
    """Erstellt einen neuen Node und seine initiale Version."""
    _verify_vault_access(vault_id, author_id)
    if parent_id:
        parent_node = Node.query.filter_by(id=parent_id, vault_id=vault_id).first()
        if not parent_node: raise ValueError("Parent node not found in the specified vault.")

    new_node = Node(title=title, parent_id=parent_id, current_version=1, vault_id=vault_id)
    db.session.add(new_node)
    db.session.flush()

    initial_version = Version(node_id=new_node.id, version=1, content=content, author_id=author_id)
    db.session.add(initial_version)

    db.session.commit()
    return new_node


def update_node(node_id: str, vault_id: int, user_id: int, title: str | None = None,
                content: str | None = None) -> Node:
    """Aktualisiert Titel und/oder Inhalt eines Nodes und erstellt eine neue Version."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).options(joinedload(Node.current_version_object)).first()
    if not node: raise ValueError("Node not found in the specified vault")

    current_title = node.title
    current_content = node.current_version_object.content if node.current_version_object else ""

    # Nimm neue Werte, wenn sie gegeben sind, sonst behalte die alten
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
    db.session.refresh(node)  # Lade den Node neu, um die neue Version zu reflektieren
    return node


def move_node(node_id: str, new_parent_id: str | None, vault_id: int, user_id: int) -> Node:
    """Bewegt einen Node zu einem neuen Parent."""
    _verify_vault_access(vault_id, user_id)
    if str(node_id) == str(new_parent_id): raise ValueError("Cannot move a node into itself.")
    node_to_move = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_move: raise ValueError("Node to move not found in the specified vault.")
    if new_parent_id:
        new_parent = Node.query.filter_by(id=new_parent_id, vault_id=vault_id).first()
        if not new_parent: raise ValueError("Target parent node not found in the specified vault.")
        if _is_descendant(node_id, new_parent_id, vault_id):
            raise ValueError("Cannot move a node into one of its own children.")

    node_to_move.parent_id = new_parent_id
    db.session.commit()
    return node_to_move


def delete_node(node_id: str, vault_id: int, user_id: int):
    """Löscht einen Node. Kind-Nodes werden dabei zu Waisen (Top-Level)."""
    _verify_vault_access(vault_id, user_id)
    node_to_delete = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_delete: raise ValueError("Node not found in the specified vault")
    if node_to_delete.parent_id is None: raise ValueError("Cannot delete the root node.")

    # Optional: Kind-Nodes zu Top-Level Nodes machen
    Node.query.filter_by(parent_id=node_id, vault_id=vault_id).update({"parent_id": None})

    db.session.delete(node_to_delete)
    db.session.commit()

def get_nodes_by_ids(node_ids: list[str], vault_id: int, user_id: int) -> list[dict]:
    """Holt mehrere Nodes nach IDs und prüft den Zugriff."""
    nodes = _get_nodes_with_content(node_ids, vault_id, user_id)
    return [node.to_dict(include_content=True) for node in nodes]

def get_content_for_nodes(node_ids: List[str], vault_id: int, user_id: int) -> Dict[str, Any]:
    if not node_ids:
        raise ValueError("Es muss mindestens eine Node-ID angegeben werden.")

    """Holt Inhalte für mehrere Nodes, nachdem der Zugriff verifiziert wurde."""
    nodes = _get_nodes_with_content(node_ids, vault_id, user_id)

    if not nodes:
        return {"titles": [], "content": ""}

    # Nodes in der ursprünglichen Reihenfolge der IDs sortieren
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

def get_nodes_by_ids_for_user(node_ids: List[str], vault_id: int, user_id: int) -> List[Node]:
    """
    Holt die vollständigen Node-Objekte für eine Liste von IDs und stellt sicher,
    dass alle angeforderten Nodes existieren und für den Benutzer zugänglich sind.
    Die aktuellen Versionen werden dabei effizient mitgeladen (eagerly loaded).

    Löst einen Fehler aus, wenn ein Node nicht gefunden wird oder die Berechtigung fehlt.

    Args:
        node_ids: Eine Liste von UUIDs (als Strings) der Nodes.
        vault_id: Die ID des Vaults, in dem die Nodes sein müssen.
        user_id: Die ID des anfragenden Benutzers zur Berechtigungsprüfung.

    Returns:
        Eine Liste der `Node`-Objekte, wenn alle Prüfungen erfolgreich sind.

    Raises:
        PermissionError: Wenn ein angeforderter Node nicht zum angegebenen Vault gehört.
        ValueError: Wenn ein angeforderter Node nicht in der Datenbank existiert.
    """
    # Schritt 1: Allgemeine Vault-Zugriffsberechtigung prüfen
    _verify_vault_access(vault_id, user_id)

    if not node_ids:
        return []

    # Schritt 2: Alle angeforderten Nodes aus der DB holen, inklusive des aktuellen
    # Version-Objekts. Dies ist der gleiche effiziente Query wie zuvor.
    nodes = (
        Node.query
        .options(
            # WICHTIG: Wir laden hier auch den Autor der Version mit, um N+1-Queries zu vermeiden.
            joinedload(Node.current_version_object).joinedload(Version.author)
        )
        .filter(Node.id.in_(node_ids))
        .all()
    )

    # Schritt 3: Überprüfen, ob alle angeforderten Nodes gefunden wurden und die Berechtigungen stimmen.
    found_nodes_map = {node.id: node for node in nodes}
    requested_ids_set = set(node_ids)

    if len(found_nodes_map) != len(requested_ids_set):
        missing_ids = requested_ids_set - found_nodes_map.keys()
        raise ValueError(f"Node(s) with ID(s) not found: {', '.join(missing_ids)}")

    for node in nodes:
        if node.vault_id != vault_id:
            raise PermissionError(f"Permission denied to access node with ID: {node.id}")

    # Schritt 4: Die vollständigen Node-Objekte zurückgeben.
    # Der Controller wird die Serialisierung übernehmen.
    return nodes
