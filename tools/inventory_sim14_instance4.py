
import os
import glob
import re

def count_files_instance4():
    path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs'
    files = glob.glob(os.path.join(path, '*3Q_sim14*'), recursive=False)
    all_files = list(set(files))
    all_files.sort()
    
    print(f"Total SIM14 files in Instance 4: {len(all_files)}")
    if all_files:
        print(f"Oldest: {all_files[0]}")
        print(f"Newest: {all_files[-1]}")
        
    distribution = {}
    for f in all_files:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f))
        if match:
            date_str = match.group(1)
            year_month = date_str[:7]
            distribution[year_month] = distribution.get(year_month, 0) + 1
            
    print("\nFile distribution by Year-Month (Instance 4):")
    for ym in sorted(distribution.keys()):
        print(f"{ym}: {distribution[ym]} files")

if __name__ == "__main__":
    count_files_instance4()
