#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看最新的股票分析结果（包含新指标）
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

def view_latest_analysis():
    """查看最新分析结果"""
    print("=" * 100)
    print(f"{'最新股票分析结果（含新指标）':^96}")
    print("=" * 100)
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 连接数据库
    db_path = 'data/stock_analysis.db'
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 2. 获取最新的分析记录（今天的）
    today = datetime.now().strftime('%Y-%m-%d')
    query = """
        SELECT code, name, created_at, context_snapshot
        FROM analysis_history 
        WHERE DATE(created_at) = ?
        ORDER BY code, created_at DESC
    """
    
    cursor.execute(query, (today,))
    records = cursor.fetchall()
    
    if not records:
        print(f"⚠️ 未找到今日（{today}）的分析记录")
        print("提示: 运行 'python main.py --webui' 或 'python main.py --schedule' 来生成分析")
        conn.close()
        return
    
    print(f"找到 {len(records)} 条今日分析记录\n")
    
    # 3. 遍历每条记录
    for code, name, created_at, context_json in records:
        print("=" * 100)
        print(f"股票: {name} ({code})")
        print(f"时间: {created_at}")
        print("=" * 100)
        
        try:
            context_data = json.loads(context_json) if context_json else {}
            trend_data = context_data.get('trend_analysis', {})
            
            # 检查是否包含新指标
            has_new_indicators = any(key.startswith(('boll_', 'kdj_', 'atr_')) for key in trend_data.keys())
            
            if not has_new_indicators:
                print("\n⚠️ 该记录不包含新指标数据（可能是旧版本分析）")
                print("   建议: 删除今日数据并重新运行分析以生成包含新指标的结果\n")
                continue
            
            # 显示新指标
            print("\n📊 新增技术指标")
            print("-" * 100)
            
            # 布林带
            if 'boll_upper' in trend_data and trend_data.get('boll_upper', 0) > 0:
                print(f"\n✅ 布林带(BOLL)指标:")
                print(f"  状态: {trend_data.get('boll_status', 'N/A')}")
                print(f"  ├─ 上轨: {trend_data.get('boll_upper', 0):.2f} 元  （压力位）")
                print(f"  ├─ 中轨: {trend_data.get('boll_middle', 0):.2f} 元  （支撑/压力）")
                print(f"  ├─ 下轨: {trend_data.get('boll_lower', 0):.2f} 元  （支撑位）")
                print(f"  ├─ 当前价位置: {trend_data.get('boll_position', 0):.1f}%  （50%为中性）")
                print(f"  ├─ 带宽: {trend_data.get('boll_bandwidth', 0):.2f}%  （<10%收窄，变盘在即）")
                print(f"  └─ 信号: {trend_data.get('boll_signal', 'N/A')}")
            else:
                print(f"\n❌ 布林带指标数据缺失")
            
            # KDJ
            if 'kdj_k' in trend_data and trend_data.get('kdj_k', 0) > 0:
                print(f"\n✅ KDJ 指标:")
                print(f"  状态: {trend_data.get('kdj_status', 'N/A')}")
                print(f"  ├─ K值: {trend_data.get('kdj_k', 0):.1f}  （快线）")
                print(f"  ├─ D值: {trend_data.get('kdj_d', 0):.1f}  （慢线）")
                print(f"  ├─ J值: {trend_data.get('kdj_j', 0):.1f}  （J<0超卖，J>100超买）")
                buy_strength = trend_data.get('kdj_buy_strength', 0)
                sell_strength = trend_data.get('kdj_sell_strength', 0)
                buy_stars = '★' * buy_strength + '☆' * (5 - buy_strength)
                sell_stars = '★' * sell_strength + '☆' * (5 - sell_strength)
                print(f"  ├─ 买入强度: {buy_stars}  ({buy_strength}/5)")
                print(f"  ├─ 卖出强度: {sell_stars}  ({sell_strength}/5)")
                print(f"  └─ 信号: {trend_data.get('kdj_signal', 'N/A')}")
            else:
                print(f"\n❌ KDJ 指标数据缺失")
            
            # ATR
            if 'atr' in trend_data and trend_data.get('atr', 0) > 0:
                print(f"\n✅ ATR 波动率:")
                print(f"  波动等级: {trend_data.get('atr_level', 'N/A')}")
                print(f"  ├─ ATR值: {trend_data.get('atr', 0):.2f} 元")
                print(f"  ├─ ATR占比: {trend_data.get('atr_pct', 0):.2f}%  （占当前股价）")
                print(f"  ├─ 止损位: {trend_data.get('atr_stop_loss', 0):.2f} 元  （2倍ATR，建议止损位）")
                print(f"  ├─ 止盈位: {trend_data.get('atr_take_profit', 0):.2f} 元  （3倍ATR，建议止盈位）")
                print(f"  └─ 信号: {trend_data.get('atr_signal', 'N/A')}")
            else:
                print(f"\n❌ ATR 指标数据缺失")
            
            print("\n")
            
        except Exception as e:
            print(f"  ❌ 解析失败: {e}")
            continue
    
    conn.close()
    
    print("=" * 100)
    print("✅ 查询完成！")
    print("=" * 100)
    print("\n说明:")
    print("  1. 如果看到'旧版本分析'提示，说明数据是在新指标实施前生成的")
    print("  2. 解决方法: 重启 Web 服务或定时任务，会自动重新分析并包含新指标")
    print("  3. 新指标数据会自动传递给 AI 进行综合分析")
    print("")

if __name__ == '__main__':
    try:
        view_latest_analysis()
    except Exception as e:
        print(f"\n❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
