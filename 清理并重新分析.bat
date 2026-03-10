@echo off
chcp 65001 >nul 2>&1
echo ================================================================================
echo                         清理旧数据并重新分析
echo ================================================================================
echo.
echo [1/3] 正在删除今日旧分析数据...
python -c "import sqlite3; import datetime; conn = sqlite3.connect('data/stock_analysis.db'); today = datetime.datetime.now().strftime('%%Y-%%m-%%d'); conn.execute('DELETE FROM analysis_history WHERE DATE(created_at) = ?', (today,)); conn.commit(); print(f'  已删除今日（{today}）的 {conn.total_changes} 条旧记录'); conn.close()"
echo.
echo [2/3] 正在启动分析（包含新指标）...
echo     提示: Gemini API 配额已用完，AI 分析可能失败
echo     但新指标数据会被计算并存储到数据库
echo.
python main.py --once
echo.
echo [3/3] 查看新指标数据...
python view_latest_analysis.py
echo.
echo ================================================================================
echo 完成！
echo ================================================================================
pause
