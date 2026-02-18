
import os
import glob

def check_folder_distribution():
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    for fld in folders:
        if os.path.exists(fld):
            files = glob.glob(os.path.join(fld, '*3Q_sim14.data'))
            # Filter for date range
            files = [f for f in files if "TradeActivityLog_20" in f and os.path.basename(f)[17:27] >= "2024-08-13"]
            print(f"Folder {fld}: {len(files)} files")

if __name__ == "__main__":
    check_folder_distribution()
