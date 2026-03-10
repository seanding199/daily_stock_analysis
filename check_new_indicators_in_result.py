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
print(f"{'检查 AI 分析结果中的新指标':^96}")
print("=" * 100)

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.execute('''
    SELECT code, name, operation_advice, sentiment_score, raw_result, created_at
    FROM analysis_history 
    WHERE DATE(created_at) >= "2026-02-10" AND code = "002361"
    ORDER BY created_at DESC
    LIMIT 1
''')

row = cursor.fetchone()
if not row:
    print("\n未找到今日分析记录")
    conn.close()
    exit(0)

code, name, advice, score, raw_json, created_at = row
print(f"\n股票: {name} ({code})")
print(f"时间: {created_at}")
print(f"建议: {advice}  |  评分: {score}")
print("=" * 100)

try:
    raw_data = json.loads(raw_json) if raw_json else {}
    
    # 检查 technical_analysis 字段
    tech_analysis = raw_data.get('technical_analysis', '')
    
    print(f"\n【technical_analysis 字段内容】")
    print(f"长度: {len(tech_analysis)} 字符")
    print("-" * 100)
    print(tech_analysis)
    print("-" * 100)
    
    # 检查是否包含新指标关键词
    indicators = {
        'BOLL': ['BOLL', '布林带', '上轨', '下轨', '中轨', '带宽'],
        'KDJ': ['KDJ', 'K=', 'D=', 'J=', '金叉', '死叉', '买入强度', '卖出强度'],
        'ATR': ['ATR', '波动率', '止损位', '止盈位', '波动等级']
    }
    
    print(f"\n{'='*100}")
    print("【新指标检测结果】")
    print(f"{'='*100}")
    
    for indicator_name, keywords in indicators.items():
        found_keywords = [kw for kw in keywords if kw in tech_analysis]
        if found_keywords:
            print(f"\n✅ {indicator_name} 指标: 已找到")
            print(f"   匹配的关键词: {', '.join(found_keywords)}")
        else:
            print(f"\n❌ {indicator_name} 指标: 未找到")
    
    # 统计
    total_found = sum(1 for keywords in indicators.values() if any(kw in tech_analysis for kw in keywords))
    print(f"\n{'='*100}")
    print(f"总结: {total_found}/3 个新指标出现在分析中")
    print(f"{'='*100}")
    
except Exception as e:
    print(f"\n解析失败: {e}")
    import traceback
    traceback.print_exc()

conn.close()
