@echo off
chcp 65001 > nul
echo ========================================
echo 新增技术指标测试
echo ========================================
echo.
echo 测试指标：
echo   - 布林带（BOLL）
echo   - KDJ 指标
echo   - ATR 波动率
echo.
echo 正在运行测试...
echo ========================================
echo.
python test_new_indicators.py
echo.
echo ========================================
echo 测试完成！
echo ========================================
pause
