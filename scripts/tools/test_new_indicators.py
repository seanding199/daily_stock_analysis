# -*- coding: utf-8 -*-
"""
测试新增技术指标（BOLL/KDJ/ATR）

使用方法：
python test_new_indicators.py
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def generate_test_data(days=60):
    """生成测试数据"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    np.random.seed(42)
    
    # 模拟多头趋势数据
    base_price = 15.0
    prices = [base_price]
    
    for i in range(days - 1):
        # 轻微上涨趋势 + 随机波动
        change = np.random.randn() * 0.02 + 0.003
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'date': dates,
        'open': [p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
        'high': [p * (1 + np.random.uniform(0.01, 0.03)) for p in prices],
        'low': [p * (1 - np.random.uniform(0.01, 0.03)) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in prices],
    })
    
    return df


def test_individual_indicators():
    """测试独立指标"""
    print("\n" + "=" * 80)
    print("测试独立技术指标")
    print("=" * 80)
    
    df = generate_test_data(60)
    
    try:
        # 测试布林带
        from src.indicators import BOLLIndicator
        boll = BOLLIndicator()
        boll_result = boll.calculate(df)
        
        print("\n📊 布林带（BOLL）测试")
        print("-" * 80)
        if boll_result:
            print(f"✅ 布林带计算成功")
            print(f"   上轨: {boll_result.upper:.2f}")
            print(f"   中轨: {boll_result.middle:.2f}")
            print(f"   下轨: {boll_result.lower:.2f}")
            print(f"   当前价: {boll_result.current_price:.2f}")
            print(f"   位置: {boll_result.position_pct:.1f}%")
            print(f"   带宽: {boll_result.bandwidth:.2f}%")
            print(f"   状态: {boll_result.status.value}")
            print(f"   信号: {boll_result.signal}")
        else:
            print("❌ 布林带计算失败")
            
    except Exception as e:
        print(f"❌ 布林带测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试 KDJ
        from src.indicators import KDJIndicator
        kdj = KDJIndicator()
        kdj_result = kdj.calculate(df)
        
        print("\n📈 KDJ 指标测试")
        print("-" * 80)
        if kdj_result:
            print(f"✅ KDJ 计算成功")
            print(f"   K值: {kdj_result.k:.2f}")
            print(f"   D值: {kdj_result.d:.2f}")
            print(f"   J值: {kdj_result.j:.2f}")
            print(f"   状态: {kdj_result.status.value}")
            print(f"   信号: {kdj_result.signal}")
            print(f"   买入强度: {'★' * kdj_result.buy_strength}{'☆' * (5-kdj_result.buy_strength)} ({kdj_result.buy_strength}/5)")
            print(f"   卖出强度: {'★' * kdj_result.sell_strength}{'☆' * (5-kdj_result.sell_strength)} ({kdj_result.sell_strength}/5)")
        else:
            print("❌ KDJ 计算失败")
            
    except Exception as e:
        print(f"❌ KDJ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试 ATR
        from src.indicators import ATRIndicator
        atr = ATRIndicator()
        atr_result = atr.calculate(df)
        
        print("\n📊 ATR 波动率测试")
        print("-" * 80)
        if atr_result:
            print(f"✅ ATR 计算成功")
            print(f"   ATR值: {atr_result.atr:.2f}")
            print(f"   ATR占比: {atr_result.atr_pct:.2f}%")
            print(f"   波动等级: {atr_result.level.value}")
            print(f"   风险等级: {atr_result.risk_level}")
            print(f"   止损位: {atr_result.stop_loss_2atr:.2f} (2倍ATR)")
            print(f"   止盈位: {atr_result.take_profit_3atr:.2f} (3倍ATR)")
            print(f"   信号: {atr_result.signal}")
        else:
            print("❌ ATR 计算失败")
            
    except Exception as e:
        print(f"❌ ATR 测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_integrated_analysis():
    """测试集成到股票分析器"""
    print("\n" + "=" * 80)
    print("测试集成分析器")
    print("=" * 80)
    
    df = generate_test_data(60)
    
    try:
        from src.stock_analyzer import StockTrendAnalyzer
        
        analyzer = StockTrendAnalyzer()
        result = analyzer.analyze(df, 'TEST001')
        
        print("\n✅ 集成分析完成")
        print("\n" + analyzer.format_analysis(result))
        
    except Exception as e:
        print(f"❌ 集成分析失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("=" * 80)
    print("新增技术指标测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试指标: BOLL（布林带）、KDJ、ATR（波动率）")
    
    # 测试独立指标
    test_individual_indicators()
    
    # 测试集成分析
    test_integrated_analysis()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == '__main__':
    main()
