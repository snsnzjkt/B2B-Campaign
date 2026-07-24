"""add company external_id and provider_search_logs table

Revision ID: f3a6b9c1d0e2
Revises: 02ef149f3566
Create Date: 2026-07-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a6b9c1d0e2'
down_revision: Union[str, Sequence[str], None] = '02ef149f3566'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('companies', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_companies_external_id'), 'companies', ['external_id'], unique=False)

    op.create_table('provider_search_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_search_logs_organization_id'), 'provider_search_logs', ['organization_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_provider_search_logs_organization_id'), table_name='provider_search_logs')
    op.drop_table('provider_search_logs')

    op.drop_index(op.f('ix_companies_external_id'), table_name='companies')
    op.drop_column('companies', 'external_id')
