
import struct
import os

def inventory_tags():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    all_tags = []
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        all_tags.append({'tag': tag, 'len': length, 'off': offset})
        offset += 8 + length

    # Find fill message
    for i, t_info in enumerate(all_tags):
        if t_info['tag'] == 0x68:
            vs = t_info['off'] + 8
            ve = vs + t_info['len']
            s = d[vs:ve].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"\n--- MATCH AT INDEX {i}, OFFSET {t_info['off']} ---")
                print(f"MSG: {s.strip()}")
                
                # Check 20 tags before and after
                start_i = max(0, i - 10)
                end_i = min(len(all_tags), i + 20)
                
                for j in range(start_i, end_i):
                    info = all_tags[j]
                    vs_j = info['off'] + 8
                    ve_j = vs_j + info['len']
                    t_j = info['tag']
                    l_j = info['len']
                    
                    if l_j == 4:
                         v = struct.unpack('<i', d[vs_j:ve_j])[0]
                         print(f"  [{j}] Tag {t_j:3} [off={info['off']:5}]: {v}")
                    elif l_j == 8:
                         v = struct.unpack('<d', d[vs_j:ve_j])[0]
                         print(f"  [{j}] Tag {t_j:3} [off={info['off']:5}]: {v:.2f}")
                    elif t_j == 0x68:
                         print(f"  [{j}] Tag {t_j:3} [off={info['off']:5}]: String={d[vs_j:ve_j].decode(errors='ignore').strip()[:50]}")
                    else:
                         print(f"  [{j}] Tag {t_j:3} [off={info['off']:5}]: Len={l_j}, Hex={d[vs_j:ve_j].hex()[:20]}")
                break

if __name__ == "__main__":
    inventory_tags()
