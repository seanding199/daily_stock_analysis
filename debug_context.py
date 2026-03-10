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
print(f"{'调试 context_snapshot 数据':^96}")
print("=" * 100)

conn = sqlite3.connect('data/stock_analysis.db')

# 查询两只股票的 context_snapshot
cursor = conn.execute('''
    SELECT code, name, created_at, context_snapshot
    FROM analysis_history 
    WHERE DATE(created_at) >= "2026-02-10"
    ORDER BY code, created_at DESC
''')

for code, name, created_at, context_json in cursor.fetchall():
    print(f"\n{'='*100}")
    print(f"股票: {name} ({code})")
    print(f"时间: {created_at}")
    print(f"{'='*100}")
    
    try:
        context = json.loads(context_json) if context_json else {}
        
        # 检查 context 结构
        print(f"\ncontext 顶层键: {list(context.keys())}")
        
        # 检查 enhanced_context
        if 'enhanced_context' in context:
            enhanced = context['enhanced_context']
            print(f"\nenhanced_context 键: {list(enhanced.keys())}")
            
            # 检查是否有 trend_analysis
            if 'trend_analysis' in enhanced:
                trend = enhanced['trend_analysis']
                if isinstance(trend, dict):
                    print(f"\n✅ trend_analysis 类型: dict")
                    print(f"   trend_analysis 键: {list(trend.keys())[:20]}...")  # 只显示前20个
                    
                    # 检查新指标
                    has_boll = any(k.startswith('boll_') for k in trend.keys())
                    has_kdj = any(k.startswith('kdj_') for k in trend.keys())
                    has_atr = any(k.startswith('atr_') for k in trend.keys())
                    
                    print(f"\n新指标检测:")
                    print(f"  BOLL: {'✅ 存在' if has_boll else '❌ 不存在'}")
                    print(f"  KDJ: {'✅ 存在' if has_kdj else '❌ 不存在'}")
                    print(f"  ATR: {'✅ 存在' if has_atr else '❌ 不存在'}")
                    
                    if has_boll:
                        print(f"\n  BOLL 数据示例:")
                        for k, v in trend.items():
                            if k.startswith('boll_'):
                                print(f"    {k}: {v}")
                    
                    if has_kdj:
                        print(f"\n  KDJ 数据示例:")
                        for k, v in trend.items():
                            if k.startswith('kdj_'):
                                print(f"    {k}: {v}")
                    
                    if has_atr:
                        print(f"\n  ATR 数据示例:")
                        for k, v in trend.items():
                            if k.startswith('atr_'):
                                print(f"    {k}: {v}")
                else:
                    print(f"\n⚠️ trend_analysis 类型: {type(trend)}")
            else:
                print(f"\n❌ enhanced_context 中没有 trend_analysis")
        else:
            print(f"\n❌ context 中没有 enhanced_context")
    
    except Exception as e:
        print(f"\n解析失败: {e}")
        import traceback
        traceback.print_exc()

conn.close()

print(f"\n{'='*100}")
print("调试完成")
print("=" * 100)
