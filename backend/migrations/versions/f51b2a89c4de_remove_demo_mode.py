"""remove demo mode

Revision ID: f51b2a89c4de
Revises: d92bc1405d0e

Former guest users and their vaults are deliberately retained. Dropping the
guest marker turns those rows into ordinary human accounts; accounts without
a usable password remain unable to authenticate until an administrator resets
their password or deletes them.
"""
from alembic import op
import sqlalchemy as sa


revision = "f51b2a89c4de"
down_revision = "d92bc1405d0e"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("demo_events")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("demo_remap")
        batch.drop_column("guest_token")
        batch.drop_column("expires_at")
        batch.drop_column("demo_state")
        batch.drop_column("is_guest")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch.add_column(sa.Column("demo_state", sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("guest_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("demo_remap", sa.JSON(), nullable=True))
        batch.create_unique_constraint("uq_users_guest_token", ["guest_token"])

    op.create_table(
        "demo_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_demo_events_event_type", "demo_events", ["event_type"])
