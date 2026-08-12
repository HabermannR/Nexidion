"""add source artifacts and curation

Revision ID: a73e91dc24bf
Revises: f51b2a89c4de
"""
from alembic import op
import sqlalchemy as sa

revision = 'a73e91dc24bf'
down_revision = 'f51b2a89c4de'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('source_artifacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('connector_id', sa.String(36), nullable=False),
        sa.Column('external_id', sa.String(1024), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('mime_type', sa.String(255), nullable=False),
        sa.Column('source_uri', sa.Text()), sa.Column('payload', sa.LargeBinary()),
        sa.Column('extracted_json', sa.JSON(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_installations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('connector_id', 'external_id', 'content_hash', name='uq_source_artifact_revision'))
    op.create_index('ix_source_artifacts_connector_id', 'source_artifacts', ['connector_id'])
    op.create_index('ix_source_artifacts_content_hash', 'source_artifacts', ['content_hash'])
    op.create_table('curation_jobs',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('artifact_id', sa.String(36), nullable=False),
        sa.Column('vault_id', sa.Integer(), nullable=False), sa.Column('parent_id', sa.String(36)),
        sa.Column('mode', sa.String(32), nullable=False), sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('model', sa.String(255)), sa.Column('visual_mode', sa.String(16), nullable=False),
        sa.Column('prompt_version', sa.String(64), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error', sa.Text()), sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=False), sa.Column('executed_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['artifact_id'], ['source_artifacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['nodes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']), sa.ForeignKeyConstraint(['executed_by_id'], ['users.id']))
    op.create_index('ix_curation_jobs_artifact_id', 'curation_jobs', ['artifact_id'])
    op.create_index('ix_curation_jobs_vault_id', 'curation_jobs', ['vault_id'])
    op.create_index('ix_curation_jobs_status', 'curation_jobs', ['status'])
    op.create_table('node_source_links',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('node_id', sa.String(36), nullable=False),
        sa.Column('artifact_id', sa.String(36), nullable=False), sa.Column('curation_job_id', sa.String(36), nullable=False),
        sa.Column('page_from', sa.Integer()), sa.Column('page_to', sa.Integer()),
        sa.Column('source_content_hash', sa.String(64), nullable=False),
        sa.Column('is_stale', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artifact_id'], ['source_artifacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['curation_job_id'], ['curation_jobs.id'], ondelete='CASCADE'))
    op.create_index('ix_node_source_links_node_id', 'node_source_links', ['node_id'])
    op.create_index('ix_node_source_links_artifact_id', 'node_source_links', ['artifact_id'])
    op.create_index('ix_node_source_links_curation_job_id', 'node_source_links', ['curation_job_id'])


def downgrade():
    op.drop_table('node_source_links')
    op.drop_table('curation_jobs')
    op.drop_table('source_artifacts')
