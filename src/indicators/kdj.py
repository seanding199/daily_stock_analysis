# -*- coding: utf-8 -*-
"""
KDJ 指标（随机指标）

用途：
1. 短线买卖点判断
2. 超买超卖识别
3. 金叉死叉信号
4. 比 RSI 更敏感

交易信号：
- K线上穿D线 → 金叉（买入）
- K线下穿D线 → 死叉（卖出）
- J值 > 100 → 超买
- J值 < 0 → 超卖
- K、D在20以下金叉 → 强烈买入
- K、D在80以上死叉 → 强烈卖出
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from .base import BaseIndicator, BaseIndicatorResult


class KDJStatus(Enum):
    """KDJ状态枚举"""
    GOLDEN_CROSS_LOW = "低位金叉"      # K线上穿D线，且在20以下（强烈买入）
    GOLDEN_CROSS = "金叉"             # K线上穿D线（买入）
    BULLISH = "多头"                  # K>D，上升趋势
    DEATH_CROSS_HIGH = "高位死叉"     # K线下穿D线，且在80以上（强烈卖出）
    DEATH_CROSS = "死叉"              # K线下穿D线（卖出）
    BEARISH = "空头"                  # K<D，下降趋势
    OVERSOLD = "超卖"                 # J<0，极度超卖
    OVERBOUGHT = "超买"               # J>100，极度超买


@dataclass
class KDJResult(BaseIndicatorResult):
    """KDJ计算结果"""
    # KDJ数值
    k: float = 0.0               # K值（快线）
    d: float = 0.0               # D值（慢线）
    j: float = 0.0               # J值（超前指标）
    
    # 状态判断
    status: KDJStatus = KDJStatus.BULLISH
    signal: str = ""             # 交易信号描述
    buy_strength: int = 0        # 买入强度（0-5）
    sell_strength: int = 0       # 卖出强度（0-5）
    
    # 信号细节
    is_golden_cross: bool = False    # 是否金叉
    is_death_cross: bool = False     # 是否死叉
    is_oversold: bool = False        # 是否超卖
    is_overbought: bool = False      # 是否超买


class KDJIndicator(BaseIndicator):
    """
    KDJ 指标计算器
    
    参数：
    - n: RSV周期，默认9日
    - m1: K值平滑周期，默认3日
    - m2: D值平滑周期，默认3日
    - oversold: 超卖阈值，默认20
    - overbought: 超买阈值，默认80
    """
    
    def __init__(
        self,
        n: int = 9,
        m1: int = 3,
        m2: int = 3,
        oversold: float = 20.0,
        overbought: float = 80.0
    ):
        self.n = n
        self.m1 = m1
        self.m2 = m2
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate(self, df: pd.DataFrame) -> Optional[KDJResult]:
        """
        计算 KDJ 指标
        
        Args:
            df: 包含 high, low, close 列的DataFrame
            
        Returns:
            KDJResult: KDJ 分析结果
        """
        if not self._validate_kdj_data(df, self.n):
            return None
        
        # 1. 计算 RSV（未成熟随机值）
        df = df.copy()
        low_list = df['low'].rolling(window=self.n, min_periods=1).min()
        high_list = df['high'].rolling(window=self.n, min_periods=1).max()
        
        # RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) * 100
        df['RSV'] = (df['close'] - low_list) / (high_list - low_list) * 100
        df['RSV'].fillna(50, inplace=True)  # 初始值设为50
        
        # 2. 计算 K、D、J
        # K = RSV的M1日移动平均
        # D = K的M2日移动平均
        # J = 3K - 2D
        df['K'] = df['RSV'].ewm(span=self.m1, adjust=False).mean()
        df['D'] = df['K'].ewm(span=self.m2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        
        # 3. 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        
        k = float(latest['K'])
        d = float(latest['D'])
        j = float(latest['J'])
        
        prev_k = float(prev['K'])
        prev_d = float(prev['D'])
        
        # 4. 判断状态
        status, signal, buy_strength, sell_strength = self._analyze_status(
            k, d, j, prev_k, prev_d
        )
        
        # 5. 判断信号
        is_golden_cross = prev_k <= prev_d and k > d
        is_death_cross = prev_k >= prev_d and k < d
        is_oversold = j < 0
        is_overbought = j > 100
        
        # 6. 构建结果
        result = KDJResult(
            k=k,
            d=d,
            j=j,
            status=status,
            signal=signal,
            buy_strength=buy_strength,
            sell_strength=sell_strength,
            is_golden_cross=is_golden_cross,
            is_death_cross=is_death_cross,
            is_oversold=is_oversold,
            is_overbought=is_overbought
        )
        
        return result
    
    def _validate_kdj_data(self, df: pd.DataFrame, min_periods: int) -> bool:
        """验证KDJ数据有效性"""
        if df is None or df.empty:
            return False
        
        if len(df) < min_periods:
            return False
        
        required_columns = ['high', 'low', 'close']
        for col in required_columns:
            if col not in df.columns:
                return False
        
        return True
    
    def _analyze_status(
        self,
        k: float,
        d: float,
        j: float,
        prev_k: float,
        prev_d: float
    ) -> Tuple[KDJStatus, str, int, int]:
        """
        分析 KDJ 状态
        
        Returns:
            (状态, 信号描述, 买入强度, 卖出强度)
        """
        buy_strength = 0
        sell_strength = 0
        
        # 1. 判断金叉/死叉
        is_golden_cross = prev_k <= prev_d and k > d
        is_death_cross = prev_k >= prev_d and k < d
        
        # 2. 低位金叉（强烈买入信号）
        if is_golden_cross and k < self.oversold:
            signal = f"低位金叉（K={k:.1f}, D={d:.1f}），强烈买入信号"
            buy_strength = 5
            return KDJStatus.GOLDEN_CROSS_LOW, signal, buy_strength, sell_strength
        
        # 3. 金叉（买入信号）
        if is_golden_cross:
            signal = f"金叉（K={k:.1f}上穿D={d:.1f}），买入信号"
            buy_strength = 3
            return KDJStatus.GOLDEN_CROSS, signal, buy_strength, sell_strength
        
        # 4. 高位死叉（强烈卖出信号）
        if is_death_cross and k > self.overbought:
            signal = f"高位死叉（K={k:.1f}, D={d:.1f}），强烈卖出信号"
            sell_strength = 5
            return KDJStatus.DEATH_CROSS_HIGH, signal, buy_strength, sell_strength
        
        # 5. 死叉（卖出信号）
        if is_death_cross:
            signal = f"死叉（K={k:.1f}下穿D={d:.1f}），卖出信号"
            sell_strength = 3
            return KDJStatus.DEATH_CROSS, signal, buy_strength, sell_strength
        
        # 6. 极度超卖（J<0）
        if j < 0:
            signal = f"极度超卖（J={j:.1f}），反弹在即"
            buy_strength = 4
            return KDJStatus.OVERSOLD, signal, buy_strength, sell_strength
        
        # 7. 极度超买（J>100）
        if j > 100:
            signal = f"极度超买（J={j:.1f}），回调风险高"
            sell_strength = 4
            return KDJStatus.OVERBOUGHT, signal, buy_strength, sell_strength
        
        # 8. 多头（K>D）
        if k > d:
            if k < self.oversold:
                signal = f"超卖区多头（K={k:.1f}, D={d:.1f}），可考虑介入"
                buy_strength = 2
            elif k > self.overbought:
                signal = f"超买区多头（K={k:.1f}, D={d:.1f}），注意回调"
                sell_strength = 2
            else:
                signal = f"多头排列（K={k:.1f} > D={d:.1f}），持股待涨"
                buy_strength = 1
            return KDJStatus.BULLISH, signal, buy_strength, sell_strength
        
        # 9. 空头（K<D）
        if k < self.oversold:
            signal = f"深度超卖（K={k:.1f}, D={d:.1f}），等待反弹"
            buy_strength = 1
        elif k > self.overbought:
            signal = f"高位空头（K={k:.1f}, D={d:.1f}），继续看空"
            sell_strength = 2
        else:
            signal = f"空头排列（K={k:.1f} < D={d:.1f}），观望为主"
            sell_strength = 1
        
        return KDJStatus.BEARISH, signal, buy_strength, sell_strength
