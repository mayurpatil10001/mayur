
import struct
import datetime
import os

FILE_PATH = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"

def sc_datetime_to_python(sc_val):
    """Convert Sierra Chart DateTime (days since 1899-12-30) to Python datetime."""
    try:
        base_date = datetime.datetime(1899, 12, 30)
        delta = datetime.timedelta(days=sc_val)
        return base_date + delta
    except:
        return None

def analyze_file():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'rb') as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")
    
    # Hex dump of the bytes 16-64
    print("\n--- BYTES 16-64 ---")
    chunk = data[16:64]
    for i in range(0, len(chunk), 16):
        hex_part = ' '.join(f'{b:02x}' for b in chunk[i:i+16])
        ascii_part = ''.join((chr(b) if 32 <= b < 127 else '.') for b in chunk[i:i+16])
        print(f"{16+i:04x}: {hex_part:<48} | {ascii_part}")

    # Search for strings
    print("\n--- STRINGS ---")
    import re
    # Look for strings of 4+ printable chars
    strings = re.finditer(b'[ -~]{4,}', data)
    for m in strings:
        print(f"Offset {m.start()}: {m.group().decode('ascii')}")

    # Search for doubles (potential timestamps or prices)
    print("\n--- POTENTIAL DOUBLES (SCDateTime or Price) ---")
    # SCDateTime for ~2025 is around 45600.0
    for i in range(0, len(data) - 8, 4): # Scanning every 4 bytes for alignment check, though might be 1 aligned
        try:
            val_double = struct.unpack('<d', data[i:i+8])[0]
            
            # Check for reasonable SCDateTime (Year 2020-2030)
            # 2020-01-01 is roughly 43831
            # 2030-01-01 is roughly 47483
            if 43800 < val_double < 47500:
                dt = sc_datetime_to_python(val_double)
                if dt:
                    print(f"Offset {i}: Double {val_double:.6f} -> Date {dt}")
            
            # Check for potential prices (e.g., ES price ~4000-6000, NQ ~15000-20000)
            if 100 < val_double < 30000:
                 # Filter out likely integers interpreted as doubles (very small exponents)
                 # Simpler check: is it close to an integer or .25, .50, .75?
                 rem = val_double % 0.25
                 if rem < 0.0001 or rem > 0.2499:
                     pass # plausible price
                     # print(f"Offset {i}: Potential Price {val_double:.2f}")

        except:
            pass


    # Analyze the structure around the first large string
    target_string = b"Trading Evaluator"
    idx = data.find(target_string)
    if idx != -1:
        print(f"\n--- STRUCTURE AROUND OFFSET {idx} ---")
        start = max(0, idx - 20)
        end = min(len(data), idx + 20)
        segment = data[start:end]
        print(f"Bytes: {segment.hex()}")
        print(f"Preceding bytes (int?): {data[idx-4:idx].hex()}")
        print(f"Preceding bytes (short?): {data[idx-2:idx].hex()}")
        
    print("\n--- STRUCTURAL SCAN ---")
    pos = 0
    while pos < len(data):
        # Read 4 bytes
        if pos + 4 > len(data): break
        val_int = struct.unpack('<I', data[pos:pos+4])[0]
        
        # Check if it is a string length?
        is_string = False
        if 0 < val_int < 1000 and pos + 4 + val_int <= len(data):
            try:
                candidate = data[pos+4 : pos+4+val_int]
                # Check for high printable ratio
                printable = sum(1 for b in candidate if 32 <= b < 127)
                if printable > 0 and printable >= val_int * 0.9:
                    print(f"[{pos:04d}] STRING (len={val_int}): {candidate.decode('ascii', errors='ignore')}")
                    pos += 4 + val_int
                    continue
            except:
                pass

        # If not string, check for timestamp (double)
        if pos + 8 <= len(data):
             val_double = struct.unpack('<d', data[pos:pos+8])[0]
             # Check for 1899-based date (approx 45000)
             if 40000 < val_double < 50000:
                  print(f"[{pos:04d}] DATE(1899) (val={val_double:.5f}): {sc_datetime_to_python(val_double)}")
             # Check for 1970-based date (approx 19000)
             if 18000 < val_double < 21000:
                  # Convert 1970-based double to date
                  try:
                      base_1970 = datetime.datetime(1970, 1, 1)
                      dt_1970 = base_1970 + datetime.timedelta(days=val_double)
                      print(f"[{pos:04d}] DATE(1970) (val={val_double:.5f}): {dt_1970}")
                  except: pass

        # Just print byte and advance
        # print(f"[{pos:04d}] BYTE   {data[pos]:02x}")
        pos += 1

if __name__ == "__main__":
    analyze_file()
