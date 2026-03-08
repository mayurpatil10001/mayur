import requests
import os

file_path = r'D:\SierraChart_Simulated_Feed\SavedTradeActivity\NQ_V_sim16_20240101-20250716.txt'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
else:
    # Try multiple encodings
    text = None
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                text = f.read()
            print(f"Read file with {enc}")
            break
        except:
            continue
    
    if text is None:
        print("Failed to read file with any encoding.")
    elif len(text) < 100:
        print("File is too short.")
    else:
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
