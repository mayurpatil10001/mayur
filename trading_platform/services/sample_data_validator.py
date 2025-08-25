#!/usr/bin/env python3
"""
Sample data validator for validating imported data against known good records.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from trading_platform.repositories.sierra_chart_repository import SierraChartRepository

logger = logging.getLogger(__name__)


@dataclass
class SampleValidationResult:
    """Result of sample data validation."""
    sample_name: str
    total_samples: int
    matches_found: int
    exact_matches: int
    close_matches: int
    missing_samples: int
    validation_errors: List[str]
    match_percentage: float
    passed: bool


class SampleDataValidator:
    """Validator for checking imported data against known good samples."""

    def __init__(self, samples_directory: str = "sample_data"):
        """Initialize the sample validator.

        Args:
            samples_directory: Directory containing sample data files
        """
        self.repository = SierraChartRepository()
        self.samples_dir = Path(samples_directory)
        self.tolerance = {
            "price": 0.01,  # $0.01 price tolerance
            "profit_loss": 0.01,  # $0.01 P&L tolerance
            "time_seconds": 5,  # 5 second time tolerance
        }

    def create_sample_data(self, output_file: str, sample_size: int = 100) -> bool:
        """Create sample data from current database for future validation.

        Args:
            output_file: Path to save sample data
            sample_size: Number of sample records to create

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get sample trades from database
            query = """
            SELECT * FROM sierra_chart_trades 
            ORDER BY RANDOM() 
            LIMIT ?
            """
            
            cursor = self.repository.connection.cursor()
            cursor.execute(query, (sample_size,))
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                logger.error("No trades found in database to create samples")
                return False
            
            # Convert to list of dictionaries
            samples = []
            for row in rows:
                trade_dict = dict(zip(columns, row))
                # Convert datetime strings for JSON serialization
                if trade_dict.get('entry_datetime'):
                    trade_dict['entry_datetime'] = str(trade_dict['entry_datetime'])
                if trade_dict.get('exit_datetime'):
                    trade_dict['exit_datetime'] = str(trade_dict['exit_datetime'])
                if trade_dict.get('created_at'):
                    trade_dict['created_at'] = str(trade_dict['created_at'])
                if trade_dict.get('updated_at'):
                    trade_dict['updated_at'] = str(trade_dict['updated_at'])
                samples.append(trade_dict)
            
            # Create sample data structure
            sample_data = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "sample_size": len(samples),
                    "description": f"Sample data for validation - {len(samples)} trades",
                    "tolerance": self.tolerance
                },
                "samples": samples
            }
            
            # Save to file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, indent=2)
            
            logger.info(f"Created {len(samples)} sample records in {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating sample data: {e}")
            return False

    def validate_against_samples(self, sample_file: str) -> SampleValidationResult:
        """Validate current database against sample data.

        Args:
            sample_file: Path to sample data file

        Returns:
            SampleValidationResult object
        """
        logger.info(f"Validating against sample data: {sample_file}")
        
        # Load sample data
        sample_data = self._load_sample_data(sample_file)
        if not sample_data:
            return SampleValidationResult(
                sample_name=Path(sample_file).name,
                total_samples=0,
                matches_found=0,
                exact_matches=0,
                close_matches=0,
                missing_samples=0,
                validation_errors=["Failed to load sample data"],
                match_percentage=0.0,
                passed=False
            )
        
        samples = sample_data.get("samples", [])
        if not samples:
            return SampleValidationResult(
                sample_name=Path(sample_file).name,
                total_samples=0,
                matches_found=0,
                exact_matches=0,
                close_matches=0,
                missing_samples=0,
                validation_errors=["No samples found in file"],
                match_percentage=0.0,
                passed=False
            )
        
        # Validate each sample
        exact_matches = 0
        close_matches = 0
        validation_errors = []
        
        for i, sample in enumerate(samples):
            try:
                match_type = self._validate_sample_trade(sample)
                if match_type == "exact":
                    exact_matches += 1
                elif match_type == "close":
                    close_matches += 1
                elif match_type == "missing":
                    validation_errors.append(f"Sample {i+1}: Trade not found - {sample.get('trade_id', 'unknown')}")
                else:
                    validation_errors.append(f"Sample {i+1}: Validation failed - {sample.get('trade_id', 'unknown')}")
            except Exception as e:
                validation_errors.append(f"Sample {i+1}: Error validating - {e}")
        
        # Calculate results
        total_samples = len(samples)
        matches_found = exact_matches + close_matches
        missing_samples = total_samples - matches_found
        match_percentage = (matches_found / total_samples * 100) if total_samples > 0 else 0
        passed = match_percentage >= 95.0  # 95% match threshold
        
        result = SampleValidationResult(
            sample_name=Path(sample_file).name,
            total_samples=total_samples,
            matches_found=matches_found,
            exact_matches=exact_matches,
            close_matches=close_matches,
            missing_samples=missing_samples,
            validation_errors=validation_errors,
            match_percentage=match_percentage,
            passed=passed
        )
        
        logger.info(f"Sample validation complete: {match_percentage:.1f}% match rate")
        return result

    def validate_all_samples(self) -> List[SampleValidationResult]:
        """Validate against all sample files in the samples directory.

        Returns:
            List of SampleValidationResult objects
        """
        results = []
        
        if not self.samples_dir.exists():
            logger.warning(f"Samples directory not found: {self.samples_dir}")
            return results
        
        # Find all JSON sample files
        sample_files = list(self.samples_dir.glob("*.json"))
        
        if not sample_files:
            logger.warning(f"No sample files found in {self.samples_dir}")
            return results
        
        logger.info(f"Found {len(sample_files)} sample files")
        
        for sample_file in sample_files:
            try:
                result = self.validate_against_samples(str(sample_file))
                results.append(result)
            except Exception as e:
                logger.error(f"Error validating against {sample_file}: {e}")
                results.append(SampleValidationResult(
                    sample_name=sample_file.name,
                    total_samples=0,
                    matches_found=0,
                    exact_matches=0,
                    close_matches=0,
                    missing_samples=0,
                    validation_errors=[f"Validation error: {e}"],
                    match_percentage=0.0,
                    passed=False
                ))
        
        return results

    def _load_sample_data(self, sample_file: str) -> Optional[Dict]:
        """Load sample data from file.

        Args:
            sample_file: Path to sample data file

        Returns:
            Sample data dictionary or None if failed
        """
        try:
            with open(sample_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sample data from {sample_file}: {e}")
            return None

    def _validate_sample_trade(self, sample: Dict) -> str:
        """Validate a single sample trade against database.

        Args:
            sample: Sample trade data

        Returns:
            Match type: "exact", "close", "missing", or "error"
        """
        trade_id = sample.get("trade_id")
        if not trade_id:
            return "error"
        
        # Find trade in database
        query = "SELECT * FROM sierra_chart_trades WHERE trade_id = ?"
        cursor = self.repository.connection.cursor()
        cursor.execute(query, (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            return "missing"
        
        # Convert row to dictionary
        columns = [description[0] for description in cursor.description]
        db_trade = dict(zip(columns, row))
        
        # Compare key fields
        exact_match = True
        close_match = True
        
        # Check critical fields for exact match
        critical_fields = ["account", "symbol", "base_symbol", "trade_quantity", "trade_type"]
        for field in critical_fields:
            if sample.get(field) != db_trade.get(field):
                exact_match = False
                close_match = False
                break
        
        if not close_match:
            return "error"
        
        # Check numeric fields with tolerance
        numeric_fields = [
            ("entry_price", "price"),
            ("exit_price", "price"),
            ("profit_loss", "profit_loss"),
        ]
        
        for field, tolerance_type in numeric_fields:
            sample_val = sample.get(field)
            db_val = db_trade.get(field)
            
            if sample_val is None or db_val is None:
                continue
            
            tolerance = self.tolerance.get(tolerance_type, 0.01)
            if abs(float(sample_val) - float(db_val)) > tolerance:
                exact_match = False
        
        # Check datetime fields with tolerance
        datetime_fields = ["entry_datetime", "exit_datetime"]
        for field in datetime_fields:
            sample_dt_str = sample.get(field)
            db_dt_str = str(db_trade.get(field))
            
            if sample_dt_str and db_dt_str:
                try:
                    sample_dt = datetime.fromisoformat(sample_dt_str.replace("Z", "+00:00"))
                    db_dt = datetime.fromisoformat(db_dt_str.replace("Z", "+00:00"))
                    
                    time_diff = abs((sample_dt - db_dt).total_seconds())
                    if time_diff > self.tolerance["time_seconds"]:
                        exact_match = False
                except Exception:
                    exact_match = False
        
        return "exact" if exact_match else "close"

    def generate_sample_validation_report(self, results: List[SampleValidationResult]) -> str:
        """Generate a report from sample validation results.

        Args:
            results: List of validation results

        Returns:
            Report as string
        """
        if not results:
            return "No sample validation results to report."
        
        report_lines = [
            "=" * 80,
            "SAMPLE DATA VALIDATION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Sample Files Validated: {len(results)}",
            "",
        ]
        
        # Overall summary
        total_samples = sum(r.total_samples for r in results)
        total_matches = sum(r.matches_found for r in results)
        total_exact = sum(r.exact_matches for r in results)
        total_close = sum(r.close_matches for r in results)
        
        overall_percentage = (total_matches / total_samples * 100) if total_samples > 0 else 0
        
        report_lines.extend([
            "OVERALL SUMMARY",
            "-" * 40,
            f"Total Sample Records: {total_samples:,}",
            f"Total Matches Found: {total_matches:,} ({overall_percentage:.1f}%)",
            f"Exact Matches: {total_exact:,}",
            f"Close Matches: {total_close:,}",
            f"Missing Records: {total_samples - total_matches:,}",
            "",
        ])
        
        # Individual file results
        report_lines.extend([
            "INDIVIDUAL FILE RESULTS",
            "-" * 40,
        ])
        
        for result in results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            report_lines.extend([
                f"\n{result.sample_name}: {status}",
                f"  Samples: {result.total_samples:,}",
                f"  Matches: {result.matches_found:,} ({result.match_percentage:.1f}%)",
                f"  Exact: {result.exact_matches:,}, Close: {result.close_matches:,}",
                f"  Missing: {result.missing_samples:,}",
            ])
            
            if result.validation_errors:
                report_lines.append(f"  Errors: {len(result.validation_errors)}")
                for error in result.validation_errors[:5]:  # Show first 5 errors
                    report_lines.append(f"    - {error}")
                if len(result.validation_errors) > 5:
                    report_lines.append(f"    ... and {len(result.validation_errors) - 5} more")
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(report_lines)