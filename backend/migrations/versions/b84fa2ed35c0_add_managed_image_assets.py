"""add managed image assets

Revision ID: b84fa2ed35c0
Revises: a73e91dc24bf
"""
from alembic import op
import sqlalchemy as sa

revision = 'b84fa2ed35c0'
down_revision = 'a73e91dc24bf'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('image_assets',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('vault_id', sa.Integer(), nullable=False),
        sa.Column('source_artifact_id', sa.String(36)), sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('storage_key', sa.String(255), nullable=False, unique=True),
        sa.Column('original_filename', sa.String(255)), sa.Column('media_type', sa.String(100), nullable=False),
        sa.Column('width', sa.Integer()), sa.Column('height', sa.Integer()), sa.Column('page_number', sa.Integer()),
        sa.Column('created_by_id', sa.Integer(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_artifact_id'], ['source_artifacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.UniqueConstraint('vault_id', 'content_hash', name='uq_image_asset_hash_per_vault'))
    op.create_index('ix_image_assets_vault_id', 'image_assets', ['vault_id'])
    op.create_index('ix_image_assets_source_artifact_id', 'image_assets', ['source_artifact_id'])
    op.create_index('ix_image_assets_content_hash', 'image_assets', ['content_hash'])


def downgrade():
    op.drop_table('image_assets')
