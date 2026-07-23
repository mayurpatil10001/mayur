"""Add OOS metrics to walk_forward_results table

Revision ID: f797182a59ef
Revises: e48628dae111
Create Date: 2026-07-21 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f797182a59ef'
down_revision: Union[str, None] = 'e48628dae111'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive columns for OOS metrics required by walk-forward gating
    op.add_column('walk_forward_results', sa.Column('oos_sharpe_ratio', sa.Float(), nullable=True))
    op.add_column('walk_forward_results', sa.Column('oos_max_drawdown', sa.Float(), nullable=True))
    op.add_column('walk_forward_results', sa.Column('oos_avg_pnl_per_trade', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('walk_forward_results', 'oos_avg_pnl_per_trade')
    op.drop_column('walk_forward_results', 'oos_max_drawdown')
    op.drop_column('walk_forward_results', 'oos_sharpe_ratio')
