"""add node and summary provenance

Revision ID: d92bc1405d0e
Revises: c81d0af728a1
"""
from alembic import op
import sqlalchemy as sa

revision = 'd92bc1405d0e'
down_revision = 'c81d0af728a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('nodes') as batch:
        batch.add_column(sa.Column('content_kind', sa.String(32), nullable=False, server_default='note'))
        batch.add_column(sa.Column('authority', sa.String(32), nullable=False, server_default='user_note'))
        batch.add_column(sa.Column('language', sa.String(16)))
        batch.add_column(sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'))
        batch.add_column(sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'))
    with op.batch_alter_table('source_items') as batch:
        batch.add_column(sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False,
                                   server_default=sa.text('CURRENT_TIMESTAMP')))
        batch.add_column(sa.Column('external_modified_at', sa.DateTime(timezone=True)))
        batch.add_column(sa.Column('mime_type', sa.String(255)))
        batch.add_column(sa.Column('sync_status', sa.String(20), nullable=False, server_default='current'))
    op.create_table('summary_artifacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36), nullable=False),
        sa.Column('source_content_hash', sa.String(64), nullable=False),
        sa.Column('summary', sa.Text()), sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('model', sa.String(255)), sa.Column('prompt_version', sa.String(64), nullable=False),
        sa.Column('visual_mode', sa.String(16), nullable=False),
        sa.Column('used_vision', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('error', sa.Text()),
        sa.Column('requested_by_id', sa.Integer()), sa.Column('executed_by_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['executed_by_id'], ['users.id']))
    op.create_index('ix_summary_artifacts_node_id', 'summary_artifacts', ['node_id'])
    op.create_index('ix_summary_artifacts_source_content_hash', 'summary_artifacts', ['source_content_hash'])
    op.create_index('ix_summary_artifacts_status', 'summary_artifacts', ['status'])


def downgrade():
    op.drop_table('summary_artifacts')
    with op.batch_alter_table('source_items') as batch:
        batch.drop_column('sync_status')
        batch.drop_column('mime_type')
        batch.drop_column('external_modified_at')
        batch.drop_column('last_seen_at')
    with op.batch_alter_table('nodes') as batch:
        batch.drop_column('metadata_json')
        batch.drop_column('tags')
        batch.drop_column('language')
        batch.drop_column('authority')
        batch.drop_column('content_kind')
