#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Prompt 生成，验证新指标是否包含在内
"""
import os
import sys
import pandas as pd

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.stock_analyzer import StockTrendAnalyzer

def test_prompt_generation():
    """测试 Prompt 生成"""
    print("=" * 80)
    print("测试 Prompt 生成 - 验证新指标是否包含")
    print("=" * 80)
    
    # 1. 创建分析器
    analyzer = StockTrendAnalyzer()
    
    # 2. 准备测试数据
    dates = pd.date_range('2026-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'open': 10.0 + (dates - dates[0]).days * 0.05,
        'high': 10.5 + (dates - dates[0]).days * 0.05,
        'low': 9.5 + (dates - dates[0]).days * 0.05,
        'close': 10.0 + (dates - dates[0]).days * 0.05,
        'volume': 1000000 + (dates - dates[0]).days * 10000,
    })
    
    # 3. 执行分析
    print("\n正在执行趋势分析...")
    result = analyzer.analyze(df, '000001')
    
    # 4. 检查结果中是否包含新指标
    print("\n" + "=" * 80)
    print("新指标数据检查")
    print("=" * 80)
    
    indicators_found = []
    indicators_missing = []
    
    # 检查 BOLL
    if hasattr(result, 'boll_upper') and result.boll_upper > 0:
        indicators_found.append('BOLL')
        print(f"\n✅ BOLL 指标:")
        print(f"   上轨: {result.boll_upper:.2f}")
        print(f"   中轨: {result.boll_middle:.2f}")
        print(f"   下轨: {result.boll_lower:.2f}")
        print(f"   状态: {result.boll_status}")
    else:
        indicators_missing.append('BOLL')
        print("\n❌ BOLL 指标未找到")
    
    # 检查 KDJ
    if hasattr(result, 'kdj_k') and result.kdj_k > 0:
        indicators_found.append('KDJ')
        print(f"\n✅ KDJ 指标:")
        print(f"   K: {result.kdj_k:.1f}")
        print(f"   D: {result.kdj_d:.1f}")
        print(f"   J: {result.kdj_j:.1f}")
        print(f"   状态: {result.kdj_status}")
    else:
        indicators_missing.append('KDJ')
        print("\n❌ KDJ 指标未找到")
    
    # 检查 ATR
    if hasattr(result, 'atr') and result.atr > 0:
        indicators_found.append('ATR')
        print(f"\n✅ ATR 指标:")
        print(f"   ATR: {result.atr:.2f}")
        print(f"   ATR%: {result.atr_pct:.2f}%")
        print(f"   等级: {result.atr_level}")
    else:
        indicators_missing.append('ATR')
        print("\n❌ ATR 指标未找到")
    
    # 5. 将结果转换为字典（模拟传递给 Prompt 生成器的数据）
    result_dict = result.to_dict()
    
    # 6. 构造测试用的 context
    context = {
        'code': '000001',
        'date': '2026-02-10',
        'stock_name': '测试股票',
        'today': {
            'close': 14.75,
            'open': 14.50,
            'high': 15.00,
            'low': 14.30,
            'pct_chg': 1.5,
            'volume': 1500000,
            'amount': 22000000,
            'ma5': 14.50,
            'ma10': 14.20,
            'ma20': 13.80,
        },
        'ma_status': '多头排列 🔼',
        'trend_analysis': result_dict,  # 包含所有新指标
    }
    
    # 7. 测试 Prompt 生成
    print("\n" + "=" * 80)
    print("测试 Prompt 生成")
    print("=" * 80)
    
    # 导入 Analyzer 来使用 _format_prompt 方法
    from src.analyzer import GeminiAnalyzer
    ai_analyzer = GeminiAnalyzer()
    
    prompt = ai_analyzer._format_prompt(context, '测试股票', news_context=None)
    
    # 8. 检查 Prompt 中是否包含新指标关键词
    print(f"\nPrompt 总长度: {len(prompt)} 字符\n")
    
    keywords = {
        'BOLL': ['布林带', 'BOLL', '上轨', '下轨', '中轨'],
        'KDJ': ['KDJ', 'K值', 'D值', 'J值'],
        'ATR': ['ATR', '波动率', '止损位', '止盈位']
    }
    
    print("检查 Prompt 中的关键词:")
    for indicator, words in keywords.items():
        found = any(word in prompt for word in words)
        if found:
            print(f"  ✅ {indicator} - 在 Prompt 中找到")
        else:
            print(f"  ❌ {indicator} - 未在 Prompt 中找到")
    
    # 9. 输出 Prompt 的相关部分
    print("\n" + "=" * 80)
    print("Prompt 片段（技术指标部分）")
    print("=" * 80)
    
    # 查找技术指标详解部分
    if '技术指标详解' in prompt:
        start_idx = prompt.find('技术指标详解')
        end_idx = prompt.find('系统分析理由', start_idx)
        if end_idx == -1:
            end_idx = start_idx + 2000
        print(prompt[start_idx:end_idx])
    else:
        print("⚠️ 未找到'技术指标详解'部分")
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    if indicators_found:
        print(f"✅ 成功找到的指标: {', '.join(indicators_found)}")
    if indicators_missing:
        print(f"❌ 缺失的指标: {', '.join(indicators_missing)}")
    
    # 检查 Prompt 包含情况
    all_in_prompt = all(
        any(word in prompt for word in words)
        for words in keywords.values()
    )
    
    if all_in_prompt:
        print("\n✅ 所有新指标数据都已包含在 Prompt 中！")
        print("   AI 现在可以看到并分析 BOLL/KDJ/ATR 数据了。")
    else:
        print("\n❌ 部分指标数据未包含在 Prompt 中")
        print("   需要进一步调试 Prompt 生成逻辑。")

if __name__ == '__main__':
    try:
        test_prompt_generation()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
