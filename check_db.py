import sqlite3
conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print("数据库表列表:", tables)

if tables:
    table_name = tables[0]
    print(f"\n{table_name} 表结构:")
    cursor = conn.execute(f'PRAGMA table_info({table_name})')
    for row in cursor.fetchall():
        print(f"  {row[1]} ({row[2]})")
conn.close()
