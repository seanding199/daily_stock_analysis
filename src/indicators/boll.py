# -*- coding: utf-8 -*-
"""
布林带（BOLL）指标

用途：
1. 判断价格波动区间
2. 识别超买超卖
3. 捕捉突破信号
4. 判断趋势强弱

交易信号：
- 价格触及下轨 → 超卖，可能反弹
- 价格触及上轨 → 超买，可能回调
- 布林带收窄 → 变盘在即
- 布林带张口 → 趋势延续
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .base import BaseIndicator, BaseIndicatorResult


class BOLLStatus(Enum):
    """布林带状态枚举"""
    UPPER_TOUCH = "触及上轨"           # 价格接近上轨（超买）
    MIDDLE_NEAR = "接近中轨"           # 价格在中轨附近
    LOWER_TOUCH = "触及下轨"           # 价格接近下轨（超卖）
    BREAK_UPPER = "突破上轨"           # 价格突破上轨（强势）
    BREAK_LOWER = "跌破下轨"           # 价格跌破下轨（弱势）
    SQUEEZE = "收窄整理"               # 布林带收窄（变盘前兆）
    EXPANSION = "张口扩张"             # 布林带扩张（趋势延续）


@dataclass
class BOLLResult(BaseIndicatorResult):
    """布林带计算结果"""
    # 布林带数值
    upper: float = 0.0           # 上轨
    middle: float = 0.0          # 中轨（MA20）
    lower: float = 0.0           # 下轨
    current_price: float = 0.0   # 当前价格
    
    # 位置分析
    position_pct: float = 0.0    # 价格在布林带中的位置（0-100%）
    bandwidth: float = 0.0        # 带宽：(上轨-下轨)/中轨 * 100
    distance_to_upper: float = 0.0   # 距离上轨距离（%）
    distance_to_lower: float = 0.0   # 距离下轨距离（%）
    
    # 状态判断
    status: BOLLStatus = BOLLStatus.MIDDLE_NEAR
    signal: str = ""             # 交易信号描述
    risk_level: str = "中等"      # 风险等级：高/中/低


class BOLLIndicator(BaseIndicator):
    """
    布林带指标计算器
    
    参数：
    - period: 周期，默认20日
    - std_dev: 标准差倍数，默认2倍
    - squeeze_threshold: 收窄阈值，默认10%（带宽低于此值为收窄）
    - touch_threshold: 触及阈值，默认3%（距离轨道小于此值为触及）
    """
    
    def __init__(
        self, 
        period: int = 20, 
        std_dev: float = 2.0,
        squeeze_threshold: float = 10.0,
        touch_threshold: float = 3.0
    ):
        self.period = period
        self.std_dev = std_dev
        self.squeeze_threshold = squeeze_threshold
        self.touch_threshold = touch_threshold
    
    def calculate(self, df: pd.DataFrame) -> Optional[BOLLResult]:
        """
        计算布林带指标
        
        Args:
            df: 包含 close 列的DataFrame
            
        Returns:
            BOLLResult: 布林带分析结果
        """
        if not self.validate_data(df, self.period):
            return None
        
        # 1. 计算布林带
        df = df.copy()
        df['MA20'] = df['close'].rolling(window=self.period).mean()
        df['STD'] = df['close'].rolling(window=self.period).std()
        df['BOLL_UPPER'] = df['MA20'] + (self.std_dev * df['STD'])
        df['BOLL_LOWER'] = df['MA20'] - (self.std_dev * df['STD'])
        
        # 2. 获取最新数据
        latest = df.iloc[-1]
        current_price = float(latest['close'])
        middle = float(latest['MA20'])
        upper = float(latest['BOLL_UPPER'])
        lower = float(latest['BOLL_LOWER'])
        
        # 3. 计算位置和带宽
        position_pct = self._calc_position(current_price, upper, middle, lower)
        bandwidth = self._calc_bandwidth(upper, middle, lower)
        distance_to_upper = ((upper - current_price) / current_price) * 100
        distance_to_lower = ((current_price - lower) / current_price) * 100
        
        # 4. 判断状态
        status, signal, risk_level = self._analyze_status(
            current_price, upper, middle, lower, 
            bandwidth, distance_to_upper, distance_to_lower, df
        )
        
        # 5. 构建结果
        result = BOLLResult(
            upper=upper,
            middle=middle,
            lower=lower,
            current_price=current_price,
            position_pct=position_pct,
            bandwidth=bandwidth,
            distance_to_upper=distance_to_upper,
            distance_to_lower=distance_to_lower,
            status=status,
            signal=signal,
            risk_level=risk_level
        )
        
        return result
    
    def _calc_position(
        self, 
        price: float, 
        upper: float, 
        middle: float, 
        lower: float
    ) -> float:
        """计算价格在布林带中的位置（0-100%）"""
        if upper == lower:
            return 50.0
        return ((price - lower) / (upper - lower)) * 100
    
    def _calc_bandwidth(self, upper: float, middle: float, lower: float) -> float:
        """计算布林带宽度"""
        if middle == 0:
            return 0.0
        return ((upper - lower) / middle) * 100
    
    def _analyze_status(
        self, 
        price: float, 
        upper: float, 
        middle: float, 
        lower: float,
        bandwidth: float,
        dist_upper: float,
        dist_lower: float,
        df: pd.DataFrame
    ) -> Tuple[BOLLStatus, str, str]:
        """
        分析布林带状态
        
        Returns:
            (状态, 信号描述, 风险等级)
        """
        # 1. 判断是否收窄整理
        if bandwidth < self.squeeze_threshold:
            signal = f"布林带收窄至 {bandwidth:.1f}%，变盘在即，密切关注方向选择"
            return BOLLStatus.SQUEEZE, signal, "中等"
        
        # 2. 判断是否突破上轨
        if price > upper:
            signal = f"突破上轨 {abs(dist_upper):.1f}%，强势特征，但需防止回落"
            return BOLLStatus.BREAK_UPPER, signal, "高"
        
        # 3. 判断是否跌破下轨
        if price < lower:
            signal = f"跌破下轨 {abs(dist_lower):.1f}%，弱势特征，等待企稳信号"
            return BOLLStatus.BREAK_LOWER, signal, "高"
        
        # 4. 判断是否触及上轨（超买）
        if dist_upper <= self.touch_threshold:
            signal = f"接近上轨（距离 {dist_upper:.1f}%），超买区域，注意回调风险"
            return BOLLStatus.UPPER_TOUCH, signal, "高"
        
        # 5. 判断是否触及下轨（超卖）
        if dist_lower <= self.touch_threshold:
            signal = f"接近下轨（距离 {dist_lower:.1f}%），超卖区域，可能反弹"
            return BOLLStatus.LOWER_TOUCH, signal, "低"
        
        # 6. 判断是否布林带扩张
        if len(df) >= 5:
            prev_bandwidth = ((df['BOLL_UPPER'].iloc[-5] - df['BOLL_LOWER'].iloc[-5]) 
                            / df['MA20'].iloc[-5] * 100)
            if bandwidth > prev_bandwidth * 1.2:
                trend = "上涨" if price > middle else "下跌"
                signal = f"布林带扩张（{bandwidth:.1f}%），{trend}趋势延续"
                return BOLLStatus.EXPANSION, signal, "中等"
        
        # 7. 默认：中轨附近
        if price > middle:
            signal = f"价格在中轨上方，多头占优，支撑位 {middle:.2f}"
        else:
            signal = f"价格在中轨下方，空头占优，压力位 {middle:.2f}"
        
        return BOLLStatus.MIDDLE_NEAR, signal, "中等"
    
    def get_support_resistance(self, df: pd.DataFrame) -> Dict[str, list]:
        """
        获取支撑位和压力位
        
        Returns:
            {'support': [支撑位列表], 'resistance': [压力位列表]}
        """
        if not self.validate_data(df, self.period):
            return {'support': [], 'resistance': []}
        
        df = df.copy()
        df['MA20'] = df['close'].rolling(window=self.period).mean()
        df['STD'] = df['close'].rolling(window=self.period).std()
        df['BOLL_UPPER'] = df['MA20'] + (self.std_dev * df['STD'])
        df['BOLL_LOWER'] = df['MA20'] - (self.std_dev * df['STD'])
        
        latest = df.iloc[-1]
        middle = float(latest['MA20'])
        lower = float(latest['BOLL_LOWER'])
        upper = float(latest['BOLL_UPPER'])
        
        # 支撑位：下轨 < 中轨
        support = [lower, middle]
        
        # 压力位：中轨 < 上轨
        resistance = [middle, upper]
        
        return {
            'support': sorted(support),
            'resistance': sorted(resistance, reverse=True)
        }
