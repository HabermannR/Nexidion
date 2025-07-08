# models.py
"""
Defines the SQLAlchemy database models for the Knowledge Base application.

These models map Python classes to the tables in the SQLite database,
providing a secure and object-oriented way to interact with the data.
"""

import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Create the SQLAlchemy database instance.
# This will be initialized with the Flask app in the main application file.
db = SQLAlchemy()


class User(db.Model):
    """
    Represents a user of the system.
    Can be a human user who logs in, or a service account for an LLM.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # z.B. 'richard', 'claude-3-opus'
    display_name = db.Column(db.String(120), nullable=False)  # z.B. 'Richard', 'Claude 3 Opus'
    password_hash = db.Column(db.String(256), nullable=True) # String-Länge sicherheitshalber erhöhen
    user_type = db.Column(db.String(20), nullable=False, default='human')  # 'human' or 'llm_assistant'
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    owned_vaults = db.relationship('Vault', backref='owner', lazy=True)
    owned_chat_sessions = db.relationship('ChatSession', backref='owner', lazy=True)
    authored_versions = db.relationship('Version', backref='author', lazy=True)
    authored_messages = db.relationship('ChatMessage', backref='author', lazy=True)

    def set_password(self, password):
        """Creates a password hash using werkzeug."""
        if self.user_type == 'human':
            # Die Methode 'pbkdf2:sha256' ist der Standard und sehr sicher.
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks a password against the hash using werkzeug."""
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'user_type': self.user_type,
            'is_admin': self.is_admin
        }

class Vault(db.Model):
    """
    Represents a single, isolated knowledge base or 'vault'.
    Each vault has its own set of nodes and chat sessions.
    """
    __tablename__ = 'vaults'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Relationships to nodes and sessions within this vault.
    # The cascade rule ensures that when a vault is deleted, all its
    # associated nodes and chat sessions are also automatically deleted.
    nodes = db.relationship('Node', backref='vault', lazy='dynamic', cascade="all, delete-orphan")
    chat_sessions = db.relationship('ChatSession', backref='vault', lazy='dynamic', cascade="all, delete-orphan")

    def to_dict(self):
        """
        Serializes the Vault object to a dictionary.
        """
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }



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

    vault_id = db.Column(db.Integer, db.ForeignKey('vaults.id'), nullable=False, index=True)

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
            'current_version': self.current_version,
            'vault_id': self.vault_id  # NEU: vault_id im Dictionary
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
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)


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


    vault_id = db.Column(db.Integer, db.ForeignKey('vaults.id'), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
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

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    llm_model_source = db.Column(db.String(100),
                                 nullable=True)  # z.B. 'claude-3-5-sonnet-20240620', nur für role='assistant'
    # Many-to-Many-Beziehung zu den Kontext-Versionen
    # Gilt nur für 'user'-Nachrichten, aber die Verknüpfung ist hier definiert.
    context_versions = db.relationship('Version', secondary=chat_message_context, lazy='subquery',
                                       backref=db.backref('context_for_messages', lazy=True))

