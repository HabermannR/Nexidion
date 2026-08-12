"""add ingestion connectors and execution identity

Revision ID: c81d0af728a1
Revises: e61437fc8b9a
"""
from alembic import op
import sqlalchemy as sa

revision = 'c81d0af728a1'
down_revision = 'e61437fc8b9a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('requested_by_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('executed_by_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_tasks_requested_by', 'users', ['requested_by_id'], ['id'])
        batch.create_foreign_key('fk_tasks_executed_by', 'users', ['executed_by_id'], ['id'])
        batch.create_index('ix_tasks_requested_by_id', ['requested_by_id'])
        batch.create_index('ix_tasks_executed_by_id', ['executed_by_id'])
    op.execute('UPDATE tasks SET requested_by_id = (SELECT owner_id FROM vaults WHERE vaults.id = tasks.vault_id)')

    op.create_table('connector_installations',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('vault_id', sa.Integer(), nullable=False),
        sa.Column('plugin_name', sa.String(120), nullable=False), sa.Column('name', sa.String(255), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False), sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('credential_ref', sa.String(255)), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.UniqueConstraint('vault_id', 'name', name='uq_connector_name_per_vault'))
    op.create_index('ix_connector_installations_vault_id', 'connector_installations', ['vault_id'])
    op.create_table('ingestion_runs',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('connector_id', sa.String(36), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=False), sa.Column('executed_by_id', sa.Integer()),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('stats', sa.JSON(), nullable=False),
        sa.Column('error', sa.Text()), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_installations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']), sa.ForeignKeyConstraint(['executed_by_id'], ['users.id']))
    op.create_index('ix_ingestion_runs_connector_id', 'ingestion_runs', ['connector_id'])
    op.create_index('ix_ingestion_runs_status', 'ingestion_runs', ['status'])
    op.create_table('source_items',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('connector_id', sa.String(36), nullable=False),
        sa.Column('external_id', sa.String(1024), nullable=False), sa.Column('node_id', sa.String(36)),
        sa.Column('source_uri', sa.Text()), sa.Column('source_version', sa.String(255)),
        sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('policy', sa.String(20), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False), sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_installations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('connector_id', 'external_id', name='uq_source_item_external_id'))
    op.create_index('ix_source_items_connector_id', 'source_items', ['connector_id'])
    op.create_index('ix_source_items_node_id', 'source_items', ['node_id'])


def downgrade():
    op.drop_table('source_items')
    op.drop_table('ingestion_runs')
    op.drop_table('connector_installations')
    with op.batch_alter_table('tasks') as batch:
        batch.drop_column('executed_by_id')
        batch.drop_column('requested_by_id')
