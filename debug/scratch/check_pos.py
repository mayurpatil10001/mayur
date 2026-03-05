
import sys, os
from pathlib import Path
sys.path.insert(0, 'C:/SierraChart/SC results WF')
import struct

f = 'D:/SierraChart_Simulated_Feed/TradeActivityLogs/TradeActivityLog_2025-12-18_UTC.V_sim16.data'

def dump_pos():
    with open(f, 'rb') as fd:
        while True:
            header = fd.read(4)
            if not header: break
            size = struct.unpack('<H', header[:2])[0]
            if size == 0: break
            data = header + fd.read(size - 4)
            
            # This is a bit too raw. Let's just import the nitro parser
            pass

dump_pos()
