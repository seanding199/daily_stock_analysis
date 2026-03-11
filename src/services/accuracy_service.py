# -*- coding: utf-8 -*-
"""
AI 建议准确率统计服务

基于回测数据，计算 AI 各类建议的历史胜率，
并提供格式化摘要供注入 prompt 或展示给用户。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.storage import DatabaseManager, BacktestResult, BacktestSummary, AnalysisHistory

logger = logging.getLogger(__name__)


class AccuracyService:
    """AI 建议准确率统计"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def get_overall_accuracy(self) -> Optional[Dict[str, Any]]:
        """获取整体准确率统计"""
        from src.services.backtest_service import BacktestService
        service = BacktestService(self.db)
        return service.get_summary(scope="overall", code=None)

    def get_stock_accuracy(self, code: str) -> Optional[Dict[str, Any]]:
        """获取单只股票的准确率统计"""
        from src.services.backtest_service import BacktestService
        service = BacktestService(self.db)
        return service.get_summary(scope="stock", code=code)

    def get_advice_win_rates(self, code: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        获取各类建议的胜率统计

        Returns:
            {
                "买入": {"total": 10, "win": 7, "loss": 2, "neutral": 1, "win_rate": 77.8},
                "卖出": {"total": 5, "win": 1, "loss": 3, "neutral": 1, "win_rate": 25.0},
                ...
            }
        """
        summary = self.get_stock_accuracy(code) if code else self.get_overall_accuracy()
        if not summary:
            return {}

        breakdown = summary.get('advice_breakdown', {})
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except (json.JSONDecodeError, TypeError):
                return {}
        return breakdown

    def get_sentiment_accuracy(self, code: Optional[str] = None) -> Dict[str, Any]:
        """
        按评分区间统计准确率

        将 sentiment_score 分为 5 个区间，统计每个区间的实际胜率：
        - 0-20: 强烈看空
        - 20-40: 看空
        - 40-60: 震荡
        - 60-80: 看多
        - 80-100: 强烈看多

        Returns:
            {
                "0-20": {"count": 5, "avg_return": -3.2, "win_rate": 20.0},
                "20-40": {"count": 8, "avg_return": -1.5, "win_rate": 37.5},
                ...
            }
        """
        from sqlalchemy import select, and_

        buckets = {
            "0-20": (0, 20),
            "20-40": (20, 40),
            "40-60": (40, 60),
            "60-80": (60, 80),
            "80-100": (80, 100),
        }

        result = {}

        try:
            with self.db.get_session() as session:
                # 联表查询：AnalysisHistory + BacktestResult
                conditions = [BacktestResult.eval_status == 'completed']
                if code:
                    conditions.append(BacktestResult.code == code)

                rows = session.execute(
                    select(
                        AnalysisHistory.sentiment_score,
                        BacktestResult.outcome,
                        BacktestResult.stock_return_pct,
                    ).join(
                        BacktestResult,
                        BacktestResult.analysis_history_id == AnalysisHistory.id
                    ).where(and_(*conditions))
                ).all()

                if not rows:
                    return {}

                # 按区间统计
                for bucket_name, (low, high) in buckets.items():
                    bucket_rows = [
                        r for r in rows
                        if r.sentiment_score is not None and low <= r.sentiment_score < high
                    ]
                    if not bucket_rows:
                        result[bucket_name] = {"count": 0, "avg_return": None, "win_rate": None}
                        continue

                    count = len(bucket_rows)
                    wins = sum(1 for r in bucket_rows if r.outcome == 'win')
                    returns = [r.stock_return_pct for r in bucket_rows if r.stock_return_pct is not None]
                    avg_ret = sum(returns) / len(returns) if returns else None

                    result[bucket_name] = {
                        "count": count,
                        "avg_return": round(avg_ret, 2) if avg_ret is not None else None,
                        "win_rate": round(wins / count * 100, 1) if count > 0 else None,
                    }

        except Exception as e:
            logger.warning(f"评分准确率统计失败: {e}")
            return {}

        return result

    def format_accuracy_summary(self, code: Optional[str] = None) -> Optional[str]:
        """
        格式化准确率摘要（用于注入 prompt 或推送报告）

        Returns:
            格式化的准确率摘要文本，无数据时返回 None
        """
        # 获取建议胜率
        advice_rates = self.get_advice_win_rates(code)
        sentiment_rates = self.get_sentiment_accuracy(code)

        if not advice_rates and not sentiment_rates:
            return None

        lines = []

        if advice_rates:
            lines.append("## AI 历史准确率")
            lines.append("| 建议类型 | 总次数 | 胜率 | 败率 |")
            lines.append("|----------|--------|------|------|")
            for advice, stats in sorted(advice_rates.items(), key=lambda x: x[1].get('total', 0), reverse=True):
                total = stats.get('total', 0)
                if total == 0:
                    continue
                win = stats.get('win', 0)
                loss = stats.get('loss', 0)
                win_pct = stats.get('win_rate_pct', stats.get('win_rate', 0))
                loss_pct = round(loss / total * 100, 1) if total > 0 else 0
                lines.append(f"| {advice} | {total} | {win_pct:.1f}% | {loss_pct:.1f}% |")

        if sentiment_rates:
            has_data = any(v.get('count', 0) > 0 for v in sentiment_rates.values())
            if has_data:
                lines.append("")
                lines.append("### 评分区间准确率")
                lines.append("| 评分区间 | 样本数 | 平均收益 | 胜率 |")
                lines.append("|----------|--------|----------|------|")
                for bucket, stats in sentiment_rates.items():
                    count = stats.get('count', 0)
                    if count == 0:
                        continue
                    avg_ret = stats.get('avg_return')
                    win_rate = stats.get('win_rate')
                    avg_str = f"{avg_ret:+.2f}%" if avg_ret is not None else "N/A"
                    win_str = f"{win_rate:.1f}%" if win_rate is not None else "N/A"
                    lines.append(f"| {bucket} | {count} | {avg_str} | {win_str} |")

        return '\n'.join(lines) if lines else None

    def format_accuracy_for_prompt(self, code: Optional[str] = None) -> Optional[str]:
        """
        格式化准确率摘要（用于注入 AI prompt，紧凑格式）

        Returns:
            紧凑格式的准确率摘要，无数据时返回 None
        """
        advice_rates = self.get_advice_win_rates(code)
        if not advice_rates:
            return None

        # 只取有样本的建议
        parts = []
        for advice, stats in advice_rates.items():
            total = stats.get('total', 0)
            if total < 3:  # 样本太少不展示
                continue
            win_pct = stats.get('win_rate_pct', stats.get('win_rate', 0))
            parts.append(f"{advice}={win_pct:.0f}%({total}次)")

        if not parts:
            return None

        return "AI历史胜率: " + " | ".join(parts)
