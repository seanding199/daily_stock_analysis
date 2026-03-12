# -*- coding: utf-8 -*-
"""
ATR（平均真实波幅）指标

用途：
1. 衡量价格波动性
2. 设置止损止盈点位
3. 风险管理
4. 判断市场活跃度

应用：
- 止损位 = 买入价 - 2*ATR
- 止盈位 = 买入价 + 3*ATR
- ATR 扩大 → 波动加剧，风险增加
- ATR 缩小 → 波动减弱，可能变盘
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from .base import BaseIndicator, BaseIndicatorResult


class ATRLevel(Enum):
    """ATR波动率等级"""
    VERY_LOW = "极低波动"      # ATR < 平均值 * 0.5
    LOW = "低波动"            # ATR < 平均值 * 0.8
    NORMAL = "正常波动"        # 平均值 * 0.8 <= ATR <= 平均值 * 1.2
    HIGH = "高波动"           # ATR > 平均值 * 1.2
    VERY_HIGH = "极高波动"     # ATR > 平均值 * 1.5


@dataclass
class ATRResult(BaseIndicatorResult):
    """ATR计算结果"""
    # ATR数值
    atr: float = 0.0             # 当前ATR值
    atr_pct: float = 0.0         # ATR占股价的百分比
    
    # 波动率等级
    level: ATRLevel = ATRLevel.NORMAL
    risk_level: str = "中等"      # 风险等级：极低/低/中等/高/极高
    
    # 止损止盈建议
    stop_loss_2atr: float = 0.0   # 2倍ATR止损位
    stop_loss_3atr: float = 0.0   # 3倍ATR止损位（保守）
    take_profit_2atr: float = 0.0 # 2倍ATR止盈位（激进）
    take_profit_3atr: float = 0.0 # 3倍ATR止盈位（推荐）
    take_profit_4atr: float = 0.0 # 4倍ATR止盈位（保守）
    
    # 信号分析
    signal: str = ""             # 信号描述
    trend_strength: str = ""     # 趋势强度描述


class ATRIndicator(BaseIndicator):
    """
    ATR 指标计算器
    
    参数：
    - period: 周期，默认14日
    - stop_loss_multiplier: 止损ATR倍数，默认2倍
    - take_profit_multiplier: 止盈ATR倍数，默认3倍
    """
    
    def __init__(
        self,
        period: int = 14,
        stop_loss_multiplier: float = 2.0,
        take_profit_multiplier: float = 3.0
    ):
        self.period = period
        self.stop_loss_multiplier = stop_loss_multiplier
        self.take_profit_multiplier = take_profit_multiplier
    
    def calculate(self, df: pd.DataFrame) -> Optional[ATRResult]:
        """
        计算 ATR 指标
        
        Args:
            df: 包含 high, low, close 列的DataFrame
            
        Returns:
            ATRResult: ATR 分析结果
        """
        if not self._validate_atr_data(df, self.period):
            return None
        
        # 1. 计算真实波幅（TR）
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        
        # TR = max(高-低, abs(高-昨收), abs(低-昨收))
        df['TR'] = df.apply(
            lambda row: max(
                row['high'] - row['low'],
                abs(row['high'] - row['prev_close']) if pd.notna(row['prev_close']) else 0,
                abs(row['low'] - row['prev_close']) if pd.notna(row['prev_close']) else 0
            ),
            axis=1
        )
        
        # 2. 计算 ATR（TR的指数移动平均）
        df['ATR'] = df['TR'].ewm(span=self.period, adjust=False).mean()
        
        # 3. 获取最新数据
        latest = df.iloc[-1]
        atr = float(latest['ATR'])
        current_price = float(latest['close'])
        atr_pct = (atr / current_price) * 100
        
        # 4. 计算历史平均ATR（用于判断波动率等级）
        avg_atr = float(df['ATR'].tail(30).mean())
        
        # 5. 判断波动率等级
        level, risk_level = self._analyze_level(atr, avg_atr)
        
        # 6. 计算止损止盈位
        stop_loss_2atr = current_price - 2 * atr
        stop_loss_3atr = current_price - 3 * atr
        take_profit_2atr = current_price + 2 * atr
        take_profit_3atr = current_price + 3 * atr
        take_profit_4atr = current_price + 4 * atr
        
        # 7. 生成信号
        signal, trend_strength = self._generate_signal(
            atr, avg_atr, atr_pct, level
        )
        
        # 8. 构建结果
        result = ATRResult(
            atr=atr,
            atr_pct=atr_pct,
            level=level,
            risk_level=risk_level,
            stop_loss_2atr=stop_loss_2atr,
            stop_loss_3atr=stop_loss_3atr,
            take_profit_2atr=take_profit_2atr,
            take_profit_3atr=take_profit_3atr,
            take_profit_4atr=take_profit_4atr,
            signal=signal,
            trend_strength=trend_strength
        )
        
        return result
    
    def _validate_atr_data(self, df: pd.DataFrame, min_periods: int) -> bool:
        """验证ATR数据有效性"""
        if df is None or df.empty:
            return False
        
        if len(df) < min_periods:
            return False
        
        required_columns = ['high', 'low', 'close']
        for col in required_columns:
            if col not in df.columns:
                return False
        
        return True
    
    def _analyze_level(
        self,
        atr: float,
        avg_atr: float
    ) -> Tuple[ATRLevel, str]:
        """
        分析波动率等级
        
        Returns:
            (ATR等级, 风险等级描述)
        """
        if avg_atr == 0:
            return ATRLevel.NORMAL, "中等"
        
        ratio = atr / avg_atr
        
        if ratio < 0.5:
            return ATRLevel.VERY_LOW, "极低"
        elif ratio < 0.8:
            return ATRLevel.LOW, "低"
        elif ratio <= 1.2:
            return ATRLevel.NORMAL, "中等"
        elif ratio <= 1.5:
            return ATRLevel.HIGH, "高"
        else:
            return ATRLevel.VERY_HIGH, "极高"
    
    def _generate_signal(
        self,
        atr: float,
        avg_atr: float,
        atr_pct: float,
        level: ATRLevel
    ) -> Tuple[str, str]:
        """
        生成交易信号
        
        Returns:
            (信号描述, 趋势强度描述)
        """
        # 生成信号描述
        if level == ATRLevel.VERY_LOW:
            signal = f"波动率极低（ATR={atr:.2f}，占股价{atr_pct:.1f}%），市场平静，可能即将变盘"
            trend_strength = "盘整，等待突破"
        elif level == ATRLevel.LOW:
            signal = f"波动率较低（ATR={atr:.2f}，占股价{atr_pct:.1f}%），市场较为平静"
            trend_strength = "趋势不明显"
        elif level == ATRLevel.NORMAL:
            signal = f"波动率正常（ATR={atr:.2f}，占股价{atr_pct:.1f}%），风险可控"
            trend_strength = "正常波动"
        elif level == ATRLevel.HIGH:
            signal = f"波动率较高（ATR={atr:.2f}，占股价{atr_pct:.1f}%），市场活跃，注意风险"
            trend_strength = "趋势明显"
        else:  # VERY_HIGH
            signal = f"波动率极高（ATR={atr:.2f}，占股价{atr_pct:.1f}%），市场剧烈波动，风险极大"
            trend_strength = "剧烈波动"
        
        return signal, trend_strength
    
    def calculate_position_size(
        self,
        capital: float,
        risk_per_trade: float,
        entry_price: float,
        atr: float
    ) -> dict:
        """
        基于ATR计算仓位大小
        
        Args:
            capital: 总资金
            risk_per_trade: 单笔交易风险比例（如0.02表示2%）
            entry_price: 入场价格
            atr: ATR值
            
        Returns:
            {'shares': 股数, 'position_value': 仓位金额, 'risk_amount': 风险金额}
        """
        # 风险金额 = 总资金 * 单笔风险比例
        risk_amount = capital * risk_per_trade
        
        # 止损距离 = 2 * ATR
        stop_distance = 2 * atr
        
        # 股数 = 风险金额 / 止损距离
        shares = int(risk_amount / stop_distance)
        
        # 仓位金额 = 股数 * 入场价格
        position_value = shares * entry_price
        
        return {
            'shares': shares,
            'position_value': position_value,
            'risk_amount': risk_amount,
            'stop_loss': entry_price - stop_distance
        }
