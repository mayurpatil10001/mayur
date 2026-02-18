
import re
from datetime import datetime

raw_text = """
Fills	2026-02-17 18:00:03.621235	2026-02-17 18:00:04.000000	21150203	Market	3
Filled	3Q_sim14	Buy	62.26	3	Order update (Filled). Info: Trading Evaluator (Filled). Info: Trade simulation fill. Bid: 62.23 Ask: 62.26 Last: 62.23	21105928
CLH26	Close	40092359.1	62.26	62.23	0.00	40092359	21105928.94042
Day	shimihson	Y
Fills	2026-02-17 20:03:10.742144	2026-02-17 20:03:13.000000	21150860	Market	3
Filled	3Q_sim14	Buy	62.37	3	AutoTrader_	Order update (Filled). Info: Trading Evaluator (Filled). Info: Trade simulation fill. Bid: 62.36 Ask: 62.37 Last: 62.37. Text: Tag: AutoTrader_. Text: Tag: AutoTrader_	21106585	CLH26	Open	3	40093226.1	0.00	40093226	21106585.97357	Good till Canceled	shimihson	Y
Fills	2026-02-17 23:38:27.623730	2026-02-17 23:38:27.000000	21150872	Limit	1
Filled	3Q_sim14	Sell	62.57	62.57	1	AutoTrader_	Order update (Filled). Info: Trading Evaluator (Filled). Info: Trade simulation fill. Bid: 62.56 Ask: 62.57 Last: 62.56. Fill based on queue. Text: Tag: AutoTrader_. Text: Tag: AutoTrader_	21106597	CLH26	Close	2	40093239.1	62.58	62.26	0.00	40093239	21106597.13433	Good till Canceled	shimihson	Y
"""

def parse_activity_log(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    fills = []
    
    current_time = None
    
    for line in lines:
        parts = re.split(r'\t|\s{2,}', line) # Split by tab or multiple spaces
        
        if line.startswith("Fills"):
            # Format: 'Fills', '2026-02-17 18:00:03.621235', ...
            if len(parts) >= 2:
                try:
                    current_time = datetime.strptime(parts[1], "%Y-%m-%d %H:%M:%S.%f")
                except:
                    current_time = None
                    
        elif line.startswith("Filled"):
            # Format: 'Filled', '3Q_sim14', 'Buy', '62.26', '3', 'Info...'
            # CAUTION: The screenshot has tab separation likely.
            # Let's try to extract by index.
            if len(parts) >= 5:
                # parts[5] contains the message which contains Symbol usually or it is in parts[6+]?
                # In screenshot: "CLH26 Close" is on the NEXT line sometimes, or end of line.
                # In the 2nd example: "CLH26 Open" is later in the same line after "AutoTrader_ ...".
                
                # Check for Symbol in line or next line? 
                # The text snippet provided in the screenshot shows:
                # Line 1: Fills ...
                # Line 2: Filled ... CLH26 Close (Separate line?) NO, looks like wrapped text or separate line.
                
                # Let's search for Symbol strictly in the line.
                symbol_m = re.search(r'([A-Z]+[HMZ]2\d)', line)
                symbol = symbol_m.group(1) if symbol_m else "UNKNOWN"
                
                # If symbol not found in 'Filled' line, look at previous 'Fills' line? No.
                # Look at next line?
                
                acc = parts[1]
                side = parts[2]
                try:
                    price = float(parts[3])
                    qty = int(parts[4])
                except:
                    continue
                
                if current_time:
                    fills.append({
                        "time": current_time,
                        "account": acc,
                        "side": side,
                        "price": price,
                        "qty": qty,
                        "symbol": symbol
                    })
    return fills

fills = parse_activity_log(raw_text)
print(f"Parsed {len(fills)} fills")
for f in fills:
    print(f)

