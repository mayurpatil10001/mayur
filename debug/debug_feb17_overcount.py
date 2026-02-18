
import asyncio
import os
import sys

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

def compare_feb17():
    bin_file = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    txt_file = r'C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt'
    
    if not os.path.exists(bin_file) or not os.path.exists(txt_file):
        print("Files missing.")
        return

    # Parse Binary
    # Use target_sym="CL" to match what the importer does
    fills_bin = _parse_file_nitro(bin_file, target_sym="CL")
    
    # Parse TXT
    fills_txt = []
    with open(txt_file, 'r') as f:
        header = f.readline().split('\t')
        try:
            q_idx = header.index('Quantity')
            fq_idx = header.index('FilledQuantity')
            t_idx = header.index('DateTime')
            s_idx = header.index('Symbol')
            p_idx = header.index('Price')
            side_idx = header.index('BuySell')
        except:
            print("TXT Header error.")
            return
            
        for line in f:
            parts = line.split('\t')
            if len(parts) > p_idx and parts[0] == 'Fills':
                if "CL" not in parts[s_idx]: continue
                if not parts[p_idx].strip(): continue
                qty_str = parts[fq_idx].strip() if parts[fq_idx].strip() else parts[q_idx].strip()
                if not qty_str: continue
                fills_txt.append({
                    'time': parts[t_idx],
                    'qty': int(float(qty_str)),
                    'price': float(parts[p_idx]),
                    'side': parts[side_idx].upper()
                })

    fills_txt_day = [f for f in fills_txt if "2026-02-17" in f['time']]

    print(f"Binary Fills: {len(fills_bin)}, Total Qty: {sum(f['quantity'] for f in fills_bin)}")
    print(f"TXT Fills (Cumulative): {len(fills_txt)}, Total Qty: {sum(f['qty'] for f in fills_txt)}")
    print(f"TXT Fills (Feb 17): {len(fills_txt_day)}, Total Qty: {sum(f['qty'] for f in fills_txt_day)}")
    
    if len(fills_bin) > 0:
        print("\nFirst 5 Binary Fills:")
        for f in fills_bin[:5]:
            print(f"  {f['timestamp']} | {f['side']} {f['quantity']} at {f['price']} | OID: {f['order_id']}")

    if len(fills_txt) > 0:
        print("\nFirst 5 TXT Fills:")
        for f in fills_txt[:5]:
            print(f"  {f['time']} | {f['side']} {f['qty']} at {f['price']}")

if __name__ == "__main__":
    compare_feb17()
