
import yfinance as yf
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self, db_path: str = "trading_platform.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Existing table uses 'date' for the timestamp
        c.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(10) NOT NULL,
                date DATETIME NOT NULL,
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                volume FLOAT,
                adjusted_close FLOAT,
                created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        # Create index for faster lookups
        c.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_date ON market_data(symbol, date)")
        conn.commit()
        conn.close()

    def fetch_vix_data(self, period: str = "2y", interval: str = "1h"):
        """Fetch historical VIX data and store in DB."""
        symbol = "^VIX"
        db_symbol = "VIX"
        
        logger.info(f"Fetching VIX data for symbol {symbol}, period={period}, interval={interval}")
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                logger.warning(f"No VIX data found for {symbol}")
                return 0

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            added = 0
            for ts, row in hist.iterrows():
                # Convert timestamp to ISO string
                ts_str = ts.isoformat()
                
                try:
                    c.execute("""
                        INSERT OR REPLACE INTO market_data 
                        (symbol, date, open_price, high_price, low_price, close_price, volume, adjusted_close)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        db_symbol,
                        ts_str,
                        float(row['Open']),
                        float(row['High']),
                        float(row['Low']),
                        float(row['Close']),
                        float(row['Volume']),
                        float(row['Close']) # Use close as adjusted_close if not provided
                    ))
                    added += 1
                except Exception as e:
                    logger.error(f"Error inserting VIX data at {ts}: {e}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully imported {added} VIX data points")
            return added
            
        except Exception as e:
            logger.error(f"Failed to fetch VIX data: {e}")
            raise e

market_data_service = MarketDataService()
