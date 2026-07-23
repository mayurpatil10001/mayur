"""Add verification_trades table for isolated re-parse audit

Revision ID: a1b2c3d4e5f6
Revises: f797182a59ef
Create Date: 2026-07-22 02:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f797182a59ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Isolated table for full re-parse verification
    op.create_table(
        'verification_trades',
        sa.Column('trade_id', sa.String(length=50), primary_key=True),
        sa.Column('account_name', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('entry_time', sa.String(length=40), nullable=False),
        sa.Column('exit_time', sa.String(length=40), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('profit_loss', sa.Float(), nullable=False),
        sa.Column('commission', sa.Float(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('hour_of_day', sa.Integer(), nullable=True),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('minute_of_hour_ny', sa.Integer(), nullable=True),
        sa.Column('trip_id', sa.String(length=100), nullable=True),
        sa.Column('source_file', sa.String(length=255), nullable=True)
    )
    op.create_index('idx_verif_trades_acc_sym', 'verification_trades', ['account_name', 'symbol'])
    op.create_index('idx_verif_trades_time', 'verification_trades', ['entry_time'])


def downgrade() -> None:
    op.drop_index('idx_verif_trades_time', table_name='verification_trades')
    op.drop_index('idx_verif_trades_acc_sym', table_name='verification_trades')
    op.drop_table('verification_trades')
