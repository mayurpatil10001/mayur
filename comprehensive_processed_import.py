#!/usr/bin/env python3
"""
Comprehensive import script for processed trade files.
"""

import logging
import sys
import os
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Any, Optional
import sqlite3
import yaml

# Add the trading platform to the path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessedTradeImporter:
    """Importer for processed trade files."""
    
    def __init__(self, config_path: str = "import_config.yaml", db_path: str = "trading_platform.db"):
        """Initialize the importer."""
        self.config_path = config_path
        self.db_path = db_path
        self.config = self._load_config()
        
        self.stats = {
            "files_found": 0,
            "files_processed": 0,
            "records_parsed": 0,
            "records_imported": 0,
            "records_failed": 0,
            "accounts_found": set(),
            "symbols_found": set(),
            "dates_found": set(),
            "total_pnl": 0.0,
            "total_commission": 0.0,
        }
        
        # Initialize parser
        from trading_platform.services.processed_trade_parser import SierraChartProcessedTradeParser
        self.parser = SierraChartProcessedTradeParser(logger)
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            # Return default config
            return {
                "import_directories": [
                    "D:\\SierraChart_Simulated_Feed\\SierraChartInstance_5\\SavedTradeActivity",
                    "D:\\SierraChart_Simulated_Feed\\SavedTradeActivity",
                    "D:\\SierraChart_Delayed_Simulated\\SavedTradeActivity",
                    "D:\\SierraChart_Simulated_Feed\\SierraChartInstance_4\\SavedTradeActivity"
                ],
                "expected_assets": ["NQ", "FDAX", "ES", "CL"],
                "expected_accounts": 43
            }
    
    def scan_directories(self) -> List[Path]:
        """Scan directories for processed trade files."""
        logger.info(f"Scanning directories: {self.config['import_directories']}")
        
        all_files = []
        
        for directory in self.config['import_directories']:
            try:
                dir_path = Path(directory)
                if not dir_path.exists():
                    logger.warning(f"Directory does not exist: {directory}")
                    continue
                
                # Find all .txt files
                files_in_dir = list(dir_path.glob("*.txt"))
                
                # Filter for relevant files
                relevant_files = []
                for file_path in files_in_dir:
                    if self._is_relevant_file(file_path):
                        relevant_files.append(file_path)
                
                all_files.extend(relevant_files)
                logger.info(f"Found {len(relevant_files)} relevant files in {directory}")
                
            except Exception as e:
                logger.error(f"Error scanning directory {directory}: {e}")
                continue
        
        self.stats["files_found"] = len(all_files)
        logger.info(f"Total files found: {len(all_files)}")
        
        return all_files
    
    def _is_relevant_file(self, file_path: Path) -> bool:
        """Check if file is relevant for trading data."""
        filename = file_path.name.upper()
        
        # Check for expected symbols
        for symbol in self.config['expected_assets']:
            if symbol in filename:
                return True
        
        return False
    
    def process_files(self, file_paths: List[Path]) -> List[Any]:
        """Process all files and return processed trades."""
        logger.info(f"Processing {len(file_paths)} files")
        
        all_trades = []
        
        for file_path in file_paths:
            try:
                logger.info(f"Processing file: {file_path}")
                
                # Parse the file
                records = self.parser.parse_file(file_path)
                self.stats["records_parsed"] += len(records)
                
                # Convert to ProcessedTrade objects
                for record in records:
                    try:
                        processed_trade = self.parser.convert_to_processed_trade(record, file_path.name)
                        all_trades.append(processed_trade)
                        
                        # Update statistics
                        self.stats["accounts_found"].add(processed_trade.account_name)
                        self.stats["symbols_found"].add(processed_trade.symbol)
                        self.stats["dates_found"].add(processed_trade.entry_time.date())
                        self.stats["total_pnl"] += processed_trade.profit_loss
                        self.stats["total_commission"] += processed_trade.commission
                        
                    except Exception as e:
                        logger.error(f"Error converting record: {e}")
                        self.stats["records_failed"] += 1
                        continue
                
                self.stats["files_processed"] += 1
                logger.info(f"Successfully processed {file_path}: {len(records)} records")
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue
        
        self.stats["records_imported"] = len(all_trades)
        logger.info(f"Total processed trades: {len(all_trades)}")
        
        return all_trades
    
    def save_to_database(self, processed_trades: List[Any]) -> bool:
        """Save processed trades to database."""
        logger.info(f"Saving {len(processed_trades)} processed trades to database")
        
        try:
            # Create database connection
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_trades (
                id INTEGER PRIMARY KEY,
                trade_id TEXT UNIQUE,
                account_name TEXT,
                symbol TEXT,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                entry_price REAL,
                exit_price REAL,
                quantity INTEGER,
                side TEXT,
                profit_loss REAL,
                commission REAL,
                duration_minutes INTEGER,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Clear existing data
            cursor.execute("DELETE FROM processed_trades")
            logger.info("Cleared existing processed trades")
            
            # Insert trades (ignore duplicates)
            for trade in processed_trades:
                cursor.execute("""
                INSERT OR IGNORE INTO processed_trades (
                    trade_id, account_name, symbol, entry_time, exit_time,
                    entry_price, exit_price, quantity, side, profit_loss,
                    commission, duration_minutes, hour_of_day, day_of_week
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id,
                    trade.account_name,
                    trade.symbol,
                    trade.entry_time.isoformat(),
                    trade.exit_time.isoformat(),
                    trade.entry_price,
                    trade.exit_price,
                    trade.quantity,
                    trade.side,
                    trade.profit_loss,
                    trade.commission,
                    trade.duration_minutes,
                    trade.hour_of_day,
                    trade.day_of_week
                ))
            
            # Commit and close
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully saved {len(processed_trades)} trades to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            return False
    
    def generate_summary_report(self) -> str:
        """Generate a comprehensive summary report."""
        report = []
        report.append("=" * 80)
        report.append("PROCESSED TRADE IMPORT SUMMARY")
        report.append("=" * 80)
        report.append("")
        
        report.append("FILE PROCESSING:")
        report.append(f"Files found: {self.stats['files_found']}")
        report.append(f"Files processed: {self.stats['files_processed']}")
        report.append("")
        
        report.append("DATA PROCESSING:")
        report.append(f"Records parsed: {self.stats['records_parsed']}")
        report.append(f"Records imported: {self.stats['records_imported']}")
        report.append(f"Records failed: {self.stats['records_failed']}")
        report.append("")
        
        report.append("ACCOUNTS AND SYMBOLS:")
        report.append(f"Accounts found: {len(self.stats['accounts_found'])} (expected: {self.config['expected_accounts']})")
        report.append(f"Symbols found: {len(self.stats['symbols_found'])} - {', '.join(sorted(self.stats['symbols_found']))}")
        report.append(f"Expected symbols: {', '.join(self.config['expected_assets'])}")
        report.append("")
        
        report.append("ACCOUNTS:")
        for account in sorted(self.stats['accounts_found']):
            report.append(f"  - {account}")
        report.append("")
        
        report.append("FINANCIAL SUMMARY:")
        report.append(f"Total P&L: ${self.stats['total_pnl']:.2f}")
        report.append(f"Total Commission: ${self.stats['total_commission']:.2f}")
        report.append(f"Net P&L: ${self.stats['total_pnl'] - self.stats['total_commission']:.2f}")
        report.append("")
        
        report.append("DATE RANGE:")
        if self.stats["dates_found"]:
            min_date = min(self.stats["dates_found"])
            max_date = max(self.stats["dates_found"])
            report.append(f"From {min_date} to {max_date}")
            report.append(f"Total trading days: {len(self.stats['dates_found'])}")
        else:
            report.append("No dates found")
        report.append("")
        
        # Check for missing data
        missing_symbols = set(self.config['expected_assets']) - self.stats['symbols_found']
        if missing_symbols:
            report.append("MISSING SYMBOLS:")
            for symbol in sorted(missing_symbols):
                report.append(f"  - {symbol}")
            report.append("")
        
        missing_accounts = self.config['expected_accounts'] - len(self.stats['accounts_found'])
        if missing_accounts > 0:
            report.append(f"MISSING ACCOUNTS: {missing_accounts} accounts not found")
            report.append("")
        
        # Success/failure status
        if (len(self.stats['symbols_found']) == len(self.config['expected_assets']) and 
            len(self.stats['accounts_found']) == self.config['expected_accounts'] and
            self.stats['records_imported'] > 0):
            report.append("✅ IMPORT COMPLETED SUCCESSFULLY!")
        else:
            report.append("⚠️  IMPORT COMPLETED WITH ISSUES")
            if len(self.stats['symbols_found']) < len(self.config['expected_assets']):
                report.append(f"   - Missing symbols: {missing_symbols}")
            if len(self.stats['accounts_found']) < self.config['expected_accounts']:
                report.append(f"   - Missing {missing_accounts} accounts")
            if self.stats['records_imported'] == 0:
                report.append("   - No records imported")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def run_import(self) -> bool:
        """Run the complete import process."""
        try:
            logger.info("Starting processed trade import")
            
            # Step 1: Scan directories
            file_paths = self.scan_directories()
            if not file_paths:
                logger.error("No files found to process")
                return False
            
            # Step 2: Process files
            processed_trades = self.process_files(file_paths)
            if not processed_trades:
                logger.error("No processed trades generated")
                return False
            
            # Step 3: Save to database
            if not self.save_to_database(processed_trades):
                logger.error("Failed to save to database")
                return False
            
            # Step 4: Generate and display summary
            summary_report = self.generate_summary_report()
            print(summary_report)
            
            # Save summary to file
            with open("processed_trade_import_summary.txt", "w") as f:
                f.write(summary_report)
            
            logger.info("Import completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False


def main():
    """Main function."""
    importer = ProcessedTradeImporter()
    success = importer.run_import()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()