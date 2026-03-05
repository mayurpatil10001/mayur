import struct
import os
import datetime

def parse_fills(file_path):
    print(f"Parsing {file_path}")
    if not os.path.exists(file_path):
        print("File not found")
        return

    # Sierra Chart Binary Log Format (approximate based on previous knowledge)
    # Header 40 bytes, Records 160 bytes
    with open(file_path, 'rb') as f:
        header = f.read(40)
        while True:
            chunk = f.read(160)
            if not chunk or len(chunk) < 160:
                break
            
            # SC Trade Activity Record (simplified)
            # Offset 0: Symbol (64 bytes)
            # Offset 80: Order ID (8 bytes)
            # Offset 88: Fill Price (8 bytes, double)
            # Offset 96: Fill Quantity (4 bytes, int)
            # Offset 100: Side (4 bytes, 1=Buy, 2=Sell)
            # Offset 112: Timestamp (8 bytes, int64, SC format: seconds since 1899-12-30 or similar)
            # But we often use datetime.datetime.fromtimestamp() for some SC formats.
            # Let's try to find the 02:26 time.
            
            symbol = chunk[0:64].strip(b'\x00').decode('ascii', errors='ignore')
            order_id = struct.unpack('<q', chunk[80:88])[0]
            price = struct.unpack('<d', chunk[88:96])[0]
            qty = struct.unpack('<i', chunk[96:100])[0]
            side_raw = struct.unpack('<i', chunk[100:104])[0]
            side = "BUY" if side_raw == 1 else "SELL"
            
            # The timestamp is at 112, 8 bytes.
            sc_ts = struct.unpack('<q', chunk[112:120])[0]
            # Convert SC timestamp (microseconds since 1970? or similar)
            # Let's try to print a human readable time.
            try:
                dt = datetime.datetime.fromtimestamp(sc_ts / 1000000, tz=datetime.timezone.utc)
                time_str = dt.strftime('%H:%M:%S.%f')
                
                if dt.hour == 2 and dt.minute >= 20 and dt.minute <= 30:
                    print(f"MATCH: {time_str} | {side} | {qty} | {price} | Order:{order_id} | {symbol}")
                elif dt.hour >= 0 and dt.hour <= 5:
                    # Print early morning fills
                    print(f"Fill: {time_str} | {side} | {qty} | {price} | Order:{order_id} | {symbol}")
            except:
                pass

file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data'
parse_fills(file_path)
