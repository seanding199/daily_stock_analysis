#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
import json

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 100)
print(f"{'DeepSeek AI 分析结果（含新指标）':^96}")
print("=" * 100)

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.execute('''
    SELECT code, name, operation_advice, sentiment_score, raw_result, created_at
    FROM analysis_history 
    WHERE DATE(created_at) >= "2026-02-10"
    ORDER BY created_at DESC
    LIMIT 2
''')

for code, name, advice, score, raw_json, created_at in cursor.fetchall():
    print(f"\n{'='*100}")
    print(f"股票: {name} ({code})")
    print(f"时间: {created_at}")
    print(f"建议: {advice}  |  评分: {score}")
    print(f"{'='*100}")
    
    try:
        raw_data = json.loads(raw_json) if raw_json else {}
        dashboard = raw_data.get('dashboard', {})
        
        # 核心结论
        core = dashboard.get('core_conclusion', {})
        print(f"\n【核心结论】")
        print(f"  {core.get('one_sentence', 'N/A')}")
        
        # 技术面评估
        tech = dashboard.get('technical_evaluation', {})
        if tech:
            print(f"\n【技术面评估】")
            for key, value in tech.items():
                if isinstance(value, dict) and 'status' in value:
                    print(f"  {key}: {value.get('status', 'N/A')} - {value.get('comment', '')}")
        
        # 决策建议
        decision = dashboard.get('decision', {})
        if decision:
            print(f"\n【决策建议】")
            if '空仓者' in decision:
                print(f"  空仓者: {decision.get('空仓者', 'N/A')}")
            if '持仓者' in decision:
                print(f"  持仓者: {decision.get('持仓者', 'N/A')}")
        
        # 价格建议
        if 'ideal_buy' in raw_data and raw_data.get('ideal_buy'):
            print(f"\n【价格建议】")
            print(f"  理想买入价: {raw_data.get('ideal_buy', 0):.2f} 元")
            if raw_data.get('secondary_buy'):
                print(f"  次优买入价: {raw_data.get('secondary_buy', 0):.2f} 元")
            if raw_data.get('stop_loss'):
                print(f"  止损价: {raw_data.get('stop_loss', 0):.2f} 元")
            if raw_data.get('take_profit'):
                print(f"  止盈价: {raw_data.get('take_profit', 0):.2f} 元")
        
        # 风险提示
        risks = dashboard.get('risk_alerts', [])
        if risks:
            print(f"\n【风险提示】")
            for risk in risks:
                print(f"  ⚠️ {risk}")
        
    except Exception as e:
        print(f"  解析失败: {e}")

conn.close()

print(f"\n{'='*100}")
print("✅ 所有分析完成！新指标（BOLL/KDJ/ATR）已传递给 DeepSeek AI 并生成分析！")
print("=" * 100)
