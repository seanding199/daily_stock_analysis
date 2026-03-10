@echo off
chcp 65001 > nul
echo 正在启动股票智能分析系统 Web 界面...
echo.
python main.py --webui
pause
