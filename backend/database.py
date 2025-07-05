# database.py

"""
The data access layer for the application, powered by Flask-SQLAlchemy.

This module provides functions to query and manipulate the database using the
ORM (Object-Relational Mapper), offering a secure and maintainable way to
interact with the Vault, Node, and Version models. All data access is
scoped to a specific vault_id to ensure data isolation.
"""

from sqlalchemy import case, func
from sqlalchemy.orm import joinedload, selectinload

from models import db, Vault, Node, Version, ChatSession, ChatMessage


def init_db():
    """
    Initializes the database schema and creates the very first default vault
    and its root node if no vaults exist yet. This is idempotent.
    """
    print("Creating database tables if they don't exist...")
    db.create_all()

    # Check if any vault exists. If not, create a default one.
    if Vault.query.first() is None:
        print("No vaults found. Creating a default 'Main' vault.")
        try:
            create_vault_with_root_node(name="Main")
            print("Default 'Main' vault created successfully.")
        except Exception as e:
            print(f"Error creating the default vault: {e}")
    else:
        print("Database already contains vaults. Skipping default creation.")


# ==============================================================================
# VAULT-RELATED FUNCTIONS
# ==============================================================================

def get_all_vaults() -> list[Vault]:
    """
    Retrieves all vaults, sorted by name.
    Returns a list of Vault objects.
    """
    return Vault.query.order_by(Vault.name).all()


def create_vault_with_root_node(name: str) -> Vault:
    """
    Creates a new vault and its corresponding root node ("Summary") after
    ensuring the name is unique.

    Args:
        name: The desired name for the new vault.

    Returns:
        The created Vault object.

    Raises:
        ValueError: If the name is empty or already exists.
    """
    name_stripped = name.strip()
    if not name_stripped:
        raise ValueError("Vault name cannot be empty.")

    if Vault.query.filter_by(name=name_stripped).first():
        raise ValueError(f"A vault with the name '{name_stripped}' already exists.")

    try:
        new_vault = Vault(name=name_stripped)
        db.session.add(new_vault)
        db.session.flush()

        root_node = Node(title="Summary", vault_id=new_vault.id, parent_id=None)
        db.session.add(root_node)
        db.session.flush()

        initial_version = Version(
            node_id=root_node.id,
            version=1,
            content=f"This is the root node for the '{name_stripped}' vault."
        )
        db.session.add(initial_version)

        db.session.commit()
        return new_vault
    except Exception as e:
        db.session.rollback()
        raise e


def rename_vault(vault_id: int, new_name: str) -> Vault:
    """
    Renames a vault after ensuring the new name is unique.

    Raises:
        ValueError: If the vault is not found or the new name is already in use.
    """
    vault = Vault.query.get(vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")

    new_name_stripped = new_name.strip()
    if not new_name_stripped:
        raise ValueError("New vault name cannot be empty.")

    existing = Vault.query.filter(Vault.id != vault_id, Vault.name == new_name_stripped).first()
    if existing:
        raise ValueError(f"Another vault with the name '{new_name_stripped}' already exists.")

    vault.name = new_name_stripped
    db.session.commit()
    return vault


def delete_vault(vault_id: int):
    """
    Deletes a vault and all its associated data (nodes, versions, etc.).

    Raises:
        ValueError: If the vault is not found or it is the last remaining vault.
    """
    vault = Vault.query.get(vault_id)
    if not vault:
        raise ValueError(f"Vault with ID {vault_id} not found.")

    if Vault.query.count() <= 1:
        raise ValueError("Cannot delete the last remaining vault.")

    try:
        # The cascade='all, delete-orphan' rule in the models handles deletion of children.
        db.session.delete(vault)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


# ==============================================================================
# NODE-RELATED FUNCTIONS
# ==============================================================================

def get_all_nodes_as_tree(vault_id: int) -> list[dict]:
    """
    Fetches all nodes for a specific vault and organizes them into a tree structure.
    """
    all_nodes = Node.query.filter_by(vault_id=vault_id).order_by(Node.title).all()
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


def get_all_nodes_as_list(vault_id: int) -> list[dict]:
    """Fetches all nodes for a specific vault as a simple flat list."""
    nodes = Node.query.filter_by(vault_id=vault_id).order_by(Node.title).all()
    return [node.to_dict(include_content=True) for node in nodes]


def get_nodes_by_title(title: str, vault_id: int) -> list[dict]:
    """Fetches nodes by title within a specific vault, sorted by relevance."""
    if not title:
        return []
    search_term = f"%{title}%"
    relevance = case((Node.title.ilike(title), 0), else_=1)
    nodes = (
        Node.query
        .filter(Node.vault_id == vault_id, Node.title.ilike(search_term))
        .order_by(relevance, Node.title)
        .all()
    )
    return [node.to_dict(include_content=False) for node in nodes]


def get_node_by_id(node_id: str, vault_id: int) -> dict | None:
    """
    Retrieves a single node by its ID, validating against the vault.
    Crucially, it now loads the full version history for the detail view.

    Returns:
        A dictionary of the node or None if not found.
    """
    node = (
        Node.query
        .options(
            joinedload(Node.current_version_object),
            selectinload(Node.versions)
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
            'timestamp': v.timestamp.isoformat()
        }
        for v in node.versions
    ]

    node_dict['versions'] = sorted(
        versions_list,
        key=lambda v: v['version'],
        reverse=True
    )

    return node_dict


def get_content_for_nodes(node_ids: list[str], vault_id: int) -> dict:
    """
    Retrieves titles and concatenated content for a list of node IDs within a vault.
    This is the sole function for fetching batch context, optimized for performance.

    Returns:
        A dictionary {"titles": [...], "content": "..."}.
    """
    if not node_ids:
        return {"titles": [], "content": ""}

    nodes_query = (
        db.session.query(Node)
        .options(joinedload(Node.current_version_object))
        .filter(Node.id.in_(node_ids), Node.vault_id == vault_id)
        .all()
    )

    nodes_by_id = {node.id: node for node in nodes_query}
    ordered_titles, ordered_contents = [], []

    for node_id in node_ids:
        if node_id in nodes_by_id:
            node = nodes_by_id[node_id]
            ordered_titles.append(node.title)
            content = node.current_version_object.content if node.current_version_object else ""
            ordered_contents.append(
                f"--- START OF DOCUMENT: {node.title} ---\n{content}\n--- END OF DOCUMENT: {node.title} ---")

    full_content = "\n\n".join(ordered_contents)
    return {"titles": ordered_titles, "content": full_content}


def create_node(title: str, content: str, parent_id: str | None, vault_id: int) -> Node:
    """Creates a new node and its initial version within a specific vault."""
    if parent_id:
        parent_node = Node.query.filter_by(id=parent_id, vault_id=vault_id).first()
        if not parent_node:
            raise ValueError("Parent node not found in the specified vault.")

    new_node = Node(title=title, parent_id=parent_id, current_version=1, vault_id=vault_id)
    db.session.add(new_node)
    db.session.flush()

    initial_version = Version(node_id=new_node.id, version=1, content=content)
    db.session.add(initial_version)
    db.session.commit()
    return new_node


def update_node(node_id: str, vault_id: int, **kwargs) -> Node:
    """
    Updates a node's title and/or content by creating a new version.
    Ensures the node belongs to the correct vault.
    """
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault")

    current_title = node.title
    current_content = node.current_version_object.content if node.current_version_object else ""
    new_title = kwargs.get('title', current_title)
    new_content = kwargs.get('content', current_content)

    if new_title == current_title and new_content == current_content:
        return node  # No changes, do nothing.

    next_version_number = (db.session.query(func.max(Version.version))
                           .filter(Version.node_id == node.id).scalar() or 0) + 1
    new_version = Version(node_id=node.id, version=next_version_number, content=new_content)
    db.session.add(new_version)

    node.title = new_title
    node.current_version = next_version_number
    db.session.commit()
    db.session.refresh(node)
    return node


def rename_node(node_id: str, new_title: str, vault_id: int) -> dict:
    """Updates only a node's title, ensuring it's in the correct vault."""
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault")
    node.title = new_title
    db.session.commit()
    return get_node_by_id(node.id, vault_id=vault_id)


def delete_node(node_id: str, vault_id: int):
    """Deletes a node and its cascaded data, ensuring it belongs to the correct vault."""
    node_to_delete = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_delete:
        raise ValueError("Node not found in the specified vault")

    db.session.delete(node_to_delete)
    db.session.commit()


def move_node(node_id: str, new_parent_id: str | None, vault_id: int):
    """Moves a node to a new parent within the same vault."""
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


def get_nodes_by_ids(node_ids: list[str], vault_id: int) -> list[dict]:
    """
    Retrieves full node objects, including their content, for a given list of IDs.

    Returns:
        A list of node dictionaries.
    """
    if not node_ids:
        return []

    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter(Node.id.in_(node_ids), Node.vault_id == vault_id)
        .all()
    )

    return [node.to_dict(include_content=True) for node in nodes]


def _is_descendant(ancestor_id: str, descendant_id: str, vault_id: int) -> bool:
    """
    Helper function to check for cyclic dependencies within a vault using a
    recursive Common Table Expression (CTE).
    """
    if not descendant_id or not ancestor_id:
        return False

    cte = (
        db.session.query(Node.id, Node.parent_id)
        .filter(Node.id == descendant_id, Node.vault_id == vault_id)
        .cte(name="ancestors", recursive=True)
    )
    parent_alias = db.aliased(Node)
    cte_alias = db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id)
        .filter(parent_alias.vault_id == vault_id)
        .join(cte_alias, parent_alias.id == cte_alias.c.parent_id)
    )
    is_found = db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar()
    return is_found is not None


def get_tree_as_text(vault_id: int) -> str:
    """Fetches the node tree for a vault and formats it as indented text."""
    tree = get_all_nodes_as_tree(vault_id=vault_id)
    text_lines = []

    def build_lines(nodes, indent_level=0):
        indent = "  " * indent_level
        for node in sorted(nodes, key=lambda x: x['title']):
            text_lines.append(f"{indent}- {node['title']}")
            if node.get('children'):
                build_lines(node['children'], indent_level + 1)

    build_lines(tree)
    return "\n".join(text_lines)


def get_full_tree_for_export(vault_id: int) -> list[dict]:
    """
    Fetches the entire tree for a vault, including all node data and version history.
    This is a memory-intensive operation designed for exporting.
    """
    all_nodes = Node.query.filter_by(vault_id=vault_id).all()
    all_versions = Version.query.join(Node).filter(Node.vault_id == vault_id).all()

    versions_map = {}
    for version in all_versions:
        if version.node_id not in versions_map:
            versions_map[version.node_id] = []
        versions_map[version.node_id].append({
            'version': version.version,
            'content': version.content,
            'timestamp': version.timestamp.isoformat()
        })

    nodes_map = {}
    for node in all_nodes:
        node_dict = node.to_dict(include_content=False)
        node_dict['versions'] = sorted(
            versions_map.get(node.id, []),
            key=lambda v: v['version']
        )
        nodes_map[node.id] = node_dict

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

    def sort_recursively(nodes):
        nodes.sort(key=lambda n: n['title'])
        for node in nodes:
            if 'children' in node and node['children']:
                sort_recursively(node['children'])

    sort_recursively(tree)
    return tree


# ==============================================================================
# CHAT-RELATED FUNCTIONS
# ==============================================================================

def list_chat_sessions(vault_id: int) -> list[dict]:
    """
    Retrieves a list of all chat sessions for a specific vault.
    """
    sessions = (
        ChatSession.query
        .filter_by(vault_id=vault_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "llm_model": session.llm_model,
            "vault_id": session.vault_id
        } for session in sessions
    ]


def get_chat_session_history(session_id: str) -> dict | None:
    """
    Retrieves the complete history of a single chat session, including messages.
    """
    session = ChatSession.query.options(selectinload(ChatSession.messages)).get(session_id)
    if not session:
        return None

    messages = [
        {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
        for msg in session.messages
    ]
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "llm_model": session.llm_model,
        "vault_id": session.vault_id,
        "messages": messages
    }


def get_chat_session_by_id(session_id: str) -> ChatSession | None:
    """Retrieves a ChatSession object by its ID, with its messages preloaded."""
    return ChatSession.query.options(selectinload(ChatSession.messages)).get(session_id)


def create_chat_session(title: str, llm_model: str, vault_id: int) -> ChatSession:
    """
    Creates a new ChatSession instance, adds it to the session, and flushes
    to assign an ID. Does not commit.
    """
    new_session = ChatSession(llm_model=llm_model, title=title, vault_id=vault_id)
    db.session.add(new_session)
    db.session.flush()  # Flush to get the new_session.id
    return new_session


def delete_chat_session(session_id: str):
    """
    Deletes a chat session and all its associated messages.

    Args:
        session_id: The ID of the session to delete.

    Raises:
        ValueError: If the session with the given ID is not found.
    """
    session = ChatSession.query.get(session_id)
    if not session:
        raise ValueError(f"Chat session with ID {session_id} not found.")

    try:
        # The 'cascade' option on the relationship in the model will handle deleting messages
        db.session.delete(session)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Re-raise the exception to be handled by the caller
        raise e


def add_chat_message(session_id: str, role: str, content: str, context_versions: list[Version] = None) -> ChatMessage:
    """
    Creates a new ChatMessage, associates it with context versions if provided,
    and adds it to the session. Does not commit.
    """
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        context_versions=context_versions or []
    )
    db.session.add(message)
    return message


def get_versions_for_node_ids(node_ids: list[str], vault_id: int) -> list[Version]:
    """
    Efficiently fetches the current_version_object for a list of node IDs
    within a specific vault.
    """
    if not node_ids:
        return []

    nodes = Node.query.options(joinedload(Node.current_version_object)).filter(
        Node.id.in_(node_ids),
        Node.vault_id == vault_id
    ).all()

    # Return only the version objects that actually exist
    return [node.current_version_object for node in nodes if node.current_version_object]