import requests
import os

file_path = r'D:\SierraChart_Simulated_Feed\SavedTradeActivity\NQ_V_sim16_20240101-20250716.txt'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
else:
    with open(file_path, 'r', encoding='utf-16', errors='ignore') as f:
        # SC exports are often UTF-16, but sometimes ANSI.
        # Let's try to detect or just use errors='ignore' with standard utf-8/latin1?
        # Actually, let's try a safe read.
        text = f.read()
    
    # If the file was empty or header only, skip
    if len(text) < 100:
        print("File is too short.")
    else:
        # Use Latin-1 if UTF-16 fails or just try to send
        payload = {"text": text}
        r = requests.post('http://localhost:8000/api/v1/trade-import/import-paste', json=payload)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Imported: {data.get('new_trades', 0)}")
            print(f"Duplicates: {data.get('duplicates', 0)}")
            print(f"Errors: {len(data.get('errors', []))}")
        else:
            print(f"Error: {r.text}")
