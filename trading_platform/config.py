"""
Configuration settings for the Trading Optimization Platform.
"""

from pathlib import Path
from typing import List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Data source paths
    SIERRA_CHART_SIMULATED_PATH = Path(r"D:\SierraChart_Simulated_Feed\SavedTradeActivity")
    SIERRA_CHART_DELAYED_PATH = Path(r"D:\SierraChart_Delayed_Simulated\SavedTradeActivity")
    
    # Database configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trading_platform.db")
    
    # MCP configuration
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")
    MCP_API_KEY = os.getenv("MCP_API_KEY", "")
    
    # API configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_RELOAD = os.getenv("API_RELOAD", "false").lower() == "true"
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "true").lower() == "true"
    
    # Analysis parameters
    RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.02"))  # 2% annual
    CONFIDENCE_LEVEL = float(os.getenv("CONFIDENCE_LEVEL", "0.95"))  # 95%
    
    # Monte Carlo simulation
    DEFAULT_SIMULATIONS = int(os.getenv("DEFAULT_SIMULATIONS", "10000"))
    DEFAULT_TIME_HORIZON = int(os.getenv("DEFAULT_TIME_HORIZON", "252"))  # Trading days in a year
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "trading_platform.log")
    
    # File processing
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "500"))
    
    @classmethod
    def get_sierra_chart_paths(cls) -> List[Path]:
        """Get all SierraChart data source paths."""
        return [cls.SIERRA_CHART_SIMULATED_PATH, cls.SIERRA_CHART_DELAYED_PATH]
    
    @classmethod
    def validate_paths(cls) -> bool:
        """Validate that all required paths exist."""
        for path in cls.get_sierra_chart_paths():
            if not path.exists():
                return False
        return True


# Create global config instance
config = Config()