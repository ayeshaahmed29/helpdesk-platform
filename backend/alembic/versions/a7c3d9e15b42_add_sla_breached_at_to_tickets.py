"""add_sla_breached_at_to_tickets

Revision ID: a7c3d9e15b42
Revises: ecbbd1e319cb
Create Date: 2026-10-14 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c3d9e15b42'
down_revision: str | Sequence[str] | None = 'ecbbd1e319cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable, so no backfill is needed: NULL means "not breached".
    op.add_column(
        'tickets',
        sa.Column('sla_breached_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tickets', 'sla_breached_at')