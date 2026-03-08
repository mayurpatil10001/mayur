import os

path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\Data\ES Production (02282024 1.3) PB.Cht_ES_PB_3_Autotrader V1.3.txt'
if not os.path.exists(path):
    print("File not found.")
else:
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            if 'V_sim16' in line.lower():
                print(line)
                break
        else:
            print("Not found in file.")
