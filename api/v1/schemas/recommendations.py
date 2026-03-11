# -*- coding: utf-8 -*-
"""推荐选股接口的请求/响应模型"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """触发扫描请求"""
    codes: Optional[List[str]] = Field(None, description="股票代码列表，为空则使用配置扫描池")
    min_score: Optional[int] = Field(None, description="最低评分", ge=0, le=100)
    top_n: Optional[int] = Field(None, description="返回前 N 名", ge=1, le=100)
    notify: bool = Field(False, description="是否发送通知")


class RecommendationItem(BaseModel):
    """单条推荐记录"""
    code: str
    name: Optional[str] = None
    signal_score: Optional[float] = None
    signal_type: Optional[str] = None
    trend_status: Optional[str] = None
    signal_reasons: List[str] = []
    risk_factors: List[str] = []
    close_price: Optional[float] = None
    change_pct: Optional[float] = None
    bias_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    macd_status: Optional[str] = None
    rsi_12: Optional[float] = None
    kdj_signal: Optional[str] = None
    boll_position: Optional[float] = None
    atr_pct: Optional[float] = None


class RecommendationListResponse(BaseModel):
    """推荐列表响应"""
    success: bool = True
    scan_date: str
    total: int
    recommendations: List[RecommendationItem]


class ScanAccepted(BaseModel):
    """扫描任务已接受"""
    success: bool = True
    message: str = "扫描任务已启动"
    scan_pool_size: int = Field(..., description="扫描池大小")
