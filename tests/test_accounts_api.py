#!/usr/bin/env python3
"""
Test script to check if the accounts API is returning temporal performance data.
"""

import requests
import json

def test_accounts_api():
    """Test the accounts API endpoint."""
    try:
        print("Testing accounts API on port 3001...")
        response = requests.get('http://localhost:3001/api/v1/accounts/?size=5')
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            
            if data.get('data') and data['data'].get('items'):
                items = data['data']['items']
                print(f"Number of accounts: {len(items)}")
                print("\nAccount Details:")
                print("-" * 80)
                
                for i, account in enumerate(items[:5]):
                    name = account['name']
                    symbol = account['symbol']
                    best_day = account.get('best_day_of_week')
                    best_hour = account.get('best_hour_of_day')
                    total_pnl = account.get('total_pnl', 0)
                    
                    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    day_name = day_names[best_day] if best_day is not None else 'N/A'
                    hour_display = f"{best_hour}:00" if best_hour is not None else 'N/A'
                    
                    print(f"{i+1}. {name} ({symbol})")
                    print(f"   Total P&L: ${total_pnl:.2f}")
                    print(f"   Best Day: {day_name} ({best_day})")
                    print(f"   Best Hour: {hour_display} ({best_hour})")
                    print()
                    
                # Check if any account has temporal data
                has_temporal_data = any(
                    account.get('best_day_of_week') is not None or 
                    account.get('best_hour_of_day') is not None 
                    for account in items
                )
                
                if has_temporal_data:
                    print("✅ SUCCESS: API is returning temporal performance data!")
                else:
                    print("❌ ISSUE: API is still returning None for best day/hour")
                    
            else:
                print("No account data found in response")
                
        else:
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to API on port 3001")
        print("Make sure the API server is running with:")
        print("python -m uvicorn trading_platform.api.main:app --host 0.0.0.0 --port 3001 --reload")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_accounts_api()