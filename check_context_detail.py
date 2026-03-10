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

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.execute('SELECT code, name, context_snapshot FROM analysis_history WHERE DATE(created_at) >= "2026-02-10" ORDER BY created_at DESC LIMIT 1')
row = cursor.fetchone()

if row:
    code, name, context_json = row
    print(f"股票: {name} ({code})")
    print("=" * 80)
    
    try:
        context = json.loads(context_json) if context_json else {}
        print(f"\ncontext 包含的键: {list(context.keys())}")
        
        # 尝试从 enhanced_context 中获取
        if 'enhanced_context' in context:
            enhanced_context = context['enhanced_context']
            if isinstance(enhanced_context, dict):
                print(f"\nenhanced_context 包含的键: {list(enhanced_context.keys())}")
                if 'trend_analysis' in enhanced_context:
                    trend_analysis = enhanced_context['trend_analysis']
                else:
                    print("\n❌ enhanced_context 中没有 trend_analysis")
                    trend_analysis = None
            else:
                print(f"\n⚠️ enhanced_context 类型: {type(enhanced_context)}")
                trend_analysis = None
        elif 'trend_analysis' in context:
            trend_analysis = context['trend_analysis']
        else:
            trend_analysis = None
        
        if trend_analysis:
            print(f"\ntrend_analysis 类型: {type(trend_analysis)}")
            
            if isinstance(trend_analysis, dict):
                print(f"\ntrend_analysis 包含的键: {list(trend_analysis.keys())}")
                
                # 检查新指标
                has_boll = any(k.startswith('boll_') for k in trend_analysis.keys())
                has_kdj = any(k.startswith('kdj_') for k in trend_analysis.keys())
                has_atr = any(k.startswith('atr_') for k in trend_analysis.keys())
                
                print(f"\n新指标检测:")
                print(f"  BOLL: {'✅' if has_boll else '❌'}")
                print(f"  KDJ: {'✅' if has_kdj else '❌'}")
                print(f"  ATR: {'✅' if has_atr else '❌'}")
                
                if has_boll:
                    print(f"\nBOLL 数据:")
                    for k, v in trend_analysis.items():
                        if k.startswith('boll_'):
                            print(f"  {k}: {v}")
                
                if has_kdj:
                    print(f"\nKDJ 数据:")
                    for k, v in trend_analysis.items():
                        if k.startswith('kdj_'):
                            print(f"  {k}: {v}")
                
                if has_atr:
                    print(f"\nATR 数据:")
                    for k, v in trend_analysis.items():
                        if k.startswith('atr_'):
                            print(f"  {k}: {v}")
            else:
                print("\n⚠️ trend_analysis 不是字典类型")
        else:
            print("\n❌ context 中没有 trend_analysis 键")
    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("未找到记录")

conn.close()
