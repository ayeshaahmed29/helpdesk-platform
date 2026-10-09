"""create invites table

Revision ID: c7e1f4a92b36
Revises: 3b2eaa0d8715
Create Date: 2026-10-08 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7e1f4a92b36'
down_revision: str | Sequence[str] | None = '3b2eaa0d8715'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['organization_id'], ['organizations.id'],
            name='fk_invites_organization_id',
        ),
        sa.ForeignKeyConstraint(
            ['invited_by'], ['users.id'],
            name='fk_invites_invited_by',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_invites_organization_id_email',
        'invites',
        ['organization_id', 'email'],
        unique=False,
    )
    op.create_index('ix_invites_token_hash', 'invites', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_invites_token_hash', table_name='invites')
    op.drop_index('ix_invites_organization_id_email', table_name='invites')
    op.drop_table('invites')