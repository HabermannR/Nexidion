"""add ingestion run lifecycle (queued runs, heartbeats, recovery)

Revision ID: b7d3e2a91c40
Revises: 4cb8a114f731
"""
from alembic import op
import sqlalchemy as sa

revision = "b7d3e2a91c40"
down_revision = "4cb8a114f731"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.add_column(sa.Column("artifact_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("request_json", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_ingestion_runs_artifact", "source_artifacts",
                                    ["artifact_id"], ["id"], ondelete="SET NULL")
    # Runs left 'processing' by a worker that was killed mid-import (the gunicorn
    # 30-second timeout did this to PDF uploads) can never finish; say so.
    op.execute(
        "UPDATE ingestion_runs SET status = 'failed', completed_at = now(), "
        "error = 'Interrupted: the server stopped this import before it finished. Upload the file again.' "
        "WHERE status = 'processing' AND created_at < now() - interval '15 minutes'"
    )


def downgrade():
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.drop_constraint("fk_ingestion_runs_artifact", type_="foreignkey")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("attempts")
        batch_op.drop_column("request_json")
        batch_op.drop_column("artifact_id")
