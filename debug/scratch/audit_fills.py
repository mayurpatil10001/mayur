import asyncio
from trading_platform.services.binary_log_parser import _parse_file_nitro

def test_parser():
    fills, ghost_counts = _parse_file_nitro("D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2026-02-25_UTC.V_sim16.data", "NQ")
    
    print(f"Total fills extracted: {len(fills)}")
    for f in fills[:30]:
        print(f"\n{f['timestamp']} | Side: {f['side']} | Qty: {f['quantity']} | P: {f['price']} | Conf: {f.get('confirmed')}")

if __name__ == "__main__":
    test_parser()
