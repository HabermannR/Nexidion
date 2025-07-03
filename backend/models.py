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

    current_version_object = db.relationship(
        'Version',
        primaryjoin="and_(Node.id==Version.node_id, Node.current_version==Version.version)",
        uselist=False,
        viewonly=True
    )

    def to_dict(self, include_children=False, include_content=True):
        """
        Konvertiert das Node-Objekt in ein serialisierbares Dictionary.
        """
        node_dict = {
            'id': self.id,
            'title': self.title,
            'parent_id': self.parent_id,
            'current_version': self.current_version
        }

        if include_content:
            content = self.current_version_object.content if self.current_version_object else ""
            node_dict['content'] = content

        if include_children:
            # ===================================================================
            # KORREKTUR: Sortiere die Kinder, bevor sie verarbeitet werden.
            # `self.children` ist eine "dynamic" Beziehung, also können wir .order_by() darauf anwenden.
            # ===================================================================
            sorted_children = self.children.order_by(Node.title).all()
            node_dict['children'] = [child.to_dict(include_children=True, include_content=False) for child in
                                     sorted_children]

        return node_dict


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


# NEU: Assoziationstabelle für den Many-to-Many-Kontext
# Eine Nachricht (message) kann viele Kontext-Versionen haben.
# Eine Version kann der Kontext für viele Nachrichten sein.
chat_message_context = db.Table('chat_message_context',
                                db.Column('message_id', db.Integer, db.ForeignKey('chat_messages.id'),
                                          primary_key=True),
                                db.Column('version_id', db.Integer, db.ForeignKey('versions.id'), primary_key=True)
                                )


class ChatSession(db.Model):
    """Represents a single, continuous chat conversation."""
    __tablename__ = 'chat_sessions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=True)  # Kann nach der 1. Frage generiert werden
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    llm_model = db.Column(db.String(100), nullable=False)

    # Eine Sitzung hat viele Nachrichten
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade="all, delete-orphan")


class ChatMessage(db.Model):
    """Represents a single message (from user or assistant) in a chat session."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('chat_sessions.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Many-to-Many-Beziehung zu den Kontext-Versionen
    # Gilt nur für 'user'-Nachrichten, aber die Verknüpfung ist hier definiert.
    context_versions = db.relationship('Version', secondary=chat_message_context, lazy='subquery',
                                       backref=db.backref('context_for_messages', lazy=True))