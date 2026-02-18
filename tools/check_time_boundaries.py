
import struct
import os

def check_time_tag_frequency():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    offset = 0
    tag_counts = {}
    fill_positions = []
    time_positions = []
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 102: time_positions.append(offset)
        if tag == 0x68:
            s = d[offset+8:offset+8+length].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                fill_positions.append(offset)
        offset += 8 + length

    print(f"Total Time (102) tags: {len(time_positions)}")
    print(f"Total Fill (0x68) tags: {len(fill_positions)}")
    
    if fill_positions and time_positions:
        # Check how many 102s between fills
        # Actually, check where the 102 is relative to the fill
        for f_pos in fill_positions[:5]:
            prev_102 = [t for t in time_positions if t < f_pos]
            next_102 = [t for t in time_positions if t > f_pos]
            print(f"Fill at {f_pos}: Prev 102 at {prev_102[-1] if prev_102 else 'N/A'}, Next 102 at {next_102[0] if next_102 else 'N/A'}")

if __name__ == "__main__":
    check_time_tag_frequency()
