import os
import glob
import sys

# Add project root to path so we can import modules
sys.path.append(r"c:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro

def main():
    base_dir = r"C:\SierraChart\SC trading results Analysis\Data"
    print(f"Searching for .data files in {base_dir}...")
    
    data_files = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.data') and "TradeActivityLog" in f:
                data_files.append(os.path.join(root, f))
                
    print(f"Found {len(data_files)} TradeActivityLog.data files.")
    
    vsim_fills = []
    
    for df in data_files:
        try:
            fills = _parse_file_nitro(df, target_sym=None)
            for fill in fills:
                if 'V_sim16' in fill.get('account_name', ''):
                     vsim_fills.append(fill)
        except Exception as e:
            print(f"Error parsing {df}: {e}")
            
    vsim_fills.sort(key=lambda x: x['timestamp'])
    
    output_file = r"c:\SierraChart\SC results WF\debug\vsim16_fills_dump.txt"
    with open(output_file, 'w') as out:
        out.write(f"Total V_sim16 Fills found: {len(vsim_fills)}\n")
        out.write("-" * 80 + "\n")
        out.write(f"{'Time':<25} | {'Side':<5} | {'Price':<10} | {'Qty'}\n")
        out.write("-" * 80 + "\n")
        
        for f in vsim_fills:
            out.write(f"{f['timestamp']:<25} | {f['side']:<5} | {f['price']:<10} | {f['quantity']}\n")
            
    print(f"Done. Wrote {len(vsim_fills)} fills to {output_file}")

if __name__ == "__main__":
    main()
