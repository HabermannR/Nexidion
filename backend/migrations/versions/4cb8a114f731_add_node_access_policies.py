"""add node access policies

Revision ID: 4cb8a114f731
Revises: f28a6c35d914
"""
from alembic import op
import sqlalchemy as sa

revision = "4cb8a114f731"
down_revision = "f28a6c35d914"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("nodes") as batch_op:
        batch_op.add_column(sa.Column("ai_read_policy", sa.String(20), nullable=False, server_default="allow"))
        batch_op.add_column(sa.Column("ai_write_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("human_write_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("policy_note", sa.Text(), nullable=True))
    op.execute("UPDATE nodes SET ai_write_locked = true WHERE icon = 'bxs-lock-alt'")
    op.execute("UPDATE nodes SET ai_read_policy = 'deny', ai_write_locked = true WHERE icon = 'bxs-no-entry'")
    op.execute("UPDATE vaults SET cached_ui_tree = NULL, cached_ui_tree_etag = NULL, cached_agent_tree = NULL, cached_agent_tree_etag = NULL")
    with op.batch_alter_table("nodes") as batch_op:
        batch_op.create_check_constraint(
            "ck_nodes_ai_read_policy", "ai_read_policy IN ('allow', 'explicit_only', 'deny')"
        )


def downgrade():
    with op.batch_alter_table("nodes") as batch_op:
        batch_op.drop_constraint("ck_nodes_ai_read_policy", type_="check")
        batch_op.drop_column("policy_note")
        batch_op.drop_column("human_write_locked")
        batch_op.drop_column("ai_write_locked")
        batch_op.drop_column("ai_read_policy")
