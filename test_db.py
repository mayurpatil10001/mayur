import sqlite3
import pandas as pd
conn = sqlite3.connect('trading_platform.db')
print(pd.read_sql("SELECT * FROM system_settings", conn).T)
