import pandas as pd

def check_columns(filepath):
    print(f"Reading {filepath}...")
    try:
        df = pd.read_csv(filepath, sep='\t', nrows=5)
        print("Columns found:")
        for col in df.columns:
            print(f" - {col}")
            
        # Check for commission-like columns
        comm_cols = [c for c in df.columns if 'comm' in c.lower() or 'fee' in c.lower()]
        if comm_cols:
            print(f"\nPotential Commission Columns: {comm_cols}")
        else:
            print("\nNo explicit Commission/Fee columns found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_columns(r"C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt")
