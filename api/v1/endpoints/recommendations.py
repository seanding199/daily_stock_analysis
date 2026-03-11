# -*- coding: utf-8 -*-
"""
推荐选股接口

提供：
- POST /scan          触发一次扫描
- GET  /              查询推荐结果
- GET  /report        获取 Markdown 格式报告
"""

import logging
import threading
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.recommendations import (
    ScanRequest,
    RecommendationItem,
    RecommendationListResponse,
    ScanAccepted,
)
from api.v1.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 扫描锁，防止并发扫描
_scan_lock = threading.Lock()
_scan_running = False


@router.post(
    "/scan",
    response_model=ScanAccepted,
    responses={409: {"model": ErrorResponse}},
    summary="触发推荐选股扫描",
)
def trigger_scan(request: ScanRequest):
    """异步触发一次推荐选股扫描"""
    global _scan_running

    if _scan_running:
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "扫描正在进行中，请稍后重试"},
        )

    from src.services.recommendation_service import RecommendationService
    svc = RecommendationService()

    # 确定扫描池
    codes = request.codes
    if not codes:
        from src.services.stock_pool_service import StockPoolService
        pool_svc = StockPoolService()
        codes = pool_svc.build_full_pool()

    pool_size = len(codes)

    # 后台线程执行扫描
    def _run_scan():
        global _scan_running
        _scan_running = True
        try:
            svc.run(
                codes=codes,
                min_score=request.min_score,
                top_n=request.top_n,
                save=True,
                notify=request.notify,
            )
        except Exception as e:
            logger.error(f"扫描异常: {e}")
        finally:
            _scan_running = False

    thread = threading.Thread(target=_run_scan, daemon=True)
    thread.start()

    return ScanAccepted(scan_pool_size=pool_size)


@router.get(
    "",
    response_model=RecommendationListResponse,
    summary="查询推荐结果",
)
def get_recommendations(
    scan_date: Optional[str] = Query(None, description="扫描日期 YYYY-MM-DD，默认今天"),
    min_score: float = Query(0, description="最低评分"),
    top_n: int = Query(20, description="返回数量", ge=1, le=100),
    signal_type: Optional[str] = Query(None, description="信号类型过滤，如 STRONG_BUY,BUY"),
):
    """查询指定日期的推荐选股结果"""
    from src.services.recommendation_service import RecommendationService
    svc = RecommendationService()

    target_date = None
    if scan_date:
        try:
            target_date = date.fromisoformat(scan_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    signal_types = None
    if signal_type:
        signal_types = [s.strip() for s in signal_type.split(',')]

    records = svc.db.get_recommendations(
        scan_date=target_date,
        min_score=min_score,
        top_n=top_n,
        signal_types=signal_types,
    )

    items = [RecommendationItem(**r.to_dict()) for r in records]
    return RecommendationListResponse(
        scan_date=(target_date or date.today()).isoformat(),
        total=len(items),
        recommendations=items,
    )


@router.get(
    "/report",
    response_model=dict,
    summary="获取推荐报告（Markdown）",
)
def get_report(
    scan_date: Optional[str] = Query(None, description="扫描日期"),
    min_score: float = Query(65, description="最低评分"),
    top_n: int = Query(10, description="推荐数量"),
):
    """获取 Markdown 格式的推荐报告"""
    from src.services.recommendation_service import RecommendationService
    svc = RecommendationService()

    target_date = None
    if scan_date:
        try:
            target_date = date.fromisoformat(scan_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")

    records = svc.db.get_recommendations(
        scan_date=target_date,
        min_score=min_score,
        top_n=top_n,
    )

    if not records:
        return {"success": True, "report": "暂无推荐数据，请先执行扫描。"}

    # 构建简化的 ScanResult 来生成报告
    lines = [
        f"# AI 推荐选股报告",
        f"**日期**: {(target_date or date.today()).isoformat()} | **数量**: {len(records)}",
        "",
        "| 排名 | 代码 | 名称 | 评分 | 信号 | 趋势 | 价格 | 乖离率 |",
        "|------|------|------|------|------|------|------|--------|",
    ]
    for i, r in enumerate(records, 1):
        lines.append(
            f"| {i} | {r.code} | {r.name or ''} "
            f"| **{r.signal_score:.0f}** | {r.signal_type} "
            f"| {r.trend_status or ''} | {r.close_price or 0:.2f} "
            f"| {r.bias_rate or 0:+.1f}% |"
        )

    return {"success": True, "report": '\n'.join(lines)}


@router.get(
    "/status",
    summary="查询扫描状态",
)
def scan_status():
    """查询当前是否有扫描正在进行"""
    return {"scanning": _scan_running}
