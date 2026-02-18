
import os
import glob
import re

def count_files():
    path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    pattern = '*TradeActivityLog*3Q_SIM14*'
    
    # Case-insensitive glob for the pattern
    files = glob.glob(os.path.join(path, '*TradeActivityLog*3Q_SIM14*'), recursive=False)
    # Also check lowercase just in case glob is strict on this OS (it usually is case-sensitive on Linux, insensitive on Windows but let's be safe)
    files_lower = glob.glob(os.path.join(path, '*TradeActivityLog*3Q_sim14*'), recursive=False)
    
    all_files = list(set(files + files_lower))
    all_files.sort()
    
    print(f"Total SIM14 files found: {len(all_files)}")
    if all_files:
        print(f"Oldest: {all_files[0]}")
        print(f"Newest: {all_files[-1]}")
        
    # Count files per year/month
    distribution = {}
    for f in all_files:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f))
        if match:
            date_str = match.group(1)
            year_month = date_str[:7]
            distribution[year_month] = distribution.get(year_month, 0) + 1
            
    print("\nFile distribution by Year-Month:")
    for ym in sorted(distribution.keys()):
        print(f"{ym}: {distribution[ym]} files")

if __name__ == "__main__":
    count_files()
