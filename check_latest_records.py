import sqlite3
conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.execute('SELECT code, name, report_type, created_at FROM analysis_history WHERE DATE(created_at) >= "2026-02-10" ORDER BY created_at DESC LIMIT 10')
rows = cursor.fetchall()
print(f'找到 {len(rows)} 条记录:')
for row in rows:
    print(f'  {row}')
conn.close()
