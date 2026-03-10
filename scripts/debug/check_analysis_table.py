import sqlite3
conn = sqlite3.connect('data/stock_analysis.db')
print("analysis_history 表结构:")
cursor = conn.execute('PRAGMA table_info(analysis_history)')
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")
print("\n最近3条记录:")
cursor = conn.execute('SELECT * FROM analysis_history ORDER BY created_at DESC LIMIT 3')
for row in cursor.fetchall():
    print(row[:5])  # 只打印前5列
conn.close()
