import os

def search_date():
    target_file = r"C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt"
    with open(target_file, "r") as f:
        for i, line in enumerate(f):
            if "2025-12-18" in line:
                print(f"Line {i}: {line.strip()}")
                return
    print("Date not found.")

if __name__ == "__main__":
    search_date()
