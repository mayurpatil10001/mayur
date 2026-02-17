
import os

def inspect(filename):
    print(f"--- {os.path.basename(filename)} ---")
    if not os.path.exists(filename):
        print("Not found")
        return
        
    with open(filename, 'r') as f:
        header = f.readline().strip().split('\t')
        row1 = f.readline().strip().split('\t')
        
    print(f"Header ({len(header)} cols): {header}")
    print(f"Row 1  ({len(row1)} cols): {row1}")
    
    # Check for target columns
    targets = ["Symbol", "Price", "DateTime", "Quantity", "OrderType"]
    for t in targets:
        if t in header:
            print(f"  Column '{t}' found at index {header.index(t)}")
        else:
            print(f"  [WARNING] Column '{t}' NOT FOUND")

def main():
    base = r"C:\SierraChart\SC results WF"
    f1 = os.path.join(base, "TradeActivityLogExport_2026-01-20_3Q_sim14.txt")
    f2 = os.path.join(base, "TradeActivityLogExport_2025-12-04_IPS_TM_5dupli.txt")
    
    inspect(f1)
    print("")
    inspect(f2)

if __name__ == "__main__":
    main()
