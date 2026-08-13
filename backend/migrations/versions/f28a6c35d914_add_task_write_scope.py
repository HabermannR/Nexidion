"""add task write scope

Revision ID: f28a6c35d914
Revises: ed6bb5901e31
"""

from alembic import op
import sqlalchemy as sa


revision = "f28a6c35d914"
down_revision = "ed6bb5901e31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("allowed_write_node_ids", sa.JSON(), nullable=True))
    op.add_column("tasks", sa.Column("allowed_write_operations", sa.JSON(), nullable=True))
    op.execute("UPDATE vaults SET cached_ui_tree = NULL, cached_ui_tree_etag = NULL, cached_agent_tree = NULL, cached_agent_tree_etag = NULL")


def downgrade():
    op.drop_column("tasks", "allowed_write_operations")
    op.drop_column("tasks", "allowed_write_node_ids")
