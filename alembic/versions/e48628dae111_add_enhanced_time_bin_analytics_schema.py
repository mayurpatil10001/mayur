"""Add enhanced time-bin analytics schema

Revision ID: e48628dae111
Revises: 2869930a34db
Create Date: 2025-08-13 09:50:44.963530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e48628dae111'
down_revision: Union[str, None] = '2869930a34db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Market data table for SPY/QQQ/VIX data storage
    op.create_table('market_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),  # 'SPY', 'QQQ', 'VIX'
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open_price', sa.Float(), nullable=True),
        sa.Column('high_price', sa.Float(), nullable=True),
        sa.Column('low_price', sa.Float(), nullable=True),
        sa.Column('close_price', sa.Float(), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('adjusted_close', sa.Float(), nullable=True),
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'date', name='uq_market_data_symbol_date')
    )
    
    # VIX volatility regimes table
    op.create_table('volatility_regimes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('regime_name', sa.String(length=20), nullable=False),  # 'Low', 'Medium', 'High'
        sa.Column('avg_vix', sa.Float(), nullable=False),
        sa.Column('min_vix', sa.Float(), nullable=False),
        sa.Column('max_vix', sa.Float(), nullable=False),
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Time-bin analysis table for performance metrics
    op.create_table('time_bin_analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_name', sa.String(length=50), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('minute_bin', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=True),  # NULL for all days
        sa.Column('analysis_date', sa.Date(), nullable=False),
        
        # Performance metrics
        sa.Column('total_trades', sa.Integer(), nullable=False),
        sa.Column('win_rate', sa.Float(), nullable=False),
        sa.Column('average_pnl', sa.Float(), nullable=False),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=False),
        sa.Column('profit_factor', sa.Float(), nullable=False),
        
        # Statistical significance
        sa.Column('confidence_interval_lower', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper', sa.Float(), nullable=True),
        sa.Column('p_value_vs_random', sa.Float(), nullable=True),
        sa.Column('statistical_significance', sa.Boolean(), nullable=True),
        sa.Column('sample_size_adequate', sa.Boolean(), nullable=True),
        
        # Market correlation
        sa.Column('spy_correlation', sa.Float(), nullable=True),
        sa.Column('qqq_correlation', sa.Float(), nullable=True),
        sa.Column('beta_spy', sa.Float(), nullable=True),
        sa.Column('alpha_vs_spy', sa.Float(), nullable=True),
        sa.Column('market_neutrality_p_value', sa.Float(), nullable=True),
        
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_name'], ['accounts.name']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Regime-specific performance
    op.create_table('regime_performance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('time_bin_analysis_id', sa.Integer(), nullable=False),
        sa.Column('regime_name', sa.String(length=20), nullable=False),
        sa.Column('trades_in_regime', sa.Integer(), nullable=False),
        sa.Column('win_rate_in_regime', sa.Float(), nullable=False),
        sa.Column('avg_pnl_in_regime', sa.Float(), nullable=False),
        sa.Column('sharpe_ratio_in_regime', sa.Float(), nullable=True),
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['time_bin_analysis_id'], ['time_bin_analysis.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Walk-forward analysis results
    op.create_table('walk_forward_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('time_bin_analysis_id', sa.Integer(), nullable=False),
        sa.Column('validation_scheme', sa.String(length=20), nullable=False),
        sa.Column('in_sample_start', sa.Date(), nullable=False),
        sa.Column('in_sample_end', sa.Date(), nullable=False),
        sa.Column('out_sample_start', sa.Date(), nullable=False),
        sa.Column('out_sample_end', sa.Date(), nullable=False),
        sa.Column('predicted_performance', sa.Float(), nullable=False),
        sa.Column('actual_performance', sa.Float(), nullable=False),
        sa.Column('prediction_error', sa.Float(), nullable=False),
        sa.Column('trades_in_out_sample', sa.Integer(), nullable=False),
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['time_bin_analysis_id'], ['time_bin_analysis.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Monte Carlo simulation results
    op.create_table('monte_carlo_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('time_bin_analysis_id', sa.Integer(), nullable=False),
        sa.Column('simulation_date', sa.Date(), nullable=False),
        sa.Column('n_scenarios', sa.Integer(), nullable=False),
        sa.Column('var_95', sa.Float(), nullable=False),
        sa.Column('var_99', sa.Float(), nullable=False),
        sa.Column('var_99_9', sa.Float(), nullable=False),
        sa.Column('expected_shortfall_95', sa.Float(), nullable=False),
        sa.Column('expected_return', sa.Float(), nullable=False),
        sa.Column('probability_of_profit', sa.Float(), nullable=False),
        sa.Column('created_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['time_bin_analysis_id'], ['time_bin_analysis.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Export and report tracking
    op.create_table('export_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('time_bin_analysis_id', sa.Integer(), nullable=False),
        sa.Column('export_directory', sa.String(length=500), nullable=False),
        sa.Column('export_config_json', sa.Text(), nullable=False),  # JSON of ExportConfig
        sa.Column('exported_files_json', sa.Text(), nullable=False),  # JSON list of exported files
        sa.Column('pdf_report_path', sa.String(length=500), nullable=True),
        sa.Column('total_trades_exported', sa.Integer(), nullable=False),
        sa.Column('export_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.String(length=100), nullable=True),  # Optional user tracking
        sa.ForeignKeyConstraint(['time_bin_analysis_id'], ['time_bin_analysis.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('pdf_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('export_history_id', sa.Integer(), nullable=False),
        sa.Column('report_title', sa.String(length=200), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size_mb', sa.Float(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('sections_included_json', sa.Text(), nullable=False),  # JSON list of sections
        sa.Column('generation_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['export_history_id'], ['export_history.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for optimal time-bin query performance
    
    # Market data indexes
    op.create_index('idx_market_data_symbol_date', 'market_data', ['symbol', 'date'])
    
    # Volatility regimes indexes
    op.create_index('idx_volatility_regimes_date', 'volatility_regimes', ['start_date', 'end_date'])
    
    # Time-bin analysis indexes
    op.create_index('idx_time_bin_analysis_lookup', 'time_bin_analysis', 
                   ['account_name', 'hour', 'minute_bin', 'day_of_week'])
    op.create_index('idx_time_bin_analysis_date', 'time_bin_analysis', ['analysis_date'])
    op.create_index('idx_time_bin_analysis_performance', 'time_bin_analysis', 
                   ['win_rate', 'sharpe_ratio', 'profit_factor'])
    
    # Regime performance indexes
    op.create_index('idx_regime_performance_lookup', 'regime_performance', 
                   ['time_bin_analysis_id', 'regime_name'])
    
    # Walk-forward results indexes
    op.create_index('idx_walk_forward_timebin', 'walk_forward_results', ['time_bin_analysis_id'])
    op.create_index('idx_walk_forward_scheme', 'walk_forward_results', ['validation_scheme'])
    
    # Monte Carlo results indexes
    op.create_index('idx_monte_carlo_timebin', 'monte_carlo_results', ['time_bin_analysis_id'])
    op.create_index('idx_monte_carlo_date', 'monte_carlo_results', ['simulation_date'])
    
    # Export history indexes
    op.create_index('idx_export_history_timebin', 'export_history', 
                   ['time_bin_analysis_id', 'export_timestamp'])
    op.create_index('idx_export_history_user', 'export_history', ['user_id'])
    
    # PDF reports indexes
    op.create_index('idx_pdf_reports_export', 'pdf_reports', ['export_history_id'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_pdf_reports_export', table_name='pdf_reports')
    op.drop_index('idx_export_history_user', table_name='export_history')
    op.drop_index('idx_export_history_timebin', table_name='export_history')
    op.drop_index('idx_monte_carlo_date', table_name='monte_carlo_results')
    op.drop_index('idx_monte_carlo_timebin', table_name='monte_carlo_results')
    op.drop_index('idx_walk_forward_scheme', table_name='walk_forward_results')
    op.drop_index('idx_walk_forward_timebin', table_name='walk_forward_results')
    op.drop_index('idx_regime_performance_lookup', table_name='regime_performance')
    op.drop_index('idx_time_bin_analysis_performance', table_name='time_bin_analysis')
    op.drop_index('idx_time_bin_analysis_date', table_name='time_bin_analysis')
    op.drop_index('idx_time_bin_analysis_lookup', table_name='time_bin_analysis')
    op.drop_index('idx_volatility_regimes_date', table_name='volatility_regimes')
    op.drop_index('idx_market_data_symbol_date', table_name='market_data')
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('pdf_reports')
    op.drop_table('export_history')
    op.drop_table('monte_carlo_results')
    op.drop_table('walk_forward_results')
    op.drop_table('regime_performance')
    op.drop_table('time_bin_analysis')
    op.drop_table('volatility_regimes')
    op.drop_table('market_data')
