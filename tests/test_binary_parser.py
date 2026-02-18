
import struct
import datetime
import os
import re

# Sierra Chart binary log parser
# Format discovered:
# - Messages seem to be length-prefixed strings
# - Each record might have a header containing a timestamp
# - "Trading Evaluator" messages represent fills

class SCBinaryImporter:
    def __init__(self, db_path='trading_platform.db'):
        self.db_path = db_path

    def sc_datetime_to_iso(self, sc_val):
        try:
            # If it's 1970 based (Unix)
            if 1000000000 < sc_val < 2000000000:
                return datetime.datetime.fromtimestamp(sc_val).isoformat()
            # If it's SC double (1899 based)
            if 40000 < sc_val < 60000:
                base_date = datetime.datetime(1899, 12, 30)
                return (base_date + datetime.timedelta(days=sc_val)).isoformat()
        except:
            return None
        return None

    def parse_file(self, file_path):
        with open(file_path, 'rb') as f:
            data = f.read()

        fills = []
        # Extract account and symbol from filename if possible
        # e.g. TradeActivityLog_...ES-TM_3.data
        filename = os.path.basename(file_path)
        parts = filename.split('.')
        account_symbol_part = parts[-2] if len(parts) > 1 else ""
        
        # Heuristic: Find all "Trading Evaluator" strings
        # and search backwards for a timestamp near them
        # pattern = rb"Trading Evaluator historical fill \(Trade simulation fill\. Bid: ([\d\.]+) Ask: ([\d\.]+) Last: ([\d\.]+)"
        # Note: Added \. to match the dot after price and handle the trailer
        # Updated pattern to find prices without trailing dots
        pattern = rb"Bid: ([\d\.]+)\s+Ask: ([\d\.]+)\s+Last: ([\d\.]+)"
        
        for match in re.finditer(pattern, data):
            prices = match.groups()
            try:
                # Decode and strip any trailing punctuation
                bid = float(prices[0].decode().rstrip('.'))
                ask = float(prices[1].decode().rstrip('.'))
                last_price = float(prices[2].decode().rstrip('.'))
            except:
                continue
            
            # Search backwards for 8-byte double (timestamp) or 4-byte int
            # Alignment is tricky index.
            offset = match.start()
            timestamp = None
            
            # Look at 4-byte alignment backwards
            for i in range(offset - 4, max(0, offset - 128), -1):
                # Try reading a Unix timestamp (4 bytes)
                val_int = struct.unpack('<I', data[i:i+4])[0]
                if 1700000000 < val_int < 1800000000: # Current era
                    timestamp = datetime.datetime.fromtimestamp(val_int).isoformat()
                    break
            
            # Search backwards for strings
            nearby = data[max(0, offset-200):offset]
            print(f"\n--- Strings before offset {offset} ---")
            strings = re.findall(b'[ -~]{4,}', nearby)
            for s in strings:
                print(f"  {s.decode('ascii', errors='ignore')}")
            
            side = "UNKNOWN"
            if b"Bought" in nearby: side = "BUY"
            elif b"Sold" in nearby: side = "SELL"
            elif b"Buy" in nearby: side = "BUY"
            elif b"Sell" in nearby: side = "SELL"
            
            msg = match.group(0).decode('ascii', errors='ignore')
            
            fills.append({
                "account": account_symbol_part,
                "symbol": account_symbol_part.split('-')[0] if '-' in account_symbol_part else account_symbol_part,
                "time": timestamp,
                "price": last_price,
                "msg": msg,
                "side": side,
                "offset": offset
            })
            
        return fills

if __name__ == "__main__":
    parser = SCBinaryImporter()
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"
    fills = parser.parse_file(path)
    print(f"Parsed {len(fills)} fills from binary file.")
    for f in fills[:5]:
        print(f)
