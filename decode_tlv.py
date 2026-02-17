
import struct
import datetime

# Hex bytes from the previous output for Tag 0x66
# 21 FA 1C E8 E9 23 0E 00
# Let's try to decode reasonable timestamps from this.

data = bytes.fromhex("21 FA 1C E8 E9 23 0E 00")

# Try Double (SCDateTime format?)
try:
    val_double = struct.unpack('<d', data)[0]
    print(f"Double: {val_double}")
    # SCDateTime: Days since 1899-12-30
    # 25569 days offset for UNIX epoch (1970-01-01)
    # If val_double is around 45000-46000 (roughly 2023-2026), it's SCDateTime
    if 40000 < val_double < 60000:
        base_date = datetime.datetime(1899, 12, 30)
        dt = base_date + datetime.timedelta(days=val_double)
        print(f"SCDateTime -> {dt}")
except Exception as e:
    print(f"Double error: {e}")

# Try Int64 (Windows FileTime / UNIX micros?)
try:
    val_int64 = struct.unpack('<q', data)[0]
    print(f"Int64: {val_int64}")
    # UNIX Micros?
    # 1700000000000000 -> 2023?
except: pass

# Maybe the timestamp is in Tag 0x66 but 4 bytes? The Length was 8.
# 66 00 00 00 08 00 00 00...
