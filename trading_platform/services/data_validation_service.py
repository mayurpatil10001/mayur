#!/usr/bin/env python3
"""
Data validation service for comprehensive import validation and reporting.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from statistics import mean, median, stdev

from trading_platform.repositories.sierra_chart_repository import SierraChartRepository

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    message: str
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    details: Dict[str, Any] = None


@dataclass
class DataQualityMetrics:
    """Data quality metrics for imported trades."""
    total_trades: int
    unique_trade_ids: int
    duplicate_count: int
    accounts: List[str]
    symbols: List[str]
    date_range: Tuple[str, str]
    profit_loss_stats: Dict[str, float]
    trade_duration_stats: Dict[str, float]
    validation_results: List[ValidationResult]
    quality_score: float


class DataValidationService:
    """Service for comprehensive data validation and reporting."""

    def __init__(self):
        """Initialize the validation service."""
        self.repository = SierraChartRepository()
        self.validation_thresholds = {
            "min_trades_per_account": 10,
            "max_duplicate_percentage": 5.0,
            "min_profit_loss_range": 100.0,
            "max_trade_duration_hours": 24,
            "min_trade_duration_seconds": 1,
            "expected_symbols": ["NQ", "FDAX", "ES", "CL", "GC"],
            "expected_account_patterns": ["IPS_TM_", "TM_", "TS_", "PB_"],
        }

    def validate_import_data(self, limit: Optional[int] = None) -> DataQualityMetrics:
        """Perform comprehensive validation of imported trade data.

        Args:
            limit: Optional limit on number of trades to validate

        Returns:
            DataQualityMetrics with validation results
        """
        logger.info("Starting comprehensive data validation")
        
        # Get trade data
        trades = self._get_trade_data(limit)
        if not trades:
            return self._create_empty_metrics("No trades found in database")

        # Run all validation checks
        validation_results = []
        validation_results.extend(self._validate_data_completeness(trades))
        validation_results.extend(self._validate_data_consistency(trades))
        validation_results.extend(self._validate_business_rules(trades))
        validation_results.extend(self._validate_data_quality(trades))
        validation_results.extend(self._validate_against_known_patterns(trades))

        # Calculate metrics
        metrics = self._calculate_quality_metrics(trades, validation_results)
        
        logger.info(f"Validation complete. Quality score: {metrics.quality_score:.2f}")
        return metrics

    def _get_trade_data(self, limit: Optional[int] = None) -> List[Dict]:
        """Get trade data from database.

        Args:
            limit: Optional limit on number of trades

        Returns:
            List of trade records as dictionaries
        """
        try:
            query = "SELECT * FROM sierra_chart_trades ORDER BY entry_datetime"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = self.repository.connection.cursor()
            cursor.execute(query)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching trade data: {e}")
            return []

    def _validate_data_completeness(self, trades: List[Dict]) -> List[ValidationResult]:
        """Validate data completeness."""
        results = []
        
        # Check for required fields
        required_fields = [
            "trade_id", "account", "symbol", "entry_datetime", "exit_datetime",
            "entry_price", "exit_price", "trade_quantity", "profit_loss"
        ]
        
        missing_data_count = 0
        for trade in trades:
            for field in required_fields:
                if trade.get(field) is None or trade.get(field) == "":
                    missing_data_count += 1
                    break
        
        if missing_data_count == 0:
            results.append(ValidationResult(
                "data_completeness",
                True,
                "All trades have complete required data",
                "INFO"
            ))
        else:
            percentage = (missing_data_count / len(trades)) * 100
            results.append(ValidationResult(
                "data_completeness",
                percentage < 1.0,
                f"{missing_data_count} trades ({percentage:.2f}%) have missing required data",
                "WARNING" if percentage < 5.0 else "ERROR"
            ))
        
        return results

    def _validate_data_consistency(self, trades: List[Dict]) -> List[ValidationResult]:
        """Validate data consistency."""
        results = []
        
        # Check for duplicate trade IDs
        trade_ids = [trade["trade_id"] for trade in trades]
        unique_ids = set(trade_ids)
        duplicate_count = len(trade_ids) - len(unique_ids)
        
        if duplicate_count == 0:
            results.append(ValidationResult(
                "duplicate_trade_ids",
                True,
                "No duplicate trade IDs found",
                "INFO"
            ))
        else:
            percentage = (duplicate_count / len(trades)) * 100
            results.append(ValidationResult(
                "duplicate_trade_ids",
                percentage < self.validation_thresholds["max_duplicate_percentage"],
                f"{duplicate_count} duplicate trade IDs ({percentage:.2f}%)",
                "WARNING" if percentage < 5.0 else "ERROR"
            ))
        
        # Check datetime consistency
        invalid_datetime_count = 0
        for trade in trades:
            try:
                entry_dt = datetime.fromisoformat(trade["entry_datetime"].replace("Z", "+00:00"))
                exit_dt = datetime.fromisoformat(trade["exit_datetime"].replace("Z", "+00:00"))
                if exit_dt <= entry_dt:
                    invalid_datetime_count += 1
            except Exception:
                invalid_datetime_count += 1
        
        if invalid_datetime_count == 0:
            results.append(ValidationResult(
                "datetime_consistency",
                True,
                "All trades have valid entry/exit datetime sequences",
                "INFO"
            ))
        else:
            percentage = (invalid_datetime_count / len(trades)) * 100
            results.append(ValidationResult(
                "datetime_consistency",
                percentage < 1.0,
                f"{invalid_datetime_count} trades ({percentage:.2f}%) have invalid datetime sequences",
                "ERROR"
            ))
        
        return results

    def _validate_business_rules(self, trades: List[Dict]) -> List[ValidationResult]:
        """Validate business rules."""
        results = []
        
        # Check trade quantities are positive
        invalid_quantity_count = sum(1 for trade in trades if trade["trade_quantity"] <= 0)
        
        if invalid_quantity_count == 0:
            results.append(ValidationResult(
                "positive_quantities",
                True,
                "All trades have positive quantities",
                "INFO"
            ))
        else:
            percentage = (invalid_quantity_count / len(trades)) * 100
            results.append(ValidationResult(
                "positive_quantities",
                percentage < 1.0,
                f"{invalid_quantity_count} trades ({percentage:.2f}%) have invalid quantities",
                "ERROR"
            ))
        
        # Check reasonable price ranges
        unreasonable_price_count = 0
        for trade in trades:
            entry_price = trade["entry_price"]
            exit_price = trade["exit_price"]
            if entry_price <= 0 or exit_price <= 0 or entry_price > 100000 or exit_price > 100000:
                unreasonable_price_count += 1
        
        if unreasonable_price_count == 0:
            results.append(ValidationResult(
                "reasonable_prices",
                True,
                "All trades have reasonable price ranges",
                "INFO"
            ))
        else:
            percentage = (unreasonable_price_count / len(trades)) * 100
            results.append(ValidationResult(
                "reasonable_prices",
                percentage < 1.0,
                f"{unreasonable_price_count} trades ({percentage:.2f}%) have unreasonable prices",
                "WARNING"
            ))
        
        return results

    def _validate_data_quality(self, trades: List[Dict]) -> List[ValidationResult]:
        """Validate data quality metrics."""
        results = []
        
        # Check account distribution
        accounts = {}
        for trade in trades:
            account = trade["account"]
            accounts[account] = accounts.get(account, 0) + 1
        
        min_trades = self.validation_thresholds["min_trades_per_account"]
        low_volume_accounts = [acc for acc, count in accounts.items() if count < min_trades]
        
        if not low_volume_accounts:
            results.append(ValidationResult(
                "account_distribution",
                True,
                f"All accounts have sufficient trade volume (>{min_trades} trades)",
                "INFO"
            ))
        else:
            results.append(ValidationResult(
                "account_distribution",
                len(low_volume_accounts) < len(accounts) * 0.5,
                f"{len(low_volume_accounts)} accounts have low trade volume (<{min_trades} trades)",
                "WARNING"
            ))
        
        # Check symbol coverage
        symbols = set(trade["base_symbol"] for trade in trades)
        expected_symbols = set(self.validation_thresholds["expected_symbols"])
        missing_symbols = expected_symbols - symbols
        
        if not missing_symbols:
            results.append(ValidationResult(
                "symbol_coverage",
                True,
                "All expected symbols are present in the data",
                "INFO"
            ))
        else:
            results.append(ValidationResult(
                "symbol_coverage",
                len(missing_symbols) < len(expected_symbols) * 0.5,
                f"Missing expected symbols: {list(missing_symbols)}",
                "WARNING"
            ))
        
        return results

    def _validate_against_known_patterns(self, trades: List[Dict]) -> List[ValidationResult]:
        """Validate against known trading patterns."""
        results = []
        
        # Check account naming patterns
        expected_patterns = self.validation_thresholds["expected_account_patterns"]
        accounts = set(trade["account"] for trade in trades)
        
        pattern_matches = 0
        for account in accounts:
            if any(pattern in account for pattern in expected_patterns):
                pattern_matches += 1
        
        pattern_percentage = (pattern_matches / len(accounts)) * 100 if accounts else 0
        
        results.append(ValidationResult(
            "account_naming_patterns",
            pattern_percentage > 80,
            f"{pattern_percentage:.1f}% of accounts match expected naming patterns",
            "INFO" if pattern_percentage > 90 else "WARNING"
        ))
        
        # Check for reasonable profit/loss distribution
        profit_losses = [trade["profit_loss"] for trade in trades if trade["profit_loss"] is not None]
        if profit_losses:
            positive_trades = sum(1 for pl in profit_losses if pl > 0)
            win_rate = (positive_trades / len(profit_losses)) * 100
            
            results.append(ValidationResult(
                "profit_loss_distribution",
                20 <= win_rate <= 80,
                f"Win rate: {win_rate:.1f}% ({positive_trades}/{len(profit_losses)} trades)",
                "INFO" if 30 <= win_rate <= 70 else "WARNING"
            ))
        
        return results

    def _calculate_quality_metrics(self, trades: List[Dict], validation_results: List[ValidationResult]) -> DataQualityMetrics:
        """Calculate comprehensive quality metrics."""
        
        # Basic counts
        total_trades = len(trades)
        trade_ids = [trade["trade_id"] for trade in trades]
        unique_trade_ids = len(set(trade_ids))
        duplicate_count = total_trades - unique_trade_ids
        
        # Account and symbol analysis
        accounts = sorted(set(trade["account"] for trade in trades))
        symbols = sorted(set(trade["base_symbol"] for trade in trades if trade["base_symbol"]))
        
        # Date range
        dates = []
        for trade in trades:
            try:
                entry_dt = datetime.fromisoformat(trade["entry_datetime"].replace("Z", "+00:00"))
                dates.append(entry_dt)
            except Exception:
                continue
        
        date_range = (
            min(dates).strftime("%Y-%m-%d") if dates else "N/A",
            max(dates).strftime("%Y-%m-%d") if dates else "N/A"
        )
        
        # Profit/Loss statistics
        profit_losses = [trade["profit_loss"] for trade in trades if trade["profit_loss"] is not None]
        profit_loss_stats = {}
        if profit_losses:
            profit_loss_stats = {
                "mean": mean(profit_losses),
                "median": median(profit_losses),
                "std_dev": stdev(profit_losses) if len(profit_losses) > 1 else 0,
                "min": min(profit_losses),
                "max": max(profit_losses),
                "total": sum(profit_losses),
                "positive_count": sum(1 for pl in profit_losses if pl > 0),
                "negative_count": sum(1 for pl in profit_losses if pl < 0),
                "win_rate": (sum(1 for pl in profit_losses if pl > 0) / len(profit_losses)) * 100
            }
        
        # Trade duration statistics
        durations = []
        for trade in trades:
            try:
                entry_dt = datetime.fromisoformat(trade["entry_datetime"].replace("Z", "+00:00"))
                exit_dt = datetime.fromisoformat(trade["exit_datetime"].replace("Z", "+00:00"))
                duration_seconds = (exit_dt - entry_dt).total_seconds()
                durations.append(duration_seconds)
            except Exception:
                continue
        
        trade_duration_stats = {}
        if durations:
            trade_duration_stats = {
                "mean_seconds": mean(durations),
                "median_seconds": median(durations),
                "std_dev_seconds": stdev(durations) if len(durations) > 1 else 0,
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "mean_minutes": mean(durations) / 60,
                "mean_hours": mean(durations) / 3600
            }
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(validation_results)
        
        return DataQualityMetrics(
            total_trades=total_trades,
            unique_trade_ids=unique_trade_ids,
            duplicate_count=duplicate_count,
            accounts=accounts,
            symbols=symbols,
            date_range=date_range,
            profit_loss_stats=profit_loss_stats,
            trade_duration_stats=trade_duration_stats,
            validation_results=validation_results,
            quality_score=quality_score
        )

    def _calculate_quality_score(self, validation_results: List[ValidationResult]) -> float:
        """Calculate overall quality score from validation results."""
        if not validation_results:
            return 0.0
        
        # Weight scores by severity
        severity_weights = {
            "INFO": 1.0,
            "WARNING": 0.7,
            "ERROR": 0.3,
            "CRITICAL": 0.0
        }
        
        total_weight = 0
        weighted_score = 0
        
        for result in validation_results:
            weight = severity_weights.get(result.severity, 0.5)
            score = 1.0 if result.passed else 0.0
            weighted_score += score * weight
            total_weight += weight
        
        return (weighted_score / total_weight * 100) if total_weight > 0 else 0.0

    def _create_empty_metrics(self, message: str) -> DataQualityMetrics:
        """Create empty metrics with error message."""
        return DataQualityMetrics(
            total_trades=0,
            unique_trade_ids=0,
            duplicate_count=0,
            accounts=[],
            symbols=[],
            date_range=("N/A", "N/A"),
            profit_loss_stats={},
            trade_duration_stats={},
            validation_results=[ValidationResult("no_data", False, message, "CRITICAL")],
            quality_score=0.0
        )

    def generate_validation_report(self, metrics: DataQualityMetrics, output_path: Optional[str] = None) -> str:
        """Generate a comprehensive validation report.

        Args:
            metrics: Data quality metrics
            output_path: Optional path to save the report

        Returns:
            Report as a string
        """
        report_lines = [
            "=" * 80,
            "COMPREHENSIVE DATA VALIDATION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Quality Score: {metrics.quality_score:.2f}/100",
            "",
            "SUMMARY STATISTICS",
            "-" * 40,
            f"Total Trades: {metrics.total_trades:,}",
            f"Unique Trade IDs: {metrics.unique_trade_ids:,}",
            f"Duplicate Count: {metrics.duplicate_count:,}",
            f"Accounts: {len(metrics.accounts)} ({', '.join(metrics.accounts[:5])}{'...' if len(metrics.accounts) > 5 else ''})",
            f"Symbols: {len(metrics.symbols)} ({', '.join(metrics.symbols)})",
            f"Date Range: {metrics.date_range[0]} to {metrics.date_range[1]}",
            "",
        ]
        
        # Profit/Loss Statistics
        if metrics.profit_loss_stats:
            pls = metrics.profit_loss_stats
            report_lines.extend([
                "PROFIT/LOSS STATISTICS",
                "-" * 40,
                f"Total P&L: ${pls.get('total', 0):,.2f}",
                f"Mean P&L: ${pls.get('mean', 0):,.2f}",
                f"Median P&L: ${pls.get('median', 0):,.2f}",
                f"Std Dev: ${pls.get('std_dev', 0):,.2f}",
                f"Min P&L: ${pls.get('min', 0):,.2f}",
                f"Max P&L: ${pls.get('max', 0):,.2f}",
                f"Win Rate: {pls.get('win_rate', 0):.1f}% ({pls.get('positive_count', 0)}/{pls.get('positive_count', 0) + pls.get('negative_count', 0)})",
                "",
            ])
        
        # Trade Duration Statistics
        if metrics.trade_duration_stats:
            tds = metrics.trade_duration_stats
            report_lines.extend([
                "TRADE DURATION STATISTICS",
                "-" * 40,
                f"Mean Duration: {tds.get('mean_minutes', 0):.1f} minutes ({tds.get('mean_hours', 0):.2f} hours)",
                f"Median Duration: {tds.get('median_seconds', 0)/60:.1f} minutes",
                f"Min Duration: {tds.get('min_seconds', 0):.0f} seconds",
                f"Max Duration: {tds.get('max_seconds', 0)/3600:.1f} hours",
                "",
            ])
        
        # Validation Results
        report_lines.extend([
            "VALIDATION RESULTS",
            "-" * 40,
        ])
        
        # Group by severity
        by_severity = {}
        for result in metrics.validation_results:
            severity = result.severity
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(result)
        
        for severity in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
            if severity in by_severity:
                report_lines.append(f"\n{severity}:")
                for result in by_severity[severity]:
                    status = "✓" if result.passed else "✗"
                    report_lines.append(f"  {status} {result.check_name}: {result.message}")
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        report_text = "\n".join(report_lines)
        
        # Save to file if requested
        if output_path:
            try:
                Path(output_path).write_text(report_text, encoding="utf-8")
                logger.info(f"Validation report saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving report to {output_path}: {e}")
        
        return report_text

    def save_metrics_json(self, metrics: DataQualityMetrics, output_path: str) -> None:
        """Save metrics to JSON file.

        Args:
            metrics: Data quality metrics to save
            output_path: Path to save the JSON file
        """
        try:
            # Convert to dictionary and handle datetime serialization
            metrics_dict = asdict(metrics)
            
            # Convert ValidationResult objects to dictionaries
            metrics_dict["validation_results"] = [
                asdict(result) for result in metrics.validation_results
            ]
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(metrics_dict, f, indent=2, default=str)
            
            logger.info(f"Metrics saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving metrics to {output_path}: {e}")