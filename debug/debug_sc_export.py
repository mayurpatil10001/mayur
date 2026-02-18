import pandas as pd

def debug_sc(filepath):
    try:
        df = pd.read_csv(filepath, sep='\t', low_memory=False)
        print(f"Total Rows: {len(df)}")
        print("Columns:", df.columns.tolist())
        if 'ActivityType' in df.columns:
            print("Unique ActivityTypes:")
            print(df['ActivityType'].value_counts())
        
        # Check if 'Symbol' exists and counts
        if 'Symbol' in df.columns:
            print("\nTop 10 Symbols:")
            print(df['Symbol'].value_counts().head(10))

        # Check Orders with Status Filled
        if 'ActivityType' in df.columns and 'OrderStatus' in df.columns:
            filled_orders = df[(df['ActivityType'] == 'Orders') & (df['OrderStatus'] == 'Filled')]
            print(f"\nOrders with Status 'Filled': {len(filled_orders)}")
            
            fills = df[df['ActivityType'] == 'Fills']
            print(f"ActivityType 'Fills': {len(fills)}")
            
            # Check overlap of InternalOrderID
            order_ids_orders = set(filled_orders['InternalOrderID'].unique())
            order_ids_fills = set(fills['InternalOrderID'].unique())
            
            print(f"Unique OrderIDs in Filled Orders: {len(order_ids_orders)}")
            print(f"Unique OrderIDs in Fills: {len(order_ids_fills)}")
            print(f"Intersection: {len(order_ids_orders & order_ids_fills)}")
            print(f"In Orders but NOT in Fills: {len(order_ids_orders - order_ids_fills)}")
            print(f"In Fills but NOT in Orders: {len(order_ids_fills - order_ids_orders)}")

            print(f"In Fills but NOT in Orders: {len(order_ids_fills - order_ids_orders)}")

        # Check AccountBalance
        if 'AccountBalance' in df.columns:
            print("\nAccountBalance Sample:")
            print(df['AccountBalance'].head(10))
            print("Non-Null Count:", df['AccountBalance'].count())
            # Convert to numeric
            bals = pd.to_numeric(df['AccountBalance'], errors='coerce')
            print("Numeric Non-Zero Count:", bals[bals != 0].count())
            print("Sample Numeric:", bals[bals != 0].head())

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_sc(r"C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt")
