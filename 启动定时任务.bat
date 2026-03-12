@echo off
chcp 65001 > nul
echo ========================================
echo 股票智能分析系统 - 定时任务模式
echo ========================================
echo.
echo 配置: 每天 18:00 自动执行分析
echo 模式: Web界面 + 定时任务
echo.
echo 提示: 程序将持续运行，按 Ctrl+C 可停止
echo ========================================
echo.
python main.py --schedule --webui
pause
