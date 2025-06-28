# database.py
"""
The data access layer for the application, powered by Flask-SQLAlchemy.

This module provides functions to query and manipulate the database using the
ORM (Object-Relational Mapper), offering a secure and maintainable way to
interact with the Node and Version models.
"""

from models import db, Node, Version


def init_db():
    """
    Initializes the database schema using the SQLAlchemy models.
    This is idempotent and will only create tables that don't already exist.
    """
    db.create_all()
    # Create the root "Summary" node if it doesn't exist
    summary = Node.query.filter_by(title='Summary', parent_id=None).first()
    if not summary:
        create_node(title='Summary', content='This is the root of your knowledge base.', parent_id=None)


def get_all_nodes_as_tree():
    """Fetches all nodes and organizes them into a tree structure."""
    all_nodes = Node.query.order_by(Node.title).all()
    node_map = {node.id: {'id': node.id, 'title': node.title, 'children': []} for node in all_nodes}

    tree = []
    for node in all_nodes:
        if node.parent_id is None:
            tree.append(node_map[node.id])
        elif node.parent_id in node_map:
            # Safely append child to parent
            node_map[node.parent_id]['children'].append(node_map[node.id])
    return tree


def get_all_nodes_as_list():
    """Fetches all nodes as a simple flat list of dictionaries."""
    nodes = Node.query.order_by(Node.title).all()
    return [{
        'id': node.id,
        'title': node.title,
        'parent_id': node.parent_id,
        'content': node.content,
        'current_version': node.current_version
    } for node in nodes]


def get_nodes_by_title(title):
    """Fetches all nodes that match a given title (case-insensitive)."""
    search_term = f"%{title.lower()}%"
    nodes = Node.query.filter(db.func.lower(Node.title).like(search_term)).order_by(Node.title).all()
    # Convert a list of Node objects to a list of dictionaries for JSON serialization
    return [{
        'id': node.id, 'title': node.title, 'parent_id': node.parent_id, 'content': node.content
    } for node in nodes]


def get_node_by_id(node_id):
    """Fetches a single node and its version history by its ID."""
    # .get() is the most efficient way to query by primary key
    node = Node.query.get(node_id)
    if not node:
        return None

    # Thanks to the 'node.versions' relationship, we don't need a second query!
    versions_list = [{
        'version': v.version, 'content': v.content, 'timestamp': v.timestamp.isoformat()
    } for v in sorted(node.versions, key=lambda x: x.version)]

    return {
        'id': node.id,
        'title': node.title,
        'content': node.content,
        'current_version': node.current_version,
        'parent_id': node.parent_id,
        'versions': versions_list
    }


def create_node(title, content, parent_id):
    """Creates a new node and its initial version."""
    new_node = Node(title=title, content=content, parent_id=parent_id, current_version=1)
    initial_version = Version(node=new_node, version=1, content=content)

    db.session.add(new_node)
    db.session.add(initial_version)
    db.session.commit()
    return get_node_by_id(new_node.id)


def update_node(node_id, title, content):
    """Updates a node's title and content, creating a new version."""
    node = Node.query.get(node_id)
    if not node:
        raise ValueError("Node not found")

    new_version_num = node.current_version + 1

    # Directly modify the object's attributes
    node.title = title
    node.content = content
    node.current_version = new_version_num

    # Create the new version object
    new_version = Version(node=node, version=new_version_num, content=content)
    db.session.add(new_version)

    # SQLAlchemy is smart and will bundle the UPDATE for the node and the INSERT
    # for the version into a single transaction.
    db.session.commit()
    return get_node_by_id(node.id)


def rename_node(node_id, new_title):
    """
    Updates a node's title without creating a new version.
    This is a lightweight operation for quick title edits.
    """
    node = Node.query.get(node_id)
    if not node:
        raise ValueError("Node not found")

    # Update the title directly
    node.title = new_title

    # Commit the session to save the change to the database
    db.session.commit()

    # Return the updated node as a simple dictionary for the API response
    return {
        'id': node.id,
        'title': node.title,
        'parent_id': node.parent_id,
        'content': node.content,
        'current_version': node.current_version
    }


def delete_node(node_id):
    """Deletes a node, its versions (via cascade), and orphans its children."""
    node_to_delete = Node.query.get(node_id)
    if not node_to_delete:
        return

    # Manually orphan children to ensure application logic is clear,
    # though the database's ON DELETE SET NULL would also handle this.
    for child in node_to_delete.children:
        child.parent_id = None

    # This one delete call is all we need.
    # The 'cascade' on the relationship will handle deleting all associated versions.
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
    """Fetches content for a list of node IDs using a safe IN clause."""
    if not node_ids:
        return {"context": "", "titles": []} if with_titles else ""

    # This is the safe, SQLAlchemy way to do an "IN" query.
    nodes = Node.query.filter(Node.id.in_(node_ids)).all()
    nodes_by_id = {node.id: node for node in nodes}  # Use direct ID for mapping

    context_parts, titles = [], []
    for node_id in node_ids:
        node = nodes_by_id.get(node_id)
        if node:
            context_parts.append(f"--- Node: {node.title} ---\n\n{node.content or ''}")
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


def _is_descendant(ancestor_id, descendant_id):
    """Helper function to check if a node is a descendant of another."""
    if not descendant_id:
        return False

    current_node = Node.query.get(descendant_id)
    # Traverse up the tree using the .parent relationship
    while current_node and current_node.parent:
        current_node = current_node.parent
        if str(current_node.id) == str(ancestor_id):
            return True
    return False