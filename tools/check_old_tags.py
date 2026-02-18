
import struct
import os

def check_old_file_tags():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-08-12_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(5 * 1024 * 1024)
        
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 0x68:
            s = d[offset+8:offset+8+length].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"\nFill at {offset}")
                # Look for Tag 126 or others
                scan_offset = offset
                found_tags = []
                # Scan next 500 bytes
                scan_limit = min(len(d), offset + 1000)
                while scan_offset < scan_limit - 8:
                    t, l = struct.unpack('<II', d[scan_offset:scan_offset+8])
                    if t in [108, 114, 126]:
                        vs = scan_offset + 8
                        if l == 4: v = struct.unpack('<i', d[vs:vs+4])[0]
                        elif l == 8: v = struct.unpack('<d', d[vs:vs+8])[0]
                        else: v = "???"
                        found_tags.append(f"Tag {t}={v}")
                    scan_offset += 8 + l
                print(f"  Nearby tags: {found_tags}")
                if len(found_tags) > 0: break
        offset += 8 + length

if __name__ == "__main__":
    check_old_file_tags()
