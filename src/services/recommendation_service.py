# -*- coding: utf-8 -*-
"""推荐选股服务"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from src.config import get_config, Config
from src.storage import DatabaseManager, StockRecommendation, get_db
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult
from src.services.stock_pool_service import StockPoolService

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    code: str
    name: str
    trend_result: Optional[TrendAnalysisResult] = None
    error: Optional[str] = None
    board: Optional[str] = None
    day_change_pct: Optional[float] = None

    @property
    def success(self) -> bool:
        return self.trend_result is not None


class RecommendationService:

    def __init__(self, config: Optional[Config] = None, db: Optional[DatabaseManager] = None):
        self.config = config or get_config()
        self.db = db or get_db()
        self.pool_service = StockPoolService(self.config)
        self.analyzer = StockTrendAnalyzer()

    def scan_and_score(self, codes: Optional[List[str]] = None, max_workers: Optional[int] = None) -> List[ScanResult]:
        if codes is None:
            codes = self.pool_service.build_full_pool()
        if not codes:
            logger.warning("扫描池为空")
            return []
        workers = max_workers or self.config.scan_max_workers
        logger.info(f"开始扫描 {len(codes)} 只股票，并发={workers}")
        results: List[ScanResult] = []
        start_time = time.time()
        from data_provider import DataFetcherManager
        dfm = DataFetcherManager()

        def _scan_one(code: str) -> ScanResult:
            try:
                name = dfm.get_stock_name(code) or f"股票{code}"
                df, source = dfm.get_daily_data(code, days=60)
                if df is None or df.empty or len(df) < 20:
                    return ScanResult(code=code, name=name, error="数据不足")
                trend_result = self.analyzer.analyze(df, code)
                return ScanResult(code=code, name=name, trend_result=trend_result)
            except Exception as e:
                return ScanResult(code=code, name=f"股票{code}", error=str(e))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_scan_one, code): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    result = future.result(timeout=60)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[{code}] 异常: {e}")
                    results.append(ScanResult(code=code, name=f"股票{code}", error=str(e)))
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.success)
        logger.info(f"扫描完成: {success_count}/{len(codes)} 成功，耗时 {elapsed:.1f}s")
        return results

    def filter_and_rank(self, results: List[ScanResult], min_score: Optional[int] = None,
                        signal_types: Optional[List[str]] = None, max_bias: float = 5.0,
                        exclude_codes: Optional[List[str]] = None, top_n: Optional[int] = None) -> List[ScanResult]:
        _min = min_score if min_score is not None else self.config.scan_min_score
        _top = top_n or self.config.scan_top_n
        _exclude = set(exclude_codes or [])
        filtered = []
        for r in results:
            if not r.success:
                continue
            tr = r.trend_result
            if r.code in _exclude:
                continue
            if tr.signal_score < _min:
                continue
            if signal_types and tr.buy_signal.name not in signal_types:
                continue
            if abs(tr.bias_ma5) > max_bias:
                continue
            filtered.append(r)
        filtered.sort(key=lambda x: x.trend_result.signal_score, reverse=True)
        return filtered[:_top]

    def save_results(self, results: List[ScanResult], scan_date: Optional[date] = None) -> int:
        target_date = scan_date or date.today()
        records = []
        for r in results:
            if not r.success:
                continue
            tr = r.trend_result
            records.append({
                "scan_date": target_date, "code": r.code, "name": r.name,
                "signal_score": tr.signal_score, "signal_type": tr.buy_signal.name,
                "trend_status": tr.trend_status.name if tr.trend_status else None,
                "signal_reasons": json.dumps(tr.signal_reasons, ensure_ascii=False),
                "risk_factors": json.dumps(tr.risk_factors, ensure_ascii=False),
                "close_price": tr.current_price, "change_pct": r.day_change_pct,
                "bias_rate": tr.bias_ma5, "volume_ratio": tr.volume_ratio_5d,
                "macd_status": tr.macd_status.name if tr.macd_status else None,
                "rsi_12": tr.rsi_12, "kdj_signal": None,
                "boll_position": None, "atr_pct": None,
            })
        if not records:
            return 0
        return self.db.save_recommendations(records)

    def run(self, codes: Optional[List[str]] = None, min_score: Optional[int] = None,
            top_n: Optional[int] = None, save: bool = True, notify: bool = False) -> List[ScanResult]:
        pool_info: Dict[str, Dict] = {}
        if codes is None:
            gainers, losers = self.pool_service.get_hot_board_stocks(board_top_n=3, stock_top_n=10)
            for item in gainers + losers:
                pool_info[item["code"]] = item
            codes_from_pool = list(pool_info.keys())
            if self.config.scan_stock_list:
                for c in self.config.scan_stock_list:
                    if c not in pool_info:
                        codes_from_pool.append(c)
            codes = codes_from_pool if codes_from_pool else None

        all_results = self.scan_and_score(codes)

        for r in all_results:
            if r.code in pool_info:
                info = pool_info[r.code]
                r.board = info.get("board")
                r.day_change_pct = info.get("change_pct")
                if not r.name or r.name.startswith("股票"):
                    r.name = info.get("name", r.name)

        recommended = self.filter_and_rank(all_results, min_score=min_score, top_n=top_n)
        logger.info(f"推荐选股完成: 扫描 {len(all_results)} 只，推荐 {len(recommended)} 只")

        if save and recommended:
            saved = self.save_results(recommended)
            logger.info(f"已保存 {saved} 条推荐记录")

        if notify and recommended:
            report = self.format_report(recommended)
            try:
                from src.channels.registry import ChannelRegistry
                registry = ChannelRegistry()
                registry.send_all(report)
            except Exception as e:
                logger.warning(f"推荐通知发送失败: {e}")

        return recommended

    def format_report(self, results: List[ScanResult], title: str = None) -> str:
        today = date.today().strftime("%Y-%m-%d")
        boards = set(r.board for r in results if r.board)
        board_info = f" | 来源板块: {chr(44).join(boards)}" if boards else ""

        lines = [
            f"# {title or 'AI 推荐选股报告'}",
            f"扫描日期: {today} | 推荐数量: {len(results)}{board_info}",
            "",
            "| 排名 | 代码 | 名称 | 评分 | 信号 | 趋势 | 涨跌幅 | 乖离率 | 板块 |",
            "|------|------|------|------|------|------|--------|--------|------|",
        ]

        for i, r in enumerate(results, 1):
            tr = r.trend_result
            chg_str = f"{r.day_change_pct:+.2f}%" if r.day_change_pct is not None else "N/A"
            board_str = r.board or ""
            lines.append(
                f"| {i} | {r.code} | {r.name} "
                f"| **{tr.signal_score}** | {tr.buy_signal.name} "
                f"| {tr.trend_status.name} | {chg_str} "
                f"| {tr.bias_ma5:+.1f}% | {board_str} |"
            )

        lines.append("")
        lines.append("---")
        lines.append("")

        for i, r in enumerate(results[:5], 1):
            tr = r.trend_result
            board_tag = f" [{r.board}]" if r.board else ""
            lines.append(f"### {i}. {r.name}({r.code}){board_tag} - 评分 {tr.signal_score}")
            if tr.signal_reasons:
                lines.append("**买入理由:**")
                for reason in tr.signal_reasons:
                    lines.append(f"- {reason}")
            if tr.risk_factors:
                lines.append("**风险提示:**")
                for risk in tr.risk_factors:
                    lines.append(f"- {risk}")
            lines.append(
                f"MACD={tr.macd_status.name} | RSI={tr.rsi_12:.1f} "
                f"| 趋势={tr.trend_status.name} | 量比={tr.volume_ratio_5d:.2f}"
            )
            lines.append("")

        lines.append("---")
        lines.append("> 以上推荐基于技术面评分，仅供参考，不构成投资建议。")
        return chr(10).join(lines)

    def get_history(self, scan_date: Optional[date] = None, min_score: float = 0, top_n: int = 20) -> List[Dict[str, Any]]:
        records = self.db.get_recommendations(scan_date=scan_date, min_score=min_score, top_n=top_n)
        return [r.to_dict() for r in records]
