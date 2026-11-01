"""widen approval authority id

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('approval_authorities', schema=None) as batch_op:
        batch_op.alter_column('authority_id',
                              existing_type=sa.String(length=24),
                              type_=sa.String(length=48),
                              existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('approval_authorities', schema=None) as batch_op:
        batch_op.alter_column('authority_id',
                              existing_type=sa.String(length=48),
                              type_=sa.String(length=24),
                              existing_nullable=False)

