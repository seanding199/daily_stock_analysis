import sqlite3
import datetime
conn = sqlite3.connect('data/stock_analysis.db')
today = datetime.datetime.now().strftime('%Y-%m-%d')
result = conn.execute('DELETE FROM analysis_history WHERE DATE(created_at) = ?', (today,))
conn.commit()
print(f'已删除今日的 {conn.total_changes} 条记录')
conn.close()
