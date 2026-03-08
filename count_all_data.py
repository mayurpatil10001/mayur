import os
import glob

base_path = r'D:\SierraChart_Simulated_Feed'
instances = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and 'SierraChartInstance' in d]
instances.append('.') # Check base folder too

for inst in instances:
    path = os.path.join(base_path, inst, 'TradeActivityLogs')
    if os.path.exists(path):
        files = glob.glob(os.path.join(path, '*V_sim16*.data'))
        data_count = len([f for f in files if os.path.getsize(f) > 193])
        print(f"{inst}: {data_count} data files")
