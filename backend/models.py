# models.py
"""
Defines the SQLAlchemy database models for the Knowledge Base application.

These models map Python classes to the tables in the SQLite database,
providing a secure and object-oriented way to interact with the data.
"""

import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

# Create the SQLAlchemy database instance.
# This will be initialized with the Flask app in the main application file.
db = SQLAlchemy()


class Node(db.Model):
    """
    Represents a single node in the knowledge graph.
    Each node can have content, a title, and a parent node, forming a tree.
    """
    __tablename__ = 'nodes'

    # --- Columns ---
    # The primary key is a UUID string, generated automatically for new nodes.
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=True)  # Matches schema where content can be NULL
    current_version = db.Column(db.Integer, nullable=False, default=1)

    # --- Relationships ---
    # Foreign key for the self-referential parent-child relationship.
    # The index=True mirrors the CREATE INDEX command in your schema for better performance.
    parent_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=True, index=True)

    # Defines the 'node.children' attribute, which provides a query to get all child nodes.
    # Using lazy='dynamic' is efficient as it doesn't load all children into memory at once.
    # The database-level "ON DELETE SET NULL" is respected by this relationship.
    children = db.relationship('Node', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # Defines the 'node.versions' attribute.
    # The 'cascade="all, delete-orphan"' rule tells SQLAlchemy to automatically delete
    # all versions of a node when the node itself is deleted, mirroring "ON DELETE CASCADE".
    versions = db.relationship('Version', backref='node', lazy=True, cascade="all, delete-orphan")


class Version(db.Model):
    """
    Represents a single version of a node's content.
    A new version is created each time a node is updated.
    """
    __tablename__ = 'versions'

    # --- Columns ---
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=True)  # Matches schema where content can be NULL
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # --- Relationships ---
    # Foreign key linking this version back to its parent Node.
    node_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=False, index=True)