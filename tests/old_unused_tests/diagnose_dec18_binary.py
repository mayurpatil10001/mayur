"""
One-off diagnostic: dump Tag 102/100/124/104/107 for Dec 18 V_SIM16 binary
to see why order_id and canceled_order_ids are not populated.
"""
import os
import struct
import sys

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_platform.services.binary_log_parser import _parse_tag66_timestamp

def run(base_path: str):
    path = os.path.join(base_path, "TradeActivityLog_2025-12-18_UTC.V_sim16.data")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    with open(path, "rb") as f:
        d = f.read(50 * 1024 * 1024)
    file_len = len(d)
    offset = 0
    # Per-record state (reset on Tag 102/0x66)
    rec_ts = None
    rec_oid = None
    rec_tag107 = None
    rec_msgs = []
    out_lines = []
    while offset < file_len - 8:
        try:
            tag, length = struct.unpack('<II', d[offset : offset+8])
            if tag == 0 or tag > 512 or length > 65536:
                next_ptr = d.find(b'\x66\x00\x00\x00', offset + 1)
                if next_ptr == -1:
                    break
                offset = next_ptr
                continue
            val_start = offset + 8
            val_end = val_start + length
            if val_end > file_len:
                break
            if tag == 102 or tag == 0x66:
                # Flush previous record if interesting
                if rec_ts is not None and (rec_msgs or rec_oid):
                    msg_flat = " ".join(rec_msgs).lower()
                    if "simulation fill" in msg_flat or "cancel" in msg_flat or "marking as" in msg_flat or "order update" in msg_flat:
                        out_lines.append({
                            "ts": str(rec_ts),
                            "oid": rec_oid,
                            "tag107": rec_tag107,
                            "msg": " ".join(rec_msgs)[:200],
                        })
                # Start new record
                new_dt = _parse_tag66_timestamp(d[val_start:val_end])
                rec_ts = new_dt
                rec_oid = None
                rec_tag107 = None
                rec_msgs = []
            elif tag == 100 or tag == 124:
                rec_oid = d[val_start:val_end].decode(errors='ignore').strip()
            elif tag == 107:
                rec_tag107 = d[val_start:val_end].decode(errors='ignore').strip()
            elif tag == 104 or tag == 0x68:
                s = d[val_start:val_end].decode(errors='ignore')
                rec_msgs.append(s)
            offset = val_end
        except Exception as e:
            break
    # Last record
    if rec_ts is not None and (rec_msgs or rec_oid):
        msg_flat = " ".join(rec_msgs).lower()
        if "simulation fill" in msg_flat or "cancel" in msg_flat or "marking as" in msg_flat or "order update" in msg_flat:
            out_lines.append({
                "ts": str(rec_ts),
                "oid": rec_oid,
                "tag107": rec_tag107,
                "msg": " ".join(rec_msgs)[:200],
            })
    return out_lines

if __name__ == "__main__":
    import json
    base = os.environ.get("SC_LOG_PATH", "D:\\SierraChart_Simulated_Feed\\TradeActivityLogs")
    # Try app_settings if path missing
    if not os.path.exists(base):
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_settings.json")) as f:
                import json as j
                cfg = j.load(f)
                for s in cfg.get("scanners", []):
                    if s.get("symbol") == "NQ":
                        base = s.get("path", base)
                        break
        except Exception:
            pass
    lines = run(base)
    print("Records with 'simulation fill' or 'cancel' / 'marking as' / 'order update':")
    for i, r in enumerate(lines):
        print(f"  [{i}] ts={r['ts']} order_id={r['oid']!r} tag107={r['tag107']!r}")
        print(f"      msg={r['msg'][:180]!r}")
