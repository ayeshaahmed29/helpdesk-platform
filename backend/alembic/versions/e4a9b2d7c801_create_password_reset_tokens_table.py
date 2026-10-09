"""create password_reset_tokens table

Revision ID: e4a9b2d7c801
Revises: 5995e320ab52
Create Date: 2026-10-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e4a9b2d7c801'
down_revision: str | Sequence[str] | None = '5995e320ab52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_password_reset_tokens_user_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_password_reset_tokens_user_id',
        'password_reset_tokens',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        'ix_password_reset_tokens_token_hash',
        'password_reset_tokens',
        ['token_hash'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_password_reset_tokens_token_hash', table_name='password_reset_tokens'
    )
    op.drop_index(
        'ix_password_reset_tokens_user_id', table_name='password_reset_tokens'
    )
    op.drop_table('password_reset_tokens')