import sys
import os

# Add service directory to path to import binary_log_parser
sys.path.append(r"c:\SierraChart\SC results WF\trading_platform\services")

# Import
import binary_log_parser as blp

print(f"Module file: {blp.__file__}")

file_path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data"

if os.path.exists(file_path):
    print(f"File exists: {file_path}")
    print(f"Size: {os.path.getsize(file_path)}")
    try:
        fills = blp._parse_file_nitro(file_path, target_sym=None)
        print(f"Fills found: {len(fills)}")
        if fills:
            print(f"Total fills: {len(fills)}")
            for i, f in enumerate(fills[:10]):
                print(f"Fill {i}: {f['timestamp']} {f['side']} {f['quantity']} @ {f['price']} ({f['symbol']})")
        else:
            print("No fills found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("File not found")
