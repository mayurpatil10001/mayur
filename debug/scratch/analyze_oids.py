import struct

def find_order_ids(path, limit=None):
    with open(path, "rb") as f:
        data = f.read()
    
    offset = 0
    records = []
    current_record = {}
    
    while offset < len(data) - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102:
            if "oid" in current_record:
                records.append(current_record)
            current_record = {}
            
        if val_end > len(data): break
        
        if tag == 100 or tag == 124:
            try:
                current_record["oid"] = data[val_start:val_end].decode(errors='ignore').strip()
            except: pass
        if tag in [108, 114, 126]:
            try:
                if length == 4: current_record["qty"] = struct.unpack('<i', data[val_start:val_end])[0]
                elif length == 8: current_record["qty"] = struct.unpack('<d', data[val_start:val_end])[0]
            except: pass
            
        offset = val_end
    
    from collections import Counter
    oids = [r["oid"] for r in records if r.get("oid")]
    counts = Counter(oids)
    
    print("\nDuplicate Order IDs (Top 20):")
    dupes_cnt = 0
    for oid, count in counts.most_common(20):
        if count > 1:
            print(f"  ID {oid:15} | Count: {count}")
            dupes_cnt += 1
    
    print(f"\nTotal Records with OIDs: {len(records)}")
    print(f"Unique OIDs: {len(counts)}")
    print(f"Total Double/Triple Reports: {sum(c-1 for c in counts.values())}")

find_order_ids(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
