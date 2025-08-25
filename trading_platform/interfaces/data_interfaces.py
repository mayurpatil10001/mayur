"""
Data processing and ingestion interfaces.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path

from ..models.sierra_chart import SierraChartTradeRecord
from ..models.trading import ProcessedTrade, Account


class IDataIngestionService(ABC):
    """Interface for data ingestion from SierraChart files."""
    
    @abstractmethod
    def ingest_from_file(self, file_path: Path) -> List[SierraChartTradeRecord]:
        """Ingest trade records from a single SierraChart file."""
        pass
    
    @abstractmethod
    def ingest_from_directory(self, directory_path: Path) -> List[SierraChartTradeRecord]:
        """Ingest trade records from all files in a directory."""
        pass
    
    @abstractmethod
    def validate_file_format(self, file_path: Path) -> bool:
        """Validate that file matches expected SierraChart format."""
        pass


class IDataCleaningService(ABC):
    """Interface for data cleaning and validation."""
    
    @abstractmethod
    def clean_incomplete_trades(self, records: List[SierraChartTradeRecord]) -> List[SierraChartTradeRecord]:
        """Remove incomplete day trades from the dataset."""
        pass
    
    @abstractmethod
    def validate_account_asset_separation(self, records: List[SierraChartTradeRecord]) -> Dict[str, List[str]]:
        """Validate that each account trades only one symbol."""
        pass
    
    @abstractmethod
    def detect_duplicates(self, records: List[SierraChartTradeRecord]) -> List[SierraChartTradeRecord]:
        """Detect and return duplicate records."""
        pass


class ITradeProcessingService(ABC):
    """Interface for converting raw fills into processed trades."""
    
    @abstractmethod
    def process_fills_to_trades(self, fills: List[SierraChartTradeRecord]) -> List[ProcessedTrade]:
        """Convert SierraChart fills into complete round-trip trades."""
        pass
    
    @abstractmethod
    def extract_accounts(self, fills: List[SierraChartTradeRecord]) -> List[Account]:
        """Extract account information from trading data."""
        pass
    
    @abstractmethod
    def calculate_trade_metrics(self, trade: ProcessedTrade) -> Dict[str, Any]:
        """Calculate additional metrics for a processed trade."""
        pass