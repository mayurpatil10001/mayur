
import os

def search_oids():
    txt_file = r'C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt'
    # Binary OIDs found in debug_feb17_overcount
    target_oids = ["40048875.1", "40048879.1", "40049191.1", "40050616.1"]
    
    with open(txt_file, 'r') as f:
        for line in f:
            for oid in target_oids:
                if oid in line:
                    ltype = line.split('\t')[0]
                    print(f"FOUND OID {oid} in line type: {ltype}")
                    print(f"  FULL: {line.strip()[:200]}")

if __name__ == "__main__":
    search_oids()
