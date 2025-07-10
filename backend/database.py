# database.py (Final Version)

"""
The data access layer for the application, powered by Flask-SQLAlchemy.

This module provides functions to query and manipulate the database using the
ORM (Object-Relational Mapper), offering a secure and maintainable way to
interact with the Vault, Node, and Version models. All data access is
scoped to a specific vault_id and authenticated user to ensure data isolation.
"""

from sqlalchemy import case, func
from sqlalchemy.orm import joinedload, selectinload

from backend.models import db, Vault, Node, Version, ChatSession, ChatMessage, User


def init_db():
    """
    Initializes the database schema. If no vaults exist, it attempts to create
    a default vault owned by the first administrative user found.
    """
    print("Creating database tables if they don't exist...")
    db.create_all()

    if Vault.query.first() is None:
        print("No vaults found. Attempting to create a default 'Main' vault.")
        default_owner = User.query.filter_by(is_admin=True).order_by(User.id).first()
        if default_owner:
            try:
                # Wir rufen die Funktion mit dem Besitzer auf
                create_vault_with_root_node(name="Main", owner_id=default_owner.id)
                print(f"Default 'Main' vault created successfully for user '{default_owner.username}'.")
            except Exception as e:
                print(f"Error creating the default vault: {e}")
        else:
            print("Could not create default vault: No admin user found in the database.")
    else:
        print("Database already contains vaults. Skipping default creation.")


# ==============================================================================
# HELPER FUNCTION FOR AUTHORIZATION
# ==============================================================================

def _verify_vault_access(vault_id: int, user_id: int) -> Vault:
    """
    Helper-Funktion, um den Zugriff auf einen Vault zu überprüfen.
    Gibt den Vault zurück, wenn der Zugriff erlaubt ist, andernfalls wird ein Fehler ausgelöst.
    """
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")
    if vault.owner_id != user_id:
        raise PermissionError("You do not have permission to access this vault.")
    return vault

# ==============================================================================
# VAULT-RELATED FUNCTIONS
# ==============================================================================

def get_vaults_for_user(user_id: int) -> list[Vault]:
    """Ruft nur die Vaults ab, die einem bestimmten Benutzer gehören."""
    return Vault.query.filter_by(owner_id=user_id).order_by(Vault.name).all()


def create_vault_with_root_node(name: str, owner_id: int) -> Vault:
    """
    Erstellt einen neuen Vault und weist ihn einem Besitzer zu.
    Dies geschieht in einer einzigen Transaktion.
    """
    name_stripped = name.strip()
    if not name_stripped:
        raise ValueError("Vault name cannot be empty.")

    if db.session.execute(db.select(Vault).filter_by(name=name_stripped, owner_id=owner_id)).first():
        raise ValueError(f"You already own a vault named '{name_stripped}'.")

    # Sicherstellen, dass der Besitzer existiert
    if not db.session.get(User, owner_id):
        raise ValueError(f"Owner with ID {owner_id} not found.")

    try:
        # Erstelle den Vault
        new_vault = Vault(name=name_stripped, owner_id=owner_id)
        db.session.add(new_vault)
        db.session.flush()  # Flush, um die new_vault.id zu bekommen

        # Erstelle den Root-Node direkt hier, um die Transaktion zu kontrollieren
        root_node = Node(title="Summary", vault_id=new_vault.id, parent_id=None, current_version=1)
        db.session.add(root_node)
        db.session.flush()  # Flush, um die root_node.id zu bekommen

        # Erstelle die initiale Version für den Root-Node
        initial_version = Version(
            node_id=root_node.id,
            version=1,
            content=f"This is the root node for the '{name_stripped}' vault.",
            author_id=owner_id  # Der Besitzer des Vaults ist der Autor
        )
        db.session.add(initial_version)

        # Führe die gesamte Transaktion aus
        db.session.commit()
        return new_vault
    except Exception as e:
        db.session.rollback()
        raise e


def rename_vault(vault_id: int, new_name: str, user_id: int) -> Vault:
    """Benennt einen Vault um, nachdem der Besitz überprüft wurde."""
    vault = _verify_vault_access(vault_id, user_id)
    new_name_stripped = new_name.strip()
    if not new_name_stripped:
        raise ValueError("New vault name cannot be empty.")
    existing = Vault.query.filter(Vault.id != vault_id, Vault.name == new_name_stripped,
                                  Vault.owner_id == user_id).first()
    if existing:
        raise ValueError(f"You already own another vault named '{new_name_stripped}'.")
    vault.name = new_name_stripped
    db.session.commit()
    return vault


def delete_vault(vault_id: int, user_id: int):
    """Löscht einen Vault, nachdem der Besitz überprüft wurde."""
    vault = _verify_vault_access(vault_id, user_id)
    if Vault.query.filter_by(owner_id=user_id).count() <= 1:
        raise ValueError("You cannot delete your last remaining vault.")
    db.session.delete(vault)
    db.session.commit()


# ==============================================================================
# NODE-RELATED FUNCTIONS
# ==============================================================================

def get_all_nodes_as_tree(vault_id: int, user_id: int) -> list[dict]:  # Hinzufügen: user_id
    """
    Holt die komplette Node-Hierarchie für einen Vault als Baumstruktur.
    Prüft vorher, ob der angegebene Benutzer Zugriff auf den Vault hat.
    """
    # === KORREKTUR: Die Berechtigungsprüfung hinzufügen ===
    _verify_vault_access(vault_id, user_id)
    # =======================================================

    # Der Rest der Funktion kann gleich bleiben
    all_nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(vault_id=vault_id)
        .order_by(Node.title)
        .all()
    )
    nodes_map = {node.id: node.to_dict(include_content=False) for node in all_nodes}
    tree = []
    for node_id, node_dict in nodes_map.items():
        parent_id = node_dict.get('parent_id')
        if parent_id in nodes_map:
            parent = nodes_map[parent_id]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(node_dict)
        else:
            tree.append(node_dict)

    def sort_children_recursively(nodes):
        for node in nodes:
            if 'children' in node:
                node['children'] = sorted(node['children'], key=lambda x: x['title'])
                sort_children_recursively(node['children'])

    sort_children_recursively(tree)
    return tree


def get_all_nodes_as_list(vault_id: int, user_id: int) -> list[dict]:
    """Holt alle Nodes als flache Liste, nachdem der Zugriff verifiziert wurde."""
    _verify_vault_access(vault_id, user_id)
    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(vault_id=vault_id)
        .order_by(Node.title)
        .all()
    )
    return [node.to_dict(include_content=True) for node in nodes]


def get_node_by_title(title: str, vault_id: int, user_id: int) -> dict | None:
    """Findet den relevantesten Node nach Titel, nachdem der Zugriff verifiziert wurde."""
    _verify_vault_access(vault_id, user_id)
    if not title:
        return None
    search_term = f"%{title}%"
    relevance = case((Node.title.ilike(title), 0), else_=1)
    node = (
        Node.query
        .options(joinedload(Node.current_version_object))  # Effizienz-Bonus
        .filter(Node.vault_id == vault_id, Node.title.ilike(search_term))
        .order_by(relevance, Node.title)
        .first()
    )
    if not node:
        return None
    return node.to_dict(include_content=True)


def get_node_by_id(node_id: str, vault_id: int, user_id: int) -> dict | None:
    """Holt einen Node nach ID, nachdem der Zugriff verifiziert wurde."""
    _verify_vault_access(vault_id, user_id)
    node = (
        Node.query
        .options(
            joinedload(Node.current_version_object),
            selectinload(Node.versions).joinedload(Version.author)
        )
        .filter_by(id=node_id, vault_id=vault_id)
        .first()
    )
    if not node:
        return None
    node_dict = node.to_dict(include_content=True)
    versions_list = [
        {
            'version': v.version,
            'content': v.content,
            'timestamp': v.timestamp.isoformat(),
            'author': v.author.display_name if v.author else "Unknown"
        }
        for v in node.versions
    ]
    node_dict['versions'] = sorted(versions_list, key=lambda v: v['version'], reverse=True)
    return node_dict


def _get_nodes_with_content(node_ids: list[str], vault_id: int, user_id: int) -> list[Node]:
    """Interne Hilfsfunktion zum Holen der Nodes."""
    _verify_vault_access(vault_id, user_id)
    if not node_ids:
        return []

    return (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter(Node.id.in_(node_ids), Node.vault_id == vault_id)
        .all()
    )


def get_nodes_by_ids(node_ids: list[str], vault_id: int, user_id: int) -> list[dict]:
    """Holt mehrere Nodes nach IDs und prüft den Zugriff."""
    nodes = _get_nodes_with_content(node_ids, vault_id, user_id)
    return [node.to_dict(include_content=True) for node in nodes]


def get_content_for_nodes(node_ids: list[str], vault_id: int, user_id: int) -> dict:
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


def create_node(title: str, content: str, parent_id: str | None, vault_id: int, author_id: int) -> Node:
    """
    Erstellt einen neuen Node und seine initiale Version. Prüft den Zugriff und führt einen Commit aus.
    """
    _verify_vault_access(vault_id, author_id)
    if parent_id:
        parent_node = Node.query.filter_by(id=parent_id, vault_id=vault_id).first()
        if not parent_node:
            raise ValueError("Parent node not found in the specified vault.")

    new_node = Node(title=title, parent_id=parent_id, current_version=1, vault_id=vault_id)
    db.session.add(new_node)
    db.session.flush()

    initial_version = Version(node_id=new_node.id, version=1, content=content, author_id=author_id)
    db.session.add(initial_version)

    # ## KORRIGIERT ##: Der Commit ist hier notwendig, da die Funktion direkt von der API aufgerufen wird.
    db.session.commit()
    return new_node


def update_node(node_id: str, vault_id: int, user_id: int, **kwargs) -> Node:
    """Aktualisiert einen Node, prüft den Zugriff und setzt den Autor der neuen Version."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).options(joinedload(Node.current_version_object)).first()
    if not node:
        raise ValueError("Node not found in the specified vault")

    current_title = node.title
    current_content = node.current_version_object.content if node.current_version_object else ""
    new_title = kwargs.get('title', current_title)
    new_content = kwargs.get('content', current_content)

    if new_title == current_title and new_content == current_content:
        return node

    next_version_number = (db.session.query(func.max(Version.version)).filter(
        Version.node_id == node.id).scalar() or 0) + 1
    new_version = Version(node_id=node.id, version=next_version_number, content=new_content, author_id=user_id)
    db.session.add(new_version)

    node.title = new_title
    node.current_version = next_version_number
    db.session.commit()
    db.session.refresh(node)
    return node


def rename_node(node_id: str, new_title: str, vault_id: int, user_id: int) -> dict:
    """Benennt einen Node um und prüft den Zugriff."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault")
    node.title = new_title
    db.session.commit()
    return get_node_by_id(node.id, vault_id=vault_id, user_id=user_id)


def delete_node(node_id: str, vault_id: int, user_id: int):
    """Löscht einen Node und prüft den Zugriff."""
    _verify_vault_access(vault_id, user_id)
    node_to_delete = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_delete:
        raise ValueError("Node not found in the specified vault")
    db.session.delete(node_to_delete)
    db.session.commit()


def move_node(node_id: str, new_parent_id: str | None, vault_id: int, user_id: int):
    """Bewegt einen Node und prüft den Zugriff."""
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



def _is_descendant(ancestor_id: str, descendant_id: str, vault_id: int) -> bool:
    """Prüft auf zyklische Abhängigkeiten."""
    # (Logik ist unverändert und korrekt)
    if not descendant_id or not ancestor_id: return False
    cte = db.session.query(Node.id, Node.parent_id).filter(Node.id == descendant_id, Node.vault_id == vault_id).cte(
        name="ancestors", recursive=True)
    parent_alias, cte_alias = db.aliased(Node), db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id).filter(parent_alias.vault_id == vault_id).join(
            cte_alias, parent_alias.id == cte_alias.c.parent_id))
    return db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar() is not None


# ... (Funktionen wie get_tree_as_text und get_full_tree_for_export lasse ich weg, da sie in der letzten app.py nicht direkt verwendet wurden, aber die Anpassung wäre analog)


# ==============================================================================
# CHAT-RELATED FUNCTIONS
# ==============================================================================

def list_chat_sessions(vault_id: int, user_id: int) -> list[dict]:
    """Listet die Chat-Sitzungen eines Benutzers in einem Vault auf."""
    _verify_vault_access(vault_id, user_id)
    sessions = (
        ChatSession.query
        .filter_by(vault_id=vault_id, owner_id=user_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "vault_id": session.vault_id,
            "owner_id": session.owner_id
        } for session in sessions
    ]


def get_chat_session_history(session_id: str, user_id: int) -> dict | None:
    """Ruft die Historie einer Session ab und prüft den Besitz."""
    session = get_chat_session_by_id(session_id)
    if not session:
        raise ValueError(f"Chat session with ID {session_id} not found.")
    if session.owner_id != user_id:
        raise PermissionError("You do not have permission to access this chat session.")

    messages = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "author": msg.author.display_name if msg.author else "System",
            "llm_model_source": msg.llm_model_source
        } for msg in session.messages
    ]
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "vault_id": session.vault_id,
        "messages": sorted(messages, key=lambda m: m['timestamp'])
    }


def get_chat_session_by_id(session_id: str) -> ChatSession | None:
    """Holt eine ChatSession und lädt die Nachrichten und deren Autoren vorab."""
    # Erstelle die Abfrage im neuen Stil mit db.select()
    stmt = (
        db.select(ChatSession)
        .options(
            selectinload(ChatSession.messages).joinedload(ChatMessage.author)
        )
        .filter_by(id=session_id)  # Filtere nach der ID
    )
    # Führe die Abfrage aus und gib das einzelne Ergebnis zurück
    return db.session.execute(stmt).scalar_one_or_none()


def create_chat_session(title: str, vault_id: int, owner_id: int) -> ChatSession:
    """Erstellt eine neue ChatSession mit einem Besitzer. `llm_model` wurde entfernt."""
    _verify_vault_access(vault_id, owner_id)
    new_session = ChatSession(title=title, vault_id=vault_id, owner_id=owner_id)
    db.session.add(new_session)
    db.session.flush()
    return new_session


def delete_chat_session(session_id: str, user_id: int):
    """Löscht eine Chat-Sitzung und prüft den Besitz."""
    session = db.session.get(ChatSession, session_id)
    if not session:
        raise ValueError(f"Chat session with ID {session_id} not found.")
    if session.owner_id != user_id:
        raise PermissionError("You do not have permission to delete this chat session.")
    db.session.delete(session)
    db.session.commit()


def add_chat_message(session_id: str, role: str, content: str, author_id: int, llm_model_source: str = None,
                     context_versions: list[Version] = None) -> ChatMessage:
    """Fügt eine Nachricht hinzu, benötigt den Autor und optional das LLM-Modell."""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        author_id=author_id,
        llm_model_source=llm_model_source,
        context_versions=context_versions or []
    )
    db.session.add(message)
    return message


def get_versions_for_node_ids(node_ids: list[str], vault_id: int, user_id: int) -> list[Version]:
    """Holt die aktuellen Versionen für eine Liste von Node-IDs und prüft den Zugriff."""
    _verify_vault_access(vault_id, user_id)
    if not node_ids: return []
    nodes = Node.query.options(joinedload(Node.current_version_object)).filter(
        Node.id.in_(node_ids),
        Node.vault_id == vault_id
    ).all()
    return [node.current_version_object for node in nodes if node.current_version_object]