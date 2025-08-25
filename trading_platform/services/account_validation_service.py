"""
Account and symbol separation validation service for SierraChart data.
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, date
from collections import defaultdict
from dataclasses import dataclass

from ..models.sierra_chart import SierraChartTradeRecord
from ..utils.validators import ValidationError


@dataclass
class AccountMetadata:
    """Metadata extracted from trading account data."""
    account_name: str
    primary_symbol: str
    symbols_traded: Set[str]
    first_trade_date: date
    last_trade_date: date
    total_trades: int
    total_volume: int
    is_active: bool
    validation_warnings: List[str]


@dataclass
class SymbolMetadata:
    """Metadata extracted from symbol trading data."""
    symbol: str
    accounts_trading: Set[str]
    first_trade_date: date
    last_trade_date: date
    total_trades: int
    total_volume: int
    validation_warnings: List[str]


@dataclass
class ValidationViolation:
    """Represents a validation rule violation."""
    violation_type: str
    account: str
    symbol: str
    description: str
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    affected_records: List[SierraChartTradeRecord]


class AccountValidationError(Exception):
    """Exception raised during account validation."""
    pass


class AccountValidationService:
    """Service for validating account and symbol separation rules."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the account validation service."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Validation statistics
        self.validation_stats = {
            'total_records_validated': 0,
            'accounts_analyzed': 0,
            'symbols_analyzed': 0,
            'violations_found': 0,
            'error_violations': 0,
            'warning_violations': 0,
            'info_violations': 0
        }
        
        # Validation results
        self.violations: List[ValidationViolation] = []
        self.account_metadata: Dict[str, AccountMetadata] = {}
        self.symbol_metadata: Dict[str, SymbolMetadata] = {}
    
    def validate_account_symbol_separation(self, records: List[SierraChartTradeRecord]) -> bool:
        """
        Validate that each account trades only one symbol.
        
        Args:
            records: List of SierraChart trade records to validate
            
        Returns:
            True if validation passes, False if violations found
            
        Raises:
            AccountValidationError: If validation fails
        """
        if not records:
            self.logger.warning("No records provided for account validation")
            return True
        
        self.logger.info(f"Starting account/symbol separation validation for {len(records)} records")
        
        try:
            # Reset validation state
            self._reset_validation_state()
            self.validation_stats['total_records_validated'] = len(records)
            
            # Extract account and symbol metadata
            self._extract_metadata(records)
            
            # Perform validation checks
            self._validate_account_symbol_rules(records)
            
            # Update final statistics
            self.validation_stats['accounts_analyzed'] = len(self.account_metadata)
            self.validation_stats['symbols_analyzed'] = len(self.symbol_metadata)
            self.validation_stats['violations_found'] = len(self.violations)
            
            # Count violations by severity
            for violation in self.violations:
                if violation.severity == 'ERROR':
                    self.validation_stats['error_violations'] += 1
                elif violation.severity == 'WARNING':
                    self.validation_stats['warning_violations'] += 1
                else:
                    self.validation_stats['info_violations'] += 1
            
            # Log results
            has_errors = self.validation_stats['error_violations'] > 0
            if has_errors:
                self.logger.error(
                    f"Account validation failed: {self.validation_stats['error_violations']} errors, "
                    f"{self.validation_stats['warning_violations']} warnings found"
                )
            else:
                self.logger.info(
                    f"Account validation passed: {self.validation_stats['warning_violations']} warnings found"
                )
            
            return not has_errors
            
        except Exception as e:
            raise AccountValidationError(f"Account validation failed: {e}")
    
    def _extract_metadata(self, records: List[SierraChartTradeRecord]):
        """
        Extract account and symbol metadata from records.
        
        Args:
            records: List of records to analyze
        """
        # Group records by account and symbol
        account_records = defaultdict(list)
        symbol_records = defaultdict(list)
        
        for record in records:
            account_records[record.trade_account].append(record)
            symbol_records[record.base_symbol].append(record)
        
        # Extract account metadata
        for account_name, account_recs in account_records.items():
            self._extract_account_metadata(account_name, account_recs)
        
        # Extract symbol metadata
        for symbol, symbol_recs in symbol_records.items():
            self._extract_symbol_metadata(symbol, symbol_recs)
    
    def _extract_account_metadata(self, account_name: str, records: List[SierraChartTradeRecord]):
        """
        Extract metadata for a specific account.
        
        Args:
            account_name: Name of the account
            records: Records for this account
        """
        if not records:
            return
        
        # Sort records by date
        sorted_records = sorted(records, key=lambda r: r.date_time)
        
        # Extract basic information
        symbols_traded = {r.base_symbol for r in records}
        primary_symbol = max(symbols_traded, key=lambda s: len([r for r in records if r.base_symbol == s]))
        
        first_trade = sorted_records[0].date_time.date()
        last_trade = sorted_records[-1].date_time.date()
        
        total_trades = len(records)
        total_volume = sum(r.filled_quantity for r in records)
        
        # Determine if account is active (traded in last 30 days)
        days_since_last_trade = (datetime.now().date() - last_trade).days
        is_active = days_since_last_trade <= 30
        
        # Collect validation warnings
        warnings = []
        if len(symbols_traded) > 1:
            warnings.append(f"Account trades multiple symbols: {symbols_traded}")
        
        # Create metadata
        metadata = AccountMetadata(
            account_name=account_name,
            primary_symbol=primary_symbol,
            symbols_traded=symbols_traded,
            first_trade_date=first_trade,
            last_trade_date=last_trade,
            total_trades=total_trades,
            total_volume=total_volume,
            is_active=is_active,
            validation_warnings=warnings
        )
        
        self.account_metadata[account_name] = metadata
    
    def _extract_symbol_metadata(self, symbol: str, records: List[SierraChartTradeRecord]):
        """
        Extract metadata for a specific symbol.
        
        Args:
            symbol: Symbol name
            records: Records for this symbol
        """
        if not records:
            return
        
        # Sort records by date
        sorted_records = sorted(records, key=lambda r: r.date_time)
        
        # Extract basic information
        accounts_trading = {r.trade_account for r in records}
        
        first_trade = sorted_records[0].date_time.date()
        last_trade = sorted_records[-1].date_time.date()
        
        total_trades = len(records)
        total_volume = sum(r.filled_quantity for r in records)
        
        # Collect validation warnings
        warnings = []
        if len(accounts_trading) > 1:
            warnings.append(f"Symbol traded by multiple accounts: {accounts_trading}")
        
        # Create metadata
        metadata = SymbolMetadata(
            symbol=symbol,
            accounts_trading=accounts_trading,
            first_trade_date=first_trade,
            last_trade_date=last_trade,
            total_trades=total_trades,
            total_volume=total_volume,
            validation_warnings=warnings
        )
        
        self.symbol_metadata[symbol] = metadata
    
    def _validate_account_symbol_rules(self, records: List[SierraChartTradeRecord]):
        """
        Validate account and symbol separation rules.
        
        Args:
            records: List of records to validate
        """
        # Rule 1: Each account should trade only one symbol
        self._validate_one_symbol_per_account(records)
        
        # Rule 2: Validate account naming conventions
        self._validate_account_naming_conventions()
        
        # Rule 3: Check for cross-contamination
        self._validate_no_cross_contamination(records)
        
        # Rule 4: Validate symbol consistency
        self._validate_symbol_consistency(records)
    
    def _validate_one_symbol_per_account(self, records: List[SierraChartTradeRecord]):
        """
        Validate that each account trades only one symbol.
        
        Args:
            records: List of records to validate
        """
        for account_name, metadata in self.account_metadata.items():
            if len(metadata.symbols_traded) > 1:
                # Find records that violate this rule
                affected_records = [r for r in records if r.trade_account == account_name]
                
                violation = ValidationViolation(
                    violation_type="MULTIPLE_SYMBOLS_PER_ACCOUNT",
                    account=account_name,
                    symbol="MULTIPLE",
                    description=f"Account {account_name} trades multiple symbols: {metadata.symbols_traded}",
                    severity="ERROR",
                    affected_records=affected_records
                )
                
                self.violations.append(violation)
                self.logger.error(f"Validation violation: {violation.description}")
    
    def _validate_account_naming_conventions(self):
        """Validate account naming conventions."""
        expected_pattern = r"^IPS_T[MS]_\w+$"
        import re
        
        for account_name, metadata in self.account_metadata.items():
            if not re.match(expected_pattern, account_name):
                violation = ValidationViolation(
                    violation_type="INVALID_ACCOUNT_NAME",
                    account=account_name,
                    symbol=metadata.primary_symbol,
                    description=f"Account name {account_name} doesn't match expected pattern {expected_pattern}",
                    severity="WARNING",
                    affected_records=[]
                )
                
                self.violations.append(violation)
                self.logger.warning(f"Validation warning: {violation.description}")
    
    def _validate_no_cross_contamination(self, records: List[SierraChartTradeRecord]):
        """
        Validate that there's no cross-contamination between accounts and symbols.
        
        Args:
            records: List of records to validate
        """
        # Check for symbols that appear in multiple accounts
        for symbol, metadata in self.symbol_metadata.items():
            if len(metadata.accounts_trading) > 1:
                # This might be acceptable in some cases, so make it a warning
                affected_records = [r for r in records if r.base_symbol == symbol]
                
                violation = ValidationViolation(
                    violation_type="SYMBOL_CROSS_CONTAMINATION",
                    account="MULTIPLE",
                    symbol=symbol,
                    description=f"Symbol {symbol} is traded by multiple accounts: {metadata.accounts_trading}",
                    severity="WARNING",
                    affected_records=affected_records
                )
                
                self.violations.append(violation)
                self.logger.warning(f"Validation warning: {violation.description}")
    
    def _validate_symbol_consistency(self, records: List[SierraChartTradeRecord]):
        """
        Validate symbol consistency and format.
        
        Args:
            records: List of records to validate
        """
        expected_base_symbols = {'NQ', 'FDAX'}
        
        for record in records:
            base_symbol = record.base_symbol
            
            if base_symbol not in expected_base_symbols:
                violation = ValidationViolation(
                    violation_type="UNEXPECTED_SYMBOL",
                    account=record.trade_account,
                    symbol=base_symbol,
                    description=f"Unexpected symbol {base_symbol} found (expected: {expected_base_symbols})",
                    severity="INFO",
                    affected_records=[record]
                )
                
                self.violations.append(violation)
                self.logger.info(f"Validation info: {violation.description}")
    
    def get_account_metadata(self, account_name: Optional[str] = None) -> Dict[str, AccountMetadata]:
        """
        Get account metadata.
        
        Args:
            account_name: Specific account name, or None for all accounts
            
        Returns:
            Dictionary of account metadata
        """
        if account_name:
            return {account_name: self.account_metadata.get(account_name)} if account_name in self.account_metadata else {}
        return self.account_metadata.copy()
    
    def get_symbol_metadata(self, symbol: Optional[str] = None) -> Dict[str, SymbolMetadata]:
        """
        Get symbol metadata.
        
        Args:
            symbol: Specific symbol, or None for all symbols
            
        Returns:
            Dictionary of symbol metadata
        """
        if symbol:
            return {symbol: self.symbol_metadata.get(symbol)} if symbol in self.symbol_metadata else {}
        return self.symbol_metadata.copy()
    
    def get_violations(self, severity: Optional[str] = None) -> List[ValidationViolation]:
        """
        Get validation violations.
        
        Args:
            severity: Filter by severity ('ERROR', 'WARNING', 'INFO'), or None for all
            
        Returns:
            List of validation violations
        """
        if severity:
            return [v for v in self.violations if v.severity == severity]
        return self.violations.copy()
    
    def get_validation_summary(self) -> Dict:
        """
        Get comprehensive validation summary.
        
        Returns:
            Dictionary with validation summary
        """
        return {
            'validation_stats': self.validation_stats.copy(),
            'account_summary': {
                'total_accounts': len(self.account_metadata),
                'active_accounts': len([a for a in self.account_metadata.values() if a.is_active]),
                'accounts_with_violations': len(set(v.account for v in self.violations if v.account != "MULTIPLE")),
                'accounts_list': list(self.account_metadata.keys())
            },
            'symbol_summary': {
                'total_symbols': len(self.symbol_metadata),
                'symbols_with_violations': len(set(v.symbol for v in self.violations if v.symbol != "MULTIPLE")),
                'symbols_list': list(self.symbol_metadata.keys())
            },
            'violation_summary': {
                'total_violations': len(self.violations),
                'errors': self.validation_stats['error_violations'],
                'warnings': self.validation_stats['warning_violations'],
                'info': self.validation_stats['info_violations'],
                'violation_types': list(set(v.violation_type for v in self.violations))
            }
        }
    
    def _reset_validation_state(self):
        """Reset validation state for new validation run."""
        self.validation_stats = {
            'total_records_validated': 0,
            'accounts_analyzed': 0,
            'symbols_analyzed': 0,
            'violations_found': 0,
            'error_violations': 0,
            'warning_violations': 0,
            'info_violations': 0
        }
        
        self.violations.clear()
        self.account_metadata.clear()
        self.symbol_metadata.clear()
    
    def export_account_metadata_to_dict(self) -> List[Dict]:
        """
        Export account metadata to list of dictionaries for serialization.
        
        Returns:
            List of account metadata dictionaries
        """
        result = []
        
        for account_name, metadata in self.account_metadata.items():
            result.append({
                'account_name': metadata.account_name,
                'primary_symbol': metadata.primary_symbol,
                'symbols_traded': list(metadata.symbols_traded),
                'first_trade_date': metadata.first_trade_date.isoformat(),
                'last_trade_date': metadata.last_trade_date.isoformat(),
                'total_trades': metadata.total_trades,
                'total_volume': metadata.total_volume,
                'is_active': metadata.is_active,
                'validation_warnings': metadata.validation_warnings
            })
        
        return result
    
    def export_violations_to_dict(self) -> List[Dict]:
        """
        Export violations to list of dictionaries for serialization.
        
        Returns:
            List of violation dictionaries
        """
        result = []
        
        for violation in self.violations:
            result.append({
                'violation_type': violation.violation_type,
                'account': violation.account,
                'symbol': violation.symbol,
                'description': violation.description,
                'severity': violation.severity,
                'affected_records_count': len(violation.affected_records)
            })
        
        return result
    
    def generate_validation_report(self) -> str:
        """
        Generate a human-readable validation report.
        
        Returns:
            Formatted validation report string
        """
        summary = self.get_validation_summary()
        
        report_lines = [
            "=== ACCOUNT AND SYMBOL VALIDATION REPORT ===",
            "",
            f"Records Validated: {summary['validation_stats']['total_records_validated']}",
            f"Accounts Analyzed: {summary['account_summary']['total_accounts']}",
            f"Symbols Analyzed: {summary['symbol_summary']['total_symbols']}",
            "",
            "=== VALIDATION RESULTS ===",
            f"Total Violations: {summary['violation_summary']['total_violations']}",
            f"  - Errors: {summary['violation_summary']['errors']}",
            f"  - Warnings: {summary['violation_summary']['warnings']}",
            f"  - Info: {summary['violation_summary']['info']}",
            "",
        ]
        
        if self.violations:
            report_lines.extend([
                "=== VIOLATIONS DETAILS ===",
                ""
            ])
            
            for violation in self.violations:
                report_lines.extend([
                    f"[{violation.severity}] {violation.violation_type}",
                    f"  Account: {violation.account}",
                    f"  Symbol: {violation.symbol}",
                    f"  Description: {violation.description}",
                    f"  Affected Records: {len(violation.affected_records)}",
                    ""
                ])
        
        if self.account_metadata:
            report_lines.extend([
                "=== ACCOUNT SUMMARY ===",
                ""
            ])
            
            for account_name, metadata in self.account_metadata.items():
                report_lines.extend([
                    f"Account: {account_name}",
                    f"  Primary Symbol: {metadata.primary_symbol}",
                    f"  Symbols Traded: {', '.join(metadata.symbols_traded)}",
                    f"  Trading Period: {metadata.first_trade_date} to {metadata.last_trade_date}",
                    f"  Total Trades: {metadata.total_trades}",
                    f"  Total Volume: {metadata.total_volume}",
                    f"  Active: {metadata.is_active}",
                    ""
                ])
        
        return "\n".join(report_lines)