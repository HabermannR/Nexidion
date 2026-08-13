"""add task LLM provider and model selection

Revision ID: ed6bb5901e31
Revises: b84fa2ed35c0
"""
from alembic import op
import sqlalchemy as sa

revision = "ed6bb5901e31"
down_revision = "b84fa2ed35c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("llm_provider", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("llm_model", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("llm_model")
        batch_op.drop_column("llm_provider")
