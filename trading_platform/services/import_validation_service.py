#!/usr/bin/env python3
"""
Comprehensive data import validation and reporting service.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict

from ..database.connection import DatabaseManager
from ..utils.validators import ValidationError


@dataclass
class ImportValidationResult:
    """Results of import validation."""
    validation_id: str
    timestamp: datetime
    total_records: int
    valid_records: int
    invalid_records: int
    validation_rate: float
    data_quality_score: float
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    recommendations: List[str]


@dataclass
class DataQualityMetrics:
    """Data quality metrics for import validation."""
    completeness_score: float
    accuracy_score: float
    consistency_score: float
    timeliness_score: float
    uniqueness_score: float
    overall_score: float


class ImportValidationService:
    """Service for comprehensive data import validation and reporting."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize the validation service."""
        self.db = db_manager or DatabaseManager()
        self.logger = logging.getLogger(__name__)
        
        # Quality thresholds
        self.quality_thresholds = {
            'min_completeness': 0.95,  # 95% of expected data present
            'min_accuracy': 0.98,      # 98% of data passes validation
            'min_consistency': 0.99,   # 99% consistency in data formats
            'min_timeliness': 0.90,    # 90% of data is recent/relevant
            'min_uniqueness': 0.999,   # 99.9% unique records
            'min_overall': 0.95        # 95% overall quality score
        }
        
        # Expected data structure
        self.expected_structure = {
            'symbols': ['NQ', 'ES', 'FD', 'CL'],
            'min_accounts': 40,
            'max_accounts': 50,
            'required_fields': [
                'trade_id', 'account_name', 'symbol', 'entry_time', 'exit_time',
                'entry_price', 'exit_price', 'quantity', 'side', 'profit_loss',
                'commission', 'duration_minutes', 'hour_of_day', 'day_of_week'
            ]
        }
    
    def validate_import(self, validation_id: Optional[str] = None) -> ImportValidationResult:
        """
        Perform comprehensive validation of imported data.
        
        Args:
            validation_id: Optional validation identifier
            
        Returns:
            ImportValidationResult with detailed validation results
        """
        if not validation_id:
            validation_id = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(f"Starting comprehensive import validation: {validation_id}")
        
        try:
            # Get basic statistics
            basic_stats = self._get_basic_statistics()
            
            # Validate data structure
            structure_issues = self._validate_data_structure()
            
            # Validate data quality
            quality_metrics = self._calculate_data_quality_metrics()
            
            # Validate business rules
            business_issues = self._validate_business_rules()
            
            # Validate temporal consistency
            temporal_issues = self._validate_temporal_consistency()
            
            # Validate account integrity
            account_issues = self._validate_account_integrity()
            
            # Combine all issues
            all_issues = structure_issues + business_issues + temporal_issues + account_issues
            
            # Calculate validation rate
            total_records = basic_stats['total_trades']
            invalid_records = len([issue for issue in all_issues if issue['severity'] == 'error'])
            valid_records = total_records - invalid_records
            validation_rate = (valid_records / total_records) if total_records > 0 else 0
            
            # Generate recommendations
            recommendations = self._generate_recommendations(all_issues, quality_metrics)
            
            # Create result
            result = ImportValidationResult(
                validation_id=validation_id,
                timestamp=datetime.now(),
                total_records=total_records,
                valid_records=valid_records,
                invalid_records=invalid_records,
                validation_rate=validation_rate,
                data_quality_score=quality_metrics.overall_score,
                issues=all_issues,
                metrics={
                    'basic_stats': basic_stats,
                    'quality_metrics': asdict(quality_metrics)
                },
                recommendations=recommendations
            )
            
            # Save validation result
            self._save_validation_result(result)
            
            self.logger.info(f"Validation completed: {validation_rate:.1%} success rate")
            return result
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            raise
    
    def _get_basic_statistics(self) -> Dict[str, Any]:
        """Get basic statistics about imported data."""
        stats = {}
        
        # Total trades
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades")
        stats['total_trades'] = result[0]['count']
        
        # Unique symbols
        result = self.db.execute_query("SELECT COUNT(DISTINCT symbol) as count FROM processed_trades")
        stats['unique_symbols'] = result[0]['count']
        
        # Unique accounts
        result = self.db.execute_query("SELECT COUNT(DISTINCT account_name) as count FROM processed_trades")
        stats['unique_accounts'] = result[0]['count']
        
        # Date range
        result = self.db.execute_query("""
            SELECT 
                MIN(entry_time) as earliest_trade,
                MAX(entry_time) as latest_trade
            FROM processed_trades
        """)
        stats['date_range'] = {
            'earliest': result[0]['earliest_trade'],
            'latest': result[0]['latest_trade']
        }
        
        # Symbol distribution
        result = self.db.execute_query("""
            SELECT symbol, COUNT(*) as count 
            FROM processed_trades 
            GROUP BY symbol 
            ORDER BY count DESC
        """)
        stats['symbol_distribution'] = {row['symbol']: row['count'] for row in result}
        
        # Account distribution (top 10)
        result = self.db.execute_query("""
            SELECT account_name, COUNT(*) as count 
            FROM processed_trades 
            GROUP BY account_name 
            ORDER BY count DESC 
            LIMIT 10
        """)
        stats['top_accounts'] = {row['account_name']: row['count'] for row in result}
        
        return stats
    
    def _validate_data_structure(self) -> List[Dict[str, Any]]:
        """Validate data structure against expected format."""
        issues = []
        
        # Check for expected symbols
        result = self.db.execute_query("SELECT DISTINCT symbol FROM processed_trades")
        found_symbols = {row['symbol'] for row in result}
        expected_symbols = set(self.expected_structure['symbols'])
        
        missing_symbols = expected_symbols - found_symbols
        if missing_symbols:
            issues.append({
                'type': 'missing_symbols',
                'severity': 'error',
                'message': f"Missing expected symbols: {', '.join(missing_symbols)}",
                'details': {'missing': list(missing_symbols), 'found': list(found_symbols)}
            })
        
        unexpected_symbols = found_symbols - expected_symbols
        if unexpected_symbols:
            issues.append({
                'type': 'unexpected_symbols',
                'severity': 'warning',
                'message': f"Unexpected symbols found: {', '.join(unexpected_symbols)}",
                'details': {'unexpected': list(unexpected_symbols)}
            })
        
        # Check account count
        result = self.db.execute_query("SELECT COUNT(DISTINCT account_name) as count FROM processed_trades")
        account_count = result[0]['count']
        
        if account_count < self.expected_structure['min_accounts']:
            issues.append({
                'type': 'insufficient_accounts',
                'severity': 'warning',
                'message': f"Only {account_count} accounts found, expected at least {self.expected_structure['min_accounts']}",
                'details': {'found': account_count, 'expected_min': self.expected_structure['min_accounts']}
            })
        elif account_count > self.expected_structure['max_accounts']:
            issues.append({
                'type': 'excessive_accounts',
                'severity': 'info',
                'message': f"{account_count} accounts found, more than expected maximum {self.expected_structure['max_accounts']}",
                'details': {'found': account_count, 'expected_max': self.expected_structure['max_accounts']}
            })
        
        # Check for null values in required fields
        for field in self.expected_structure['required_fields']:
            result = self.db.execute_query(f"SELECT COUNT(*) as count FROM processed_trades WHERE {field} IS NULL")
            null_count = result[0]['count']
            
            if null_count > 0:
                issues.append({
                    'type': 'null_values',
                    'severity': 'error',
                    'message': f"Found {null_count} null values in required field '{field}'",
                    'details': {'field': field, 'null_count': null_count}
                })
        
        return issues
    
    def _calculate_data_quality_metrics(self) -> DataQualityMetrics:
        """Calculate comprehensive data quality metrics."""
        
        # Get total record count
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades")
        total_records = result[0]['count']
        
        if total_records == 0:
            return DataQualityMetrics(0, 0, 0, 0, 0, 0)
        
        # Completeness: Check for missing required data
        completeness_issues = 0
        for field in self.expected_structure['required_fields']:
            result = self.db.execute_query(f"SELECT COUNT(*) as count FROM processed_trades WHERE {field} IS NULL OR {field} = ''")
            completeness_issues += result[0]['count']
        
        completeness_score = max(0, 1 - (completeness_issues / (total_records * len(self.expected_structure['required_fields']))))
        
        # Accuracy: Check for invalid data values
        accuracy_issues = 0
        
        # Invalid prices (negative or zero)
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE entry_price <= 0 OR exit_price <= 0")
        accuracy_issues += result[0]['count']
        
        # Invalid quantities (negative or zero)
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE quantity <= 0")
        accuracy_issues += result[0]['count']
        
        # Invalid time sequences (entry after exit)
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE entry_time >= exit_time")
        accuracy_issues += result[0]['count']
        
        accuracy_score = max(0, 1 - (accuracy_issues / total_records))
        
        # Consistency: Check for consistent data formats
        consistency_issues = 0
        
        # Check side values
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE side NOT IN ('LONG', 'SHORT')")
        consistency_issues += result[0]['count']
        
        # Check hour_of_day range
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE hour_of_day < 0 OR hour_of_day > 23")
        consistency_issues += result[0]['count']
        
        # Check day_of_week range
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE day_of_week < 0 OR day_of_week > 6")
        consistency_issues += result[0]['count']
        
        consistency_score = max(0, 1 - (consistency_issues / total_records))
        
        # Timeliness: Check if data is recent and relevant
        cutoff_date = datetime.now() - timedelta(days=365 * 2)  # 2 years ago
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE entry_time >= ?", (cutoff_date.isoformat(),))
        recent_records = result[0]['count']
        timeliness_score = recent_records / total_records if total_records > 0 else 0
        
        # Uniqueness: Check for duplicate trade IDs
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades")
        total_count = result[0]['count']
        result = self.db.execute_query("SELECT COUNT(DISTINCT trade_id) as count FROM processed_trades")
        unique_count = result[0]['count']
        uniqueness_score = unique_count / total_count if total_count > 0 else 0
        
        # Overall score (weighted average)
        weights = {
            'completeness': 0.25,
            'accuracy': 0.30,
            'consistency': 0.20,
            'timeliness': 0.15,
            'uniqueness': 0.10
        }
        
        overall_score = (
            completeness_score * weights['completeness'] +
            accuracy_score * weights['accuracy'] +
            consistency_score * weights['consistency'] +
            timeliness_score * weights['timeliness'] +
            uniqueness_score * weights['uniqueness']
        )
        
        return DataQualityMetrics(
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            consistency_score=consistency_score,
            timeliness_score=timeliness_score,
            uniqueness_score=uniqueness_score,
            overall_score=overall_score
        )
    
    def _validate_business_rules(self) -> List[Dict[str, Any]]:
        """Validate business rules and trading logic."""
        issues = []
        
        # Check for unrealistic profit/loss values
        result = self.db.execute_query("""
            SELECT COUNT(*) as count 
            FROM processed_trades 
            WHERE ABS(profit_loss) > 10000
        """)
        if result[0]['count'] > 0:
            issues.append({
                'type': 'unrealistic_pnl',
                'severity': 'warning',
                'message': f"Found {result[0]['count']} trades with unrealistic P&L (>$10,000)",
                'details': {'count': result[0]['count']}
            })
        
        # Check for unrealistic trade durations
        result = self.db.execute_query("""
            SELECT COUNT(*) as count 
            FROM processed_trades 
            WHERE duration_minutes > 1440 OR duration_minutes < 0
        """)
        if result[0]['count'] > 0:
            issues.append({
                'type': 'unrealistic_duration',
                'severity': 'warning',
                'message': f"Found {result[0]['count']} trades with unrealistic duration",
                'details': {'count': result[0]['count']}
            })
        
        # Check for missing commission data
        result = self.db.execute_query("SELECT COUNT(*) as count FROM processed_trades WHERE commission = 0")
        if result[0]['count'] > 0:
            issues.append({
                'type': 'missing_commission',
                'severity': 'info',
                'message': f"Found {result[0]['count']} trades with zero commission",
                'details': {'count': result[0]['count']}
            })
        
        return issues
    
    def _validate_temporal_consistency(self) -> List[Dict[str, Any]]:
        """Validate temporal consistency of trade data."""
        issues = []
        
        # Check for trades outside market hours (basic check)
        result = self.db.execute_query("""
            SELECT COUNT(*) as count 
            FROM processed_trades 
            WHERE hour_of_day < 6 OR hour_of_day > 22
        """)
        if result[0]['count'] > 0:
            issues.append({
                'type': 'outside_market_hours',
                'severity': 'info',
                'message': f"Found {result[0]['count']} trades outside typical market hours",
                'details': {'count': result[0]['count']}
            })
        
        # Check for weekend trading
        result = self.db.execute_query("""
            SELECT COUNT(*) as count 
            FROM processed_trades 
            WHERE day_of_week IN (5, 6)
        """)
        if result[0]['count'] > 0:
            issues.append({
                'type': 'weekend_trading',
                'severity': 'info',
                'message': f"Found {result[0]['count']} trades on weekends",
                'details': {'count': result[0]['count']}
            })
        
        return issues
    
    def _validate_account_integrity(self) -> List[Dict[str, Any]]:
        """Validate account data integrity."""
        issues = []
        
        # Check for accounts trading multiple symbols
        result = self.db.execute_query("""
            SELECT account_name, COUNT(DISTINCT symbol) as symbol_count
            FROM processed_trades
            GROUP BY account_name
            HAVING COUNT(DISTINCT symbol) > 1
        """)
        
        if result:
            multi_symbol_accounts = [row['account_name'] for row in result]
            issues.append({
                'type': 'multi_symbol_accounts',
                'severity': 'info',
                'message': f"Found {len(multi_symbol_accounts)} accounts trading multiple symbols",
                'details': {'accounts': multi_symbol_accounts}
            })
        
        # Check for accounts with very few trades
        result = self.db.execute_query("""
            SELECT account_name, COUNT(*) as trade_count
            FROM processed_trades
            GROUP BY account_name
            HAVING COUNT(*) < 10
        """)
        
        if result:
            low_activity_accounts = [row['account_name'] for row in result]
            issues.append({
                'type': 'low_activity_accounts',
                'severity': 'info',
                'message': f"Found {len(low_activity_accounts)} accounts with very few trades (<10)",
                'details': {'accounts': low_activity_accounts}
            })
        
        return issues
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]], quality_metrics: DataQualityMetrics) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Quality-based recommendations
        if quality_metrics.completeness_score < self.quality_thresholds['min_completeness']:
            recommendations.append("Improve data completeness by addressing missing values in required fields")
        
        if quality_metrics.accuracy_score < self.quality_thresholds['min_accuracy']:
            recommendations.append("Review data validation rules to improve accuracy of imported data")
        
        if quality_metrics.consistency_score < self.quality_thresholds['min_consistency']:
            recommendations.append("Standardize data formats to improve consistency across all records")
        
        if quality_metrics.uniqueness_score < self.quality_thresholds['min_uniqueness']:
            recommendations.append("Implement stronger duplicate detection to ensure data uniqueness")
        
        # Issue-based recommendations
        error_count = len([issue for issue in issues if issue['severity'] == 'error'])
        if error_count > 0:
            recommendations.append(f"Address {error_count} critical data errors before proceeding with analysis")
        
        warning_count = len([issue for issue in issues if issue['severity'] == 'warning'])
        if warning_count > 5:
            recommendations.append(f"Review {warning_count} data warnings to improve overall data quality")
        
        # Overall quality recommendation
        if quality_metrics.overall_score < self.quality_thresholds['min_overall']:
            recommendations.append("Overall data quality is below threshold - consider re-importing with improved validation")
        else:
            recommendations.append("Data quality is acceptable for analysis and reporting")
        
        return recommendations
    
    def _save_validation_result(self, result: ImportValidationResult) -> None:
        """Save validation result to file and database."""
        
        # Save to JSON file
        report_path = Path(f"validation_reports/import_validation_{result.validation_id}.json")
        report_path.parent.mkdir(exist_ok=True)
        
        # Convert result to dict for JSON serialization
        result_dict = asdict(result)
        result_dict['timestamp'] = result.timestamp.isoformat()
        
        with open(report_path, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        self.logger.info(f"Validation report saved to: {report_path}")
    
    def get_validation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of validation results."""
        report_dir = Path("validation_reports")
        if not report_dir.exists():
            return []
        
        validation_files = sorted(
            report_dir.glob("import_validation_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        history = []
        for file_path in validation_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    history.append({
                        'validation_id': data['validation_id'],
                        'timestamp': data['timestamp'],
                        'validation_rate': data['validation_rate'],
                        'data_quality_score': data['data_quality_score'],
                        'total_records': data['total_records'],
                        'issue_count': len(data['issues'])
                    })
            except Exception as e:
                self.logger.warning(f"Failed to load validation history from {file_path}: {e}")
        
        return history
    
    def create_validation_summary_report(self) -> str:
        """Create a human-readable validation summary report."""
        result = self.validate_import()
        
        report = []
        report.append("=" * 80)
        report.append("DATA IMPORT VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Validation ID: {result.validation_id}")
        report.append(f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Overall Results
        report.append("OVERALL RESULTS:")
        report.append(f"Total Records: {result.total_records:,}")
        report.append(f"Valid Records: {result.valid_records:,}")
        report.append(f"Invalid Records: {result.invalid_records:,}")
        report.append(f"Validation Rate: {result.validation_rate:.1%}")
        report.append(f"Data Quality Score: {result.data_quality_score:.1%}")
        report.append("")
        
        # Quality Metrics
        quality_metrics = result.metrics['quality_metrics']
        report.append("DATA QUALITY METRICS:")
        report.append(f"Completeness: {quality_metrics['completeness_score']:.1%}")
        report.append(f"Accuracy: {quality_metrics['accuracy_score']:.1%}")
        report.append(f"Consistency: {quality_metrics['consistency_score']:.1%}")
        report.append(f"Timeliness: {quality_metrics['timeliness_score']:.1%}")
        report.append(f"Uniqueness: {quality_metrics['uniqueness_score']:.1%}")
        report.append("")
        
        # Basic Statistics
        basic_stats = result.metrics['basic_stats']
        report.append("DATA STATISTICS:")
        report.append(f"Unique Symbols: {basic_stats['unique_symbols']}")
        report.append(f"Unique Accounts: {basic_stats['unique_accounts']}")
        report.append(f"Date Range: {basic_stats['date_range']['earliest']} to {basic_stats['date_range']['latest']}")
        report.append("")
        
        # Symbol Distribution
        report.append("SYMBOL DISTRIBUTION:")
        for symbol, count in basic_stats['symbol_distribution'].items():
            report.append(f"  {symbol}: {count:,} trades")
        report.append("")
        
        # Issues
        if result.issues:
            report.append("VALIDATION ISSUES:")
            for issue in result.issues:
                severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue['severity'], "•")
                report.append(f"{severity_icon} {issue['message']}")
            report.append("")
        
        # Recommendations
        if result.recommendations:
            report.append("RECOMMENDATIONS:")
            for i, rec in enumerate(result.recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        # Status
        if result.data_quality_score >= self.quality_thresholds['min_overall']:
            report.append("✅ DATA QUALITY: ACCEPTABLE FOR ANALYSIS")
        else:
            report.append("⚠️ DATA QUALITY: BELOW THRESHOLD - REVIEW REQUIRED")
        
        report.append("=" * 80)
        
        return "\n".join(report)