#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
展示新指标分析结果（无需 API 调用）
"""
import os
import sys
from datetime import datetime

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.stock_analyzer import StockTrendAnalyzer
from data_provider import DataFetcherManager
from dotenv import load_dotenv

load_dotenv()

def display_indicators():
    """展示新指标分析"""
    print("=" * 100)
    print(f"{'新增技术指标分析展示':^96}")
    print("=" * 100)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 初始化
    analyzer = StockTrendAnalyzer()
    provider = DataFetcherManager()
    
    # 2. 获取股票列表
    stock_list = os.getenv('STOCK_LIST', '002361,600783').split(',')
    stock_list = [code.strip() for code in stock_list if code.strip()]
    
    print(f"正在分析 {len(stock_list)} 只股票: {', '.join(stock_list)}\n")
    
    for code in stock_list:
        print("=" * 100)
        print(f"股票代码: {code}")
        print("=" * 100)
        
        try:
            # 3. 获取历史数据
            print(f"\n[1/4] 获取历史数据...")
            df = provider.get_stock_data(code, days=120)
            if df is None or df.empty:
                print(f"  ❌ 无法获取 {code} 的数据")
                continue
            print(f"  ✅ 成功获取 {len(df)} 天数据")
            
            # 4. 执行趋势分析
            print(f"\n[2/4] 执行趋势分析（包含新指标）...")
            result = analyzer.analyze(df, code)
            print(f"  ✅ 分析完成")
            
            # 5. 显示新指标
            print(f"\n[3/4] 新指标详细数据")
            print("-" * 100)
            
            # 布林带
            if hasattr(result, 'boll_upper') and result.boll_upper > 0:
                print(f"\n📊 布林带(BOLL)指标:")
                print(f"  状态: {result.boll_status}")
                print(f"  ├─ 上轨: {result.boll_upper:.2f} 元  （压力位）")
                print(f"  ├─ 中轨: {result.boll_middle:.2f} 元  （支撑/压力）")
                print(f"  ├─ 下轨: {result.boll_lower:.2f} 元  （支撑位）")
                print(f"  ├─ 当前价位置: {result.boll_position:.1f}%  （50%为中性）")
                print(f"  ├─ 带宽: {result.boll_bandwidth:.2f}%  （<10%收窄，变盘在即）")
                print(f"  └─ 信号: {result.boll_signal}")
            else:
                print(f"\n❌ 布林带指标数据缺失")
            
            # KDJ
            if hasattr(result, 'kdj_k') and result.kdj_k > 0:
                print(f"\n📈 KDJ 指标:")
                print(f"  状态: {result.kdj_status}")
                print(f"  ├─ K值: {result.kdj_k:.1f}  （快线）")
                print(f"  ├─ D值: {result.kdj_d:.1f}  （慢线）")
                print(f"  ├─ J值: {result.kdj_j:.1f}  （J<0超卖，J>100超买）")
                buy_stars = '★' * result.kdj_buy_strength + '☆' * (5 - result.kdj_buy_strength)
                sell_stars = '★' * result.kdj_sell_strength + '☆' * (5 - result.kdj_sell_strength)
                print(f"  ├─ 买入强度: {buy_stars}  ({result.kdj_buy_strength}/5)")
                print(f"  ├─ 卖出强度: {sell_stars}  ({result.kdj_sell_strength}/5)")
                print(f"  └─ 信号: {result.kdj_signal}")
            else:
                print(f"\n❌ KDJ 指标数据缺失")
            
            # ATR
            if hasattr(result, 'atr') and result.atr > 0:
                print(f"\n📊 ATR 波动率:")
                print(f"  波动等级: {result.atr_level}")
                print(f"  ├─ ATR值: {result.atr:.2f} 元")
                print(f"  ├─ ATR占比: {result.atr_pct:.2f}%  （占当前股价）")
                print(f"  ├─ 止损位: {result.atr_stop_loss:.2f} 元  （2倍ATR，建议止损位）")
                print(f"  ├─ 止盈位: {result.atr_take_profit:.2f} 元  （3倍ATR，建议止盈位）")
                print(f"  └─ 信号: {result.atr_signal}")
            else:
                print(f"\n❌ ATR 指标数据缺失")
            
            # 6. 显示完整的文本报告
            print(f"\n[4/4] 完整技术分析报告")
            print("-" * 100)
            report = analyzer.format_analysis(result)
            print(report)
            
            print("\n" + "=" * 100)
            print("")
            
        except Exception as e:
            print(f"  ❌ 分析失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "=" * 100)
    print("✅ 所有股票分析完成！")
    print("=" * 100)
    print("\n说明:")
    print("  1. 新指标（BOLL/KDJ/ATR）已成功集成到系统")
    print("  2. 这些指标会自动传递给 AI 进行综合分析")
    print("  3. 如果 Gemini API 配额已满，等待恢复后可查看 AI 分析")
    print("")

if __name__ == '__main__':
    try:
        display_indicators()
    except Exception as e:
        print(f"\n❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
