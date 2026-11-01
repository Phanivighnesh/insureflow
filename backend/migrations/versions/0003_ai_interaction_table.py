"""ai interaction table

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('ai_interactions',
    sa.Column('interaction_id', sa.String(length=24), nullable=False),
    sa.Column('user_id', sa.String(length=48), nullable=False),
    sa.Column('role', sa.String(length=24), nullable=False),
    sa.Column('question', sa.String(length=500), nullable=False),
    sa.Column('intent', sa.String(length=40), nullable=False),
    sa.Column('record_refs', sa.JSON(), nullable=True),
    sa.Column('provider', sa.String(length=24), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=True),
    sa.Column('used_fallback', sa.Boolean(), nullable=False),
    sa.Column('fallback_reason', sa.String(length=120), nullable=True),
    sa.Column('guard_result', sa.JSON(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('prompt_version', sa.String(length=24), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('interaction_id')
    )
    op.create_index(op.f('ix_ai_interactions_intent'), 'ai_interactions', ['intent'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_interactions_intent'), table_name='ai_interactions')
    op.drop_table('ai_interactions')

