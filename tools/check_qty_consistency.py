
import struct
import os

def check_diverse_quantities():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    with open(file_path, "rb") as bf:
        d = bf.read()
        
    all_tags = []
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        all_tags.append({'tag': tag, 'len': length, 'off': offset})
        offset += 8 + length

    fill_count = 0
    for i, t_info in enumerate(all_tags):
        if t_info['tag'] == 0x68:
            vs = t_info['off'] + 8
            ve = vs + t_info['len']
            s = d[vs:ve].decode(errors='ignore')
            if "trade simulation fill" in s.lower() or "processed execution report" in s.lower():
                print(f"\nFill at {t_info['off']}: {s.strip()[:60]}...")
                # Look for Tag 108, 114, 126 nearby
                for j in range(i - 10, i + 30):
                    if 0 <= j < len(all_tags):
                        info = all_tags[j]
                        if info['tag'] in [108, 114, 126]:
                            vs_j = info['off'] + 8
                            ve_j = vs_j + info['len']
                            if info['len'] == 8:
                                v = struct.unpack('<d', d[vs_j:ve_j])[0]
                            elif info['len'] == 4:
                                v = struct.unpack('<i', d[vs_j:ve_j])[0]
                            else: v = "Unknown"
                            print(f"  Tag {info['tag']} at {info['off']} = {v}")
                fill_count += 1
                if fill_count >= 10: break

if __name__ == "__main__":
    check_diverse_quantities()
