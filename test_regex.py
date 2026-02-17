import re
filename = "TradeActivityLog_2026-02-13_UTC.NQ-TM_3.data"
sym = "NQ"
print(f"Testing {sym} in {filename}")
pattern = rf"[._]{sym}[.\-_]"
match = re.search(pattern, filename)
print(f"Match: {match}")

filename2 = "TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"
sym2 = "ES"
print(f"Testing {sym2} in {filename2}")
match2 = re.search(rf"[._]{sym2}[.\-_]", filename2)
print(f"Match: {match2}")
