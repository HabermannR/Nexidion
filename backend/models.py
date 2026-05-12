# models.py
"""
Defines the SQLAlchemy database models for the Knowledge Base application.

These models map Python classes to the tables in the Postgres database,
providing a secure and object-oriented way to interact with the data.
"""

import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.ext.associationproxy import association_proxy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects import postgresql
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

    # Cached vault list for fast GET /api/vaults/ responses
    cached_vault_list      = db.Column(db.JSON,       nullable=True)
    cached_vault_list_etag = db.Column(db.String(32), nullable=True)

    # Relationships
    owned_vaults = db.relationship('Vault', back_populates='owner', lazy=True)
    authored_versions = db.relationship('Version', back_populates='author', lazy=True)

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

    # 1. Ultra-lightweight tree for the Frontend
    cached_ui_tree = db.Column(db.JSON, nullable=True)
    cached_ui_tree_etag = db.Column(db.String(32), nullable=True)

    # 2. Heavier tree including AI summaries for the LLM
    cached_agent_tree = db.Column(db.JSON, nullable=True)
    cached_agent_tree_etag = db.Column(db.String(32), nullable=True)

    # Relationships to nodes and sessions within this vault.
    # The cascade rule ensures that when a vault is deleted, all its
    # associated nodes and chat sessions are also automatically deleted.
    nodes = db.relationship('Node', back_populates='vault', lazy='dynamic', cascade="all, delete-orphan")
    # Add explicitly for the User relationship
    owner = db.relationship('User', back_populates='owned_vaults')

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
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    current_version = db.Column(db.Integer, nullable=False, default=1)
    icon = db.Column(db.String(50), nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    summary_is_current = db.Column(db.Boolean, nullable=False, default=False)

    fts_summary_en = db.Column(postgresql.TSVECTOR(), sa.Computed(
        "setweight(to_tsvector('english', coalesce(ai_summary,'')), 'C')",
        persisted=True
    ))
    fts_summary_de = db.Column(postgresql.TSVECTOR(), sa.Computed(
        "setweight(to_tsvector('german', coalesce(ai_summary,'')), 'C')",
        persisted=True
    ))

    __table_args__ = (
        db.Index('ix_nodes_fts_summary_en', 'fts_summary_en', postgresql_using='gin'),
        db.Index('ix_nodes_fts_summary_de', 'fts_summary_de', postgresql_using='gin'),
    )

    # --- Relationships ---
    parent_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=True, index=True)
    vault_id = db.Column(db.Integer, db.ForeignKey('vaults.id'), nullable=False, index=True)

    versions = db.relationship('Version', back_populates='node', lazy=True, cascade="all, delete-orphan")
    vault = db.relationship('Vault', back_populates='nodes')

    # Self-referential relationships using back_populates
    children = db.relationship('Node', back_populates='parent')
    parent = db.relationship('Node', back_populates='children', remote_side=[id])

    current_version_object = db.relationship(
        'Version',
        primaryjoin="and_(Node.id==Version.node_id, Node.current_version==Version.version)",
        uselist=False,
        viewonly=True
    )

    title = association_proxy('current_version_object', 'title')

    def to_dict(self, include_children=False, include_content=True):
        node_dict = {
            'id': self.id,
            'title': self.current_version_object.title if self.current_version_object else "Unbenannter Node",
            'parent_id': self.parent_id,
            'current_version': self.current_version,
            'vault_id': self.vault_id,
            'icon': self.icon,
            'ai_summary': self.ai_summary,
            'summary_is_current': self.summary_is_current,
        }

        if include_content:
            content = self.current_version_object.content if self.current_version_object else ""
            node_dict['content'] = content

        if include_children:
            node_dict['children'] = [
                child.to_dict(include_children=True, include_content=False)
                for child in self.children
            ]

        return node_dict


class Version(db.Model):
    """
    Represents a single version of a node's content.
    A new version is created each time a node is updated.
    """
    __tablename__ = 'versions'

    # --- Columns ---
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=True)  # Matches schema where content can be NULL
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    fts_en = db.Column(postgresql.TSVECTOR(), sa.Computed(
        "setweight(to_tsvector('english', coalesce(title,'')), 'A') || "
        "setweight(to_tsvector('english', coalesce(content,'')), 'B')",
        persisted=True
    ))
    fts_de = db.Column(postgresql.TSVECTOR(), sa.Computed(
        "setweight(to_tsvector('german', coalesce(title,'')), 'A') || "
        "setweight(to_tsvector('german', coalesce(content,'')), 'B')",
        persisted=True
    ))

    __table_args__ = (
        db.Index('ix_versions_fts_en', 'fts_en', postgresql_using='gin'),
        db.Index('ix_versions_fts_de', 'fts_de', postgresql_using='gin'),
    )

    # --- Relationships ---
    # Foreign key linking this version back to its parent Node.
    node_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    node = db.relationship('Node', back_populates='versions')
    author = db.relationship('User', back_populates='authored_versions')

    def to_dict(self, include_content=True):
        """
        Gibt eine Dictionary-Repräsentation der Version zurück.
        Enthält jetzt alle für die UI notwendigen Daten, um den "Single API Call"-Ansatz zu unterstützen.
        """
        data = {
            'id': self.id,
            'node_id': self.node_id,
            # Node-Metadaten für die UI ---
            'vault_id': self.node.vault_id,  # Wird für Aktionen (save, delete) benötigt
            'icon': self.node.icon,  # Kosmetisch, aber nützlich für die Anzeige
            # Die AI Summary vom übergeordneten Node holen +++
            'ai_summary': self.node.ai_summary,
            'summary_is_current': self.node.summary_is_current,
            # --- Versions-spezifische Daten ---
            'title': self.title,  # Das neue, versionierte Titelfeld
            'version': self.version,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'author_id': self.author_id,
            'author_name': self.author.display_name if self.author else "Unknown",
        }

        if include_content:
            data['content'] = self.content
        else:
            data['content'] = None

        return data


class VaultAccess(db.Model):
    __tablename__ = 'vault_access'
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey('vaults.id'), primary_key=True)
    role     = db.Column(db.String(10), nullable=False, default='editor')
    # 'editor' is all you need for now. 'viewer' can come later if ever.

class Task(db.Model):
    __tablename__ = 'tasks'

    id               = db.Column(db.String(36), primary_key=True,
                                 default=lambda: str(uuid.uuid4()))
    vault_id         = db.Column(db.Integer, db.ForeignKey('vaults.id'),
                                 nullable=False, index=True)
    instruction      = db.Column(db.Text, nullable=False)
    status           = db.Column(db.String(20), nullable=False,
                                 default='pending', index=True)
                                 # 'pending' | 'processing' | 'completed' | 'failed'
    context_node_ids = db.Column(db.JSON, nullable=False, default=list)
    created_at       = db.Column(db.DateTime, nullable=False,
                                 default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id':               self.id,
            'vault_id':         self.vault_id,
            'instruction':      self.instruction,
            'status':           self.status,
            'context_node_ids': self.context_node_ids,
            'created_at':       self.created_at.isoformat(),
        }
