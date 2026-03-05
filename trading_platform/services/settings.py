
import json
import os
from pathlib import Path
from typing import Dict, Any

SETTINGS_FILE = Path("app_settings.json")

class SettingsService:
    def __init__(self):
        self.default_settings = {
            "scanners": [
                { "symbol": 'CL', "path": 'D:\\SierraChart_Simulated_Feed\\SierraChartInstance_4\\TradeActivityLogs' },
                { "symbol": 'ES', "path": 'D:\\SierraChart_Simulated_Feed\\SierraChartInstance_5\\TradeActivityLogs' },
                { "symbol": 'NQ', "path": 'D:\\SierraChart_Simulated_Feed\\TradeActivityLogs' },
                { "symbol": 'FDAX', "path": 'D:\\SierraChart_Delayed_Simulated\\TradeActivityLogs' },
            ],
            "last_import_range": "2000", # effectively unlimited
            "last_used_symbol": "CL"
        }
        self.settings = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    merged = self.default_settings.copy()
                    merged.update(saved)
                    return merged
            except Exception as e:
                print(f"Error loading settings: {e}")
        return self.default_settings

    def save_settings(self, new_settings: Dict[str, Any]):
        try:
            self.settings.update(new_settings)
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get_settings(self) -> Dict[str, Any]:
        return self.settings

settings_service = SettingsService()
