# -*- coding: utf-8 -*-
"""
技术指标基础类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import pandas as pd


class BaseIndicator(ABC):
    """技术指标基类"""
    
    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> Any:
        """
        计算指标
        
        Args:
            df: 包含 OHLCV 数据的 DataFrame
            
        Returns:
            指标计算结果
        """
        pass
    
    def validate_data(self, df: pd.DataFrame, min_periods: int) -> bool:
        """
        验证数据有效性
        
        Args:
            df: 数据DataFrame
            min_periods: 最小周期数
            
        Returns:
            bool: 数据是否有效
        """
        if df is None or df.empty:
            return False
        
        if len(df) < min_periods:
            return False
        
        required_columns = ['close']
        for col in required_columns:
            if col not in df.columns:
                return False
        
        return True


class BaseIndicatorResult:
    """指标结果基类"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            k: v.value if hasattr(v, 'value') else v
            for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
