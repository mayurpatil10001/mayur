
import os

def inspect(filename):
    print(f"--- {filename} ---")
    if not os.path.exists(filename):
        print("Not found")
        return
    with open(filename, 'r') as f:
        for i in range(5):
            line = f.readline()
            if not line: break
            print(f"Line {i+1}: {line.strip()}")

def main():
    inspect("3q_sim14_01192026_TradesList.txt")
    inspect("IPS_TM_5_dupli_03122025_TradesList.txt")

if __name__ == "__main__":
    main()
