# database.py
"""
The data access layer for the application, powered by Flask-SQLAlchemy.

This module provides functions to query and manipulate the database using the
ORM (Object-Relational Mapper), offering a secure and maintainable way to
interact with the Node and Version models.
"""

from models import db, Node, Version
from sqlalchemy import case, text
from sqlalchemy.orm import joinedload, selectinload


def init_db(root_node_title='Summary'):
    """
    Initializes the database schema and creates the root node.
    This is idempotent and will only create tables/root node if they don't exist.

    Args:
        root_node_title (str): The title for the root node of the knowledge base.
    """
    print("Creating database tables...")
    db.create_all()

    # Check if a root node (parent_id=None) already exists
    root_node = Node.query.filter_by(parent_id=None).first()
    if not root_node:
        print(f"No root node found. Creating new root node with title: '{root_node_title}'")
        # MODIFICATION: Remove the circular import and call the function directly.
        create_node(
            title=root_node_title,
            content=f'This is the root of the "{root_node_title}" knowledge base.',
            parent_id=None
        )
    else:
        print(f"Database already has a root node titled: '{root_node.title}'. Skipping creation.")

    # ... (rest of your database.py file)


def get_all_nodes_as_tree():
    """
    Fetches all nodes and organizes them into a tree structure.
    This is optimized to use a single query to prevent the N+1 problem.
    """
    # 1. Fetch all nodes in one go.
    all_nodes = Node.query.order_by(Node.title).all()

    # 2. Create a dictionary for quick lookups by ID.
    nodes_map = {node.id: node.to_dict(include_content=False) for node in all_nodes}

    # 3. Build the tree structure.
    tree = []
    for node_id, node_dict in nodes_map.items():
        parent_id = node_dict.get('parent_id')
        if parent_id in nodes_map:
            # This is a child node, add it to its parent's 'children' list.
            parent = nodes_map[parent_id]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(node_dict)
        else:
            # This is a root node.
            tree.append(node_dict)

    # Optional: Sort children within each node if the order matters
    # (The initial query already sorted everything by title)
    def sort_children_recursively(nodes):
        for node in nodes:
            if 'children' in node:
                node['children'] = sorted(node['children'], key=lambda x: x['title'])
                sort_children_recursively(node['children'])

    sort_children_recursively(tree)

    return tree


def get_all_nodes_as_list():
    """Fetches all nodes as a simple flat list of dictionaries using the .to_dict() method."""
    nodes = Node.query.order_by(Node.title).all()
    # include_content=True hier, falls eine Listenansicht mal den Inhalt braucht.
    return [node.to_dict(include_content=True) for node in nodes]


def get_nodes_by_title(title: str) -> list[dict]:
    """Fetches nodes by title using the .to_dict() method."""
    if not title:
        return []
    search_term = f"%{title}%"
    relevance = case((Node.title.ilike(title), 0), else_=1)
    nodes: list[Node] = Node.query.filter(Node.title.ilike(search_term)).order_by(relevance, Node.title).all()
    # Für Suchergebnisse wollen wir typischerweise den Inhalt nicht, um die Antwort klein zu halten.
    return [node.to_dict(include_content=False) for node in nodes]


def get_node_by_id(node_id):
    """Fetches a single node and its version history by its ID."""
    # Use eager loading to fetch related objects in a more efficient way.
    # - joinedload: Good for one-to-one relationships (current_version_object).
    # - selectinload: Good for one-to-many relationships (versions).
    node = (
        Node.query
        .options(
            joinedload(Node.current_version_object),
            selectinload(Node.versions)
        )
        .get(node_id)
    )

    if not node:
        return None

    # Now, when we call .to_dict() or access .versions, no new queries are sent.
    node_dict = node.to_dict()

    versions_list = [{
        'version': v.version, 'content': v.content, 'timestamp': v.timestamp.isoformat()
    } for v in sorted(node.versions, key=lambda x: x.version, reverse=True)]

    node_dict['versions'] = versions_list
    return node_dict

def get_node_content_by_id(node_id: int) -> str:
    """
    Holt nur den Inhalt eines Nodes anhand seiner ID.
    Gibt einen leeren String zurück, wenn der Node oder seine Version nicht gefunden wird.
    """
    node = Node.query.get(node_id)
    if node and node.current_version_object:
        return node.current_version_object.content
    return ""


def create_node(title, content, parent_id):
    """Creates a new node and its initial version."""
    # ACHTUNG: Node hat keine content-Spalte mehr!
    new_node = Node(title=title, parent_id=parent_id, current_version=1)
    # Wir müssen den Node zuerst zur Session hinzufügen, um eine ID für die Version zu haben
    db.session.add(new_node)
    db.session.flush()  # Weist die ID zu, ohne zu committen

    initial_version = Version(node_id=new_node.id, version=1, content=content)
    db.session.add(initial_version)

    db.session.commit()
    # get_node_by_id holt jetzt den vollständig formatierten Node
    return get_node_by_id(new_node.id)


def update_node(node_id: str, **kwargs):
    node = Node.query.get(node_id)
    if not node:
        raise ValueError("Node not found")

    # Der Titel kommt immer vom Node selbst
    current_title = node.title
    # Der Inhalt kommt immer von der aktuellen Version
    current_content = node.current_version_object.content if node.current_version_object else ""

    new_title = kwargs.get('title', current_title)
    new_content = kwargs.get('content', current_content)

    if new_title == current_title and new_content == current_content:
        return node

    next_version_number = (db.session.query(db.func.max(Version.version))
                           .filter(Version.node_id == node.id).scalar() or 0) + 1

    new_version = Version(
        node_id=node.id,
        version=next_version_number,
        content=new_content  # Nur hier wird der neue Inhalt gespeichert
    )
    db.session.add(new_version)

    # Aktualisiere den Haupt-Node
    node.title = new_title
    node.current_version = next_version_number
    # KEIN node.content = new_content mehr nötig!

    db.session.commit()
    db.session.refresh(node)

    return node


def rename_node(node_id, new_title):
    """Updates a node's title without creating a new version."""
    node = Node.query.get(node_id)
    if not node:
        raise ValueError("Node not found")
    node.title = new_title
    db.session.commit()
    # Verwende get_node_by_id, um eine konsistente Antwort zu gewährleisten.
    return get_node_by_id(node.id)

def delete_node(node_id):
    """
    Deletes a node from the database.
    - Associated versions are deleted via the 'cascade' rule in the model.
    - Children nodes are orphaned (parent_id set to NULL) via the database's
      ON DELETE SET NULL foreign key constraint.
    """
    node_to_delete = Node.query.get(node_id)

    if node_to_delete:
        db.session.delete(node_to_delete)
        db.session.commit()


def move_node(node_id, new_parent_id):
    """Moves a node to a new parent."""
    # Setting new_parent_id to None or an empty string should make it a root node
    if not new_parent_id:
        new_parent_id = None

    if str(node_id) == str(new_parent_id) or _is_descendant(node_id, new_parent_id):
        raise ValueError("Cannot move a node into itself or one of its own children.")

    node_to_move = Node.query.get(node_id)
    if node_to_move:
        node_to_move.parent_id = new_parent_id
        db.session.commit()


def get_context_from_ids(node_ids, with_titles=False):
    """Fetches content for a list of node IDs using the current version."""
    if not node_ids:
        return {"context": "", "titles": []} if with_titles else ""

    # Eager load the current_version_object to avoid N+1 queries.
    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter(Node.id.in_(node_ids))
        .all()
    )

    # The rest of the function remains the same, but is now much faster.
    context_parts, titles = [], []
    for node in nodes:
        content = node.current_version_object.content if node.current_version_object else ""
        context_parts.append(f"--- Node: {node.title} ---\n\n{content}")
        if with_titles:
            titles.append(node.title)

    context_string = "\n\n".join(context_parts)
    return {"context": context_string, "titles": titles} if with_titles else context_string


def get_tree_as_text():
    """Fetches the entire node tree and formats it as indented text."""
    tree = get_all_nodes_as_tree()
    text_lines = []

    def build_lines(nodes, indent_level=0):
        indent = "  " * indent_level
        for node in sorted(nodes, key=lambda x: x['title']):
            text_lines.append(f"{indent}- {node['title']}")
            if node.get('children'):
                build_lines(node['children'], indent_level + 1)

    build_lines(tree)
    return "\n".join(text_lines)


# database.py

def get_full_tree_for_export():
    """
    Fetches the entire KB tree including all node data and all version history.
    This is a memory-intensive operation designed for exporting.
    """
    all_nodes = Node.query.all()
    all_versions = Version.query.all()

    # Map versions to their node_id for quick lookup
    versions_map = {}
    for version in all_versions:
        if version.node_id not in versions_map:
            versions_map[version.node_id] = []
        versions_map[version.node_id].append({
            'version': version.version,
            'content': version.content,
            'timestamp': version.timestamp.isoformat()
        })

    # Create the base node dictionaries, attaching all their versions
    nodes_map = {}
    for node in all_nodes:
        node_dict = node.to_dict(include_content=False)  # Get base dict
        node_dict['versions'] = sorted(
            versions_map.get(node.id, []),
            key=lambda v: v['version']
        )
        nodes_map[node.id] = node_dict

    # Build the tree structure
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

    # Sort for consistent output
    def sort_recursively(nodes):
        nodes.sort(key=lambda n: n['title'])
        for node in nodes:
            if 'children' in node and node['children']:
                sort_recursively(node['children'])

    sort_recursively(tree)
    return tree


def _is_descendant(ancestor_id, descendant_id):
    """
    Helper function to check if a node is a descendant of another,
    using an optimized recursive CTE query to avoid iterative lookups.
    """
    if not descendant_id or not ancestor_id:
        return False

    # A recursive CTE to find all ancestors of the descendant_id
    cte = db.session.query(Node.id, Node.parent_id).filter(Node.id == descendant_id).cte(name="ancestors",
                                                                                         recursive=True)

    # Recursive part of the CTE
    parent_alias = db.aliased(Node)
    cte_alias = db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id)
        .join(cte_alias, parent_alias.id == cte_alias.c.parent_id)
    )

    # Check if the ancestor_id exists in the set of all ancestors.
    is_found = db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar()

    return is_found is not None