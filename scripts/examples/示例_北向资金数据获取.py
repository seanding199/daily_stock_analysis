# -*- coding: utf-8 -*-
"""
===================================
北向资金（外资）数据获取示例
===================================

用途：
1. 追踪外资流向
2. 判断市场热度
3. 挖掘外资重仓股
4. 预判市场走势

数据维度：
- 沪股通/深股通每日净流入
- 连续流入/流出天数
- 外资重仓股 TOP10
- 外资持股市值变化
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class NorthFlowTrend(Enum):
    """北向资金趋势枚举"""
    STRONG_INFLOW = "强势流入"      # 连续3日以上大幅流入
    INFLOW = "持续流入"            # 连续2日流入
    WEAK_INFLOW = "微弱流入"       # 单日小额流入
    NEUTRAL = "震荡"               # 流入流出交替
    WEAK_OUTFLOW = "微弱流出"      # 单日小额流出
    OUTFLOW = "持续流出"           # 连续2日流出
    STRONG_OUTFLOW = "强势流出"    # 连续3日以上大幅流出


@dataclass
class NorthFlowData:
    """北向资金数据结构"""
    date: str                       # 日期
    
    # 流入数据
    shanghai_inflow: float = 0.0    # 沪股通净流入（亿元）
    shenzhen_inflow: float = 0.0    # 深股通净流入（亿元）
    total_inflow: float = 0.0       # 合计净流入（亿元）
    
    # 趋势分析
    trend: NorthFlowTrend = NorthFlowTrend.NEUTRAL
    continuous_days: int = 0        # 连续流入/流出天数
    recent_7d_total: float = 0.0    # 近7日累计流入
    recent_30d_total: float = 0.0   # 近30日累计流入
    
    # 重仓股
    top_holdings: List[Dict] = None  # 外资重仓股列表
    
    # 信号
    signal: str = ""                # 信号描述
    market_impact: str = ""         # 市场影响判断
    
    def __post_init__(self):
        if self.top_holdings is None:
            self.top_holdings = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date,
            'shanghai_inflow': self.shanghai_inflow,
            'shenzhen_inflow': self.shenzhen_inflow,
            'total_inflow': self.total_inflow,
            'trend': self.trend.value,
            'continuous_days': self.continuous_days,
            'recent_7d_total': self.recent_7d_total,
            'recent_30d_total': self.recent_30d_total,
            'top_holdings': self.top_holdings,
            'signal': self.signal,
            'market_impact': self.market_impact,
        }


class NorthFlowAnalyzer:
    """
    北向资金分析器
    
    功能：
    1. 获取每日北向资金流入数据
    2. 分析连续流入/流出天数
    3. 统计历史累计流入
    4. 获取外资重仓股TOP10
    5. 生成交易信号
    """
    
    # 阈值配置
    LARGE_INFLOW = 50.0      # 大额流入阈值（亿元）
    LARGE_OUTFLOW = -50.0    # 大额流出阈值（亿元）
    
    def __init__(self):
        pass
    
    def get_daily_flow(self, days: int = 30) -> pd.DataFrame:
        """
        获取北向资金每日流入数据
        
        Args:
            days: 获取天数，默认30天
            
        Returns:
            DataFrame: 包含日期、沪股通、深股通、合计等列
        """
        try:
            # 使用 AkShare 获取北向资金流入数据
            # 接口：stock_em_hsgt_north_net_flow_in
            df = ak.stock_em_hsgt_north_net_flow_in(symbol="北向资金")
            
            if df is None or df.empty:
                print("⚠️ 未获取到北向资金数据")
                return pd.DataFrame()
            
            # 数据清洗和转换
            df = df.tail(days).copy()
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期', ascending=False)
            
            # 单位转换：元 → 亿元
            df['沪股通'] = df['沪股通'].astype(float) / 100000000
            df['深股通'] = df['深股通'].astype(float) / 100000000
            df['北向资金'] = df['北向资金'].astype(float) / 100000000
            
            return df
            
        except Exception as e:
            print(f"❌ 获取北向资金数据失败: {e}")
            return pd.DataFrame()
    
    def analyze_flow(self, days: int = 30) -> Optional[NorthFlowData]:
        """
        分析北向资金流向
        
        Args:
            days: 分析天数
            
        Returns:
            NorthFlowData: 分析结果
        """
        df = self.get_daily_flow(days)
        
        if df.empty:
            return None
        
        # 获取最新数据
        latest = df.iloc[0]
        date = latest['日期'].strftime('%Y-%m-%d')
        shanghai = latest['沪股通']
        shenzhen = latest['深股通']
        total = latest['北向资金']
        
        # 计算连续天数
        continuous_days = self._calc_continuous_days(df)
        
        # 计算近期累计
        recent_7d = df.head(7)['北向资金'].sum()
        recent_30d = df.head(30)['北向资金'].sum()
        
        # 判断趋势
        trend = self._analyze_trend(df, continuous_days)
        
        # 生成信号
        signal, impact = self._generate_signal(
            total, continuous_days, recent_7d, recent_30d, trend
        )
        
        # 构建结果
        result = NorthFlowData(
            date=date,
            shanghai_inflow=shanghai,
            shenzhen_inflow=shenzhen,
            total_inflow=total,
            trend=trend,
            continuous_days=continuous_days,
            recent_7d_total=recent_7d,
            recent_30d_total=recent_30d,
            signal=signal,
            market_impact=impact
        )
        
        return result
    
    def get_top_holdings(self, top_n: int = 10) -> List[Dict]:
        """
        获取外资重仓股 TOP N
        
        Args:
            top_n: 返回前N只股票
            
        Returns:
            List[Dict]: 重仓股列表
        """
        try:
            # 使用 AkShare 获取沪深港通持股数据
            # 接口：stock_em_hsgt_hold_stock
            df = ak.stock_em_hsgt_hold_stock(market="北向", indicator="持股数量")
            
            if df is None or df.empty:
                return []
            
            # 数据处理
            df = df.head(top_n)
            
            holdings = []
            for _, row in df.iterrows():
                holdings.append({
                    'code': row['代码'],
                    'name': row['名称'],
                    'hold_shares': row['持股数量'],  # 股
                    'hold_ratio': row['持股占比'],   # %
                    'hold_value': row['持股市值'],   # 元
                })
            
            return holdings
            
        except Exception as e:
            print(f"❌ 获取外资重仓股失败: {e}")
            return []
    
    def _calc_continuous_days(self, df: pd.DataFrame) -> int:
        """计算连续流入/流出天数（正数=流入，负数=流出）"""
        if df.empty:
            return 0
        
        count = 0
        sign = 1 if df.iloc[0]['北向资金'] > 0 else -1
        
        for i, row in df.iterrows():
            flow = row['北向资金']
            if (sign > 0 and flow > 0) or (sign < 0 and flow < 0):
                count += 1
            else:
                break
        
        return count * sign
    
    def _analyze_trend(self, df: pd.DataFrame, continuous_days: int) -> NorthFlowTrend:
        """分析资金流向趋势"""
        if df.empty:
            return NorthFlowTrend.NEUTRAL
        
        latest_flow = df.iloc[0]['北向资金']
        
        # 强势流入：连续3日以上 + 大额流入
        if continuous_days >= 3 and latest_flow >= self.LARGE_INFLOW:
            return NorthFlowTrend.STRONG_INFLOW
        
        # 持续流入：连续2日流入
        if continuous_days >= 2 and latest_flow > 0:
            return NorthFlowTrend.INFLOW
        
        # 微弱流入：单日小额流入
        if continuous_days >= 1 and 0 < latest_flow < self.LARGE_INFLOW:
            return NorthFlowTrend.WEAK_INFLOW
        
        # 强势流出
        if continuous_days <= -3 and latest_flow <= self.LARGE_OUTFLOW:
            return NorthFlowTrend.STRONG_OUTFLOW
        
        # 持续流出
        if continuous_days <= -2 and latest_flow < 0:
            return NorthFlowTrend.OUTFLOW
        
        # 微弱流出
        if continuous_days <= -1 and self.LARGE_OUTFLOW < latest_flow < 0:
            return NorthFlowTrend.WEAK_OUTFLOW
        
        return NorthFlowTrend.NEUTRAL
    
    def _generate_signal(
        self, 
        today_flow: float, 
        continuous_days: int,
        recent_7d: float,
        recent_30d: float,
        trend: NorthFlowTrend
    ) -> tuple:
        """
        生成交易信号
        
        Returns:
            (信号描述, 市场影响)
        """
        # 生成信号描述
        if continuous_days > 0:
            signal = f"连续 {continuous_days} 日净流入，今日流入 {today_flow:.2f} 亿元"
        elif continuous_days < 0:
            signal = f"连续 {abs(continuous_days)} 日净流出，今日流出 {abs(today_flow):.2f} 亿元"
        else:
            signal = f"今日净流入 {today_flow:.2f} 亿元"
        
        # 判断市场影响
        if trend == NorthFlowTrend.STRONG_INFLOW:
            impact = "强势看多，外资持续加仓，市场情绪乐观"
        elif trend == NorthFlowTrend.INFLOW:
            impact = "偏多，外资持续流入，利好市场"
        elif trend == NorthFlowTrend.WEAK_INFLOW:
            impact = "中性偏多，观望为主"
        elif trend == NorthFlowTrend.STRONG_OUTFLOW:
            impact = "强势看空，外资持续撤离，谨慎操作"
        elif trend == NorthFlowTrend.OUTFLOW:
            impact = "偏空，外资持续流出，不利市场"
        elif trend == NorthFlowTrend.WEAK_OUTFLOW:
            impact = "中性偏空，观望为主"
        else:
            impact = "中性，短期震荡"
        
        # 叠加历史数据判断
        if recent_7d > 100:
            impact += f"（近7日累计流入 {recent_7d:.0f} 亿，资金面良好）"
        elif recent_7d < -100:
            impact += f"（近7日累计流出 {abs(recent_7d):.0f} 亿，资金面承压）"
        
        return signal, impact


# ========== 使用示例 ==========
def example_usage():
    """北向资金分析使用示例"""
    
    print("=" * 60)
    print("北向资金分析示例")
    print("=" * 60)
    
    # 1. 创建分析器
    analyzer = NorthFlowAnalyzer()
    
    # 2. 获取并分析资金流向
    print("\n📊 正在获取北向资金数据...")
    result = analyzer.analyze_flow(days=30)
    
    if result:
        print("\n" + "=" * 60)
        print("北向资金分析结果")
        print("=" * 60)
        print(f"日期: {result.date}")
        print(f"\n💰 今日流入数据:")
        print(f"  沪股通: {result.shanghai_inflow:.2f} 亿元")
        print(f"  深股通: {result.shenzhen_inflow:.2f} 亿元")
        print(f"  合计: {result.total_inflow:.2f} 亿元")
        print(f"\n📈 趋势分析:")
        print(f"  趋势: {result.trend.value}")
        print(f"  连续天数: {result.continuous_days} 天")
        print(f"  近7日累计: {result.recent_7d_total:.2f} 亿元")
        print(f"  近30日累计: {result.recent_30d_total:.2f} 亿元")
        print(f"\n🎯 信号:")
        print(f"  {result.signal}")
        print(f"\n💡 市场影响:")
        print(f"  {result.market_impact}")
    
    # 3. 获取外资重仓股
    print("\n📋 正在获取外资重仓股 TOP10...")
    holdings = analyzer.get_top_holdings(top_n=10)
    
    if holdings:
        print("\n" + "=" * 60)
        print("外资重仓股 TOP10")
        print("=" * 60)
        for i, stock in enumerate(holdings, 1):
            print(f"{i}. {stock['name']}({stock['code']}) "
                  f"- 持股占比: {stock['hold_ratio']:.2f}%")


if __name__ == '__main__':
    example_usage()
