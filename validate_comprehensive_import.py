#!/usr/bin/env python3
"""
Comprehensive validation script for the trading platform data import.
"""

import logging
import sys
import os
from pathlib import Path

# Add the trading platform to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_platform.services.import_validation_service import ImportValidationService
from trading_platform.database.connection import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run comprehensive import validation."""
    
    logger.info("Starting comprehensive import validation")
    
    try:
        # Initialize validation service
        validation_service = ImportValidationService()
        
        # Run comprehensive validation
        logger.info("Running comprehensive validation...")
        result = validation_service.validate_import()
        
        # Generate and display summary report
        summary_report = validation_service.create_validation_summary_report()
        print(summary_report)
        
        # Save summary to file
        summary_path = f"validation_summary_{result.validation_id}.txt"
        with open(summary_path, 'w') as f:
            f.write(summary_report)
        
        logger.info(f"Validation summary saved to: {summary_path}")
        
        # Show validation history
        history = validation_service.get_validation_history(5)
        if history:
            print("\nRECENT VALIDATION HISTORY:")
            print("-" * 80)
            for entry in history:
                print(f"{entry['timestamp']}: {entry['validation_rate']:.1%} success, "
                      f"{entry['data_quality_score']:.1%} quality, "
                      f"{entry['total_records']:,} records, "
                      f"{entry['issue_count']} issues")
        
        # Exit with appropriate code
        if result.data_quality_score >= 0.95:  # 95% threshold
            logger.info("✅ Validation passed - data quality is acceptable")
            sys.exit(0)
        else:
            logger.warning("⚠️ Validation concerns - data quality below threshold")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()