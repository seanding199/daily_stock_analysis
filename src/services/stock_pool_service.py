# -*- coding: utf-8 -*-
"""
股票池服务

提供推荐选股的候选股票来源：
1. 底部蓄力策略：找到低位+大资金流入的板块，挑选里面蓄积最好的股票
2. 配置文件自定义扫描池 (SCAN_STOCK_LIST)
3. 自选股列表 (STOCK_LIST) 兜底
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class SectorScore:
    """板块评分结果"""
    name: str
    position_pct: float       # 位置百分位 (0=最低, 100=最高)
    fund_flow_score: float    # 资金流入评分 (0~100)
    accumulation_score: float # 蓄力综合评分 (0~100)
    recent_inflow_days: int   # 近期连续净流入天数
    total_inflow_5d: float    # 近5日主力累计净流入(亿)
    total_inflow_10d: float   # 近10日主力累计净流入(亿)
    change_pct_5d: float      # 近5日涨跌幅
    detail: str               # 说明


class StockPoolService:
    """股票池管理"""

    def __init__(self, config=None):
        self.config = config or get_config()

    # ===================== 底部蓄力策略 =====================

    def find_accumulation_sectors(
        self,
        position_threshold: float = 40.0,
        min_inflow_days: int = 2,
        top_n: int = 5,
        lookback_days: int = 60,
    ) -> List[SectorScore]:
        """
        找到处于低位且有大资金持续流入的板块

        策略：
        1. 低位判断: 当前价格在近N日范围的低位区域 (position_pct < threshold)
        2. 资金流入: 近期有连续多日主力净流入
        3. 蓄力评分: 综合低位 + 资金流入强度 + 持续性
        """
        try:
            import akshare as ak
            import pandas as pd
        except ImportError:
            logger.warning("akshare 未安装，无法执行底部蓄力分析")
            return []

        # 1. 获取所有行业板块
        try:
            all_sectors_df = ak.stock_board_industry_name_em()
            sector_names = all_sectors_df["板块名称"].tolist()
            logger.info(f"获取到 {len(sector_names)} 个行业板块")
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")
            return []

        # 2. 获取今日资金流向排名
        flow_today = {}
        try:
            flow_df = ak.stock_sector_fund_flow_rank(
                indicator="今日", sector_type="行业资金流"
            )
            flow_df["今日主力净流入-净额"] = pd.to_numeric(
                flow_df["今日主力净流入-净额"], errors="coerce"
            )
            for _, row in flow_df.iterrows():
                flow_today[row["名称"]] = row["今日主力净流入-净额"]
            logger.info(f"获取今日资金流向: {len(flow_today)} 个板块")
        except Exception as e:
            logger.warning(f"获取资金流向失败: {e}")

        # 3. 对每个板块计算低位 + 蓄力评分
        candidates: List[SectorScore] = []

        for sector_name in sector_names:
            try:
                # 获取板块K线历史
                hist_df = ak.stock_board_industry_hist_em(
                    symbol=sector_name, period="日k",
                    start_date=(pd.Timestamp.now() - pd.Timedelta(days=lookback_days + 30)).strftime("%Y%m%d"),
                    end_date=pd.Timestamp.now().strftime("%Y%m%d"),
                )
                if hist_df is None or len(hist_df) < 20:
                    continue

                closes = hist_df["收盘"].values[-lookback_days:]
                current = closes[-1]
                high = np.max(closes)
                low = np.min(closes)
                range_val = high - low
                if range_val <= 0:
                    continue

                # 位置百分位: 0=最低, 100=最高
                position_pct = (current - low) / range_val * 100

                # 只留低位板块
                if position_pct > position_threshold:
                    continue

                # 获取板块历史资金流向
                try:
                    fund_hist = ak.stock_sector_fund_flow_hist(symbol=sector_name)
                    if fund_hist is None or len(fund_hist) < 5:
                        continue
                    fund_hist = fund_hist.sort_values("日期", ascending=True)
                    inflows = fund_hist["主力净流入-净额"].values

                    # 近5日累计流入
                    total_5d = np.sum(inflows[-5:]) / 1e8
                    # 近10日累计流入
                    total_10d = np.sum(inflows[-10:]) / 1e8 if len(inflows) >= 10 else total_5d

                    # 连续净流入天数（从最近一天往前数）
                    consecutive = 0
                    for v in reversed(inflows[-10:]):
                        if v > 0:
                            consecutive += 1
                        else:
                            break

                    # 过滤: 至少有一定资金流入迹象
                    if consecutive < min_inflow_days and total_5d <= 0:
                        continue

                    # 评分组成：
                    # 1) 低位分 (0~40): 越低越好
                    pos_score = max(0, (position_threshold - position_pct) / position_threshold * 40)

                    # 2) 资金流入强度分 (0~35)
                    inflow_strength = 0
                    if total_5d > 0:
                        inflow_strength += min(20, total_5d / 5 * 20)  # 5亿以上满分
                    if total_10d > 0:
                        inflow_strength += min(15, total_10d / 15 * 15)  # 15亿以上满分

                    # 3) 持续性分 (0~25): 连续流入天数
                    persist_score = min(25, consecutive / 5 * 25)

                    total_score = pos_score + inflow_strength + persist_score

                    # 5日涨跌幅
                    chg_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0

                    detail_parts = []
                    detail_parts.append(f"位置{position_pct:.0f}%")
                    detail_parts.append(f"5日流入{total_5d:.1f}亿")
                    detail_parts.append(f"连续{consecutive}日")
                    detail_parts.append(f"5日涨跌{chg_5d:+.1f}%")

                    candidates.append(SectorScore(
                        name=sector_name,
                        position_pct=position_pct,
                        fund_flow_score=inflow_strength,
                        accumulation_score=total_score,
                        recent_inflow_days=consecutive,
                        total_inflow_5d=total_5d,
                        total_inflow_10d=total_10d,
                        change_pct_5d=chg_5d,
                        detail=" | ".join(detail_parts),
                    ))
                except Exception as e:
                    logger.debug(f"板块 [{sector_name}] 资金流向获取失败: {e}")
                    continue

            except Exception as e:
                logger.debug(f"板块 [{sector_name}] 分析失败: {e}")
                continue

        # 按蓄力评分排序
        candidates.sort(key=lambda x: x.accumulation_score, reverse=True)
        top = candidates[:top_n]

        if top:
            logger.info(f"底部蓄力板块 Top{top_n}:")
            for s in top:
                logger.info(f"  [{s.name}] 评分={s.accumulation_score:.1f} | {s.detail}")

        return top

    def get_sector_stocks(
        self,
        sector_name: str,
    ) -> List[Dict]:
        """
        获取板块成分股

        Returns: [{"code": str, "name": str, "change_pct": float, "board": str}]
        """
        try:
            import akshare as ak
            import pandas as pd

            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is None or df.empty:
                return []

            code_col = "代码" if "代码" in df.columns else None
            name_col = "名称" if "名称" in df.columns else None
            chg_col = None
            for c in ["涨跌幅", "涨幅"]:
                if c in df.columns:
                    chg_col = c
                    break
            if not code_col or not chg_col:
                return []

            df[chg_col] = pd.to_numeric(df[chg_col], errors="coerce")
            df = df.dropna(subset=[chg_col])

            stocks = []
            for _, row in df.iterrows():
                code = str(row[code_col]).strip()
                stock_name = str(row.get(name_col, "")) if name_col else ""
                if "ST" in stock_name.upper():
                    continue
                if code.startswith("8") or code.startswith("9"):
                    continue
                stocks.append({
                    "code": code,
                    "name": stock_name,
                    "change_pct": float(row[chg_col]),
                    "board": sector_name,
                })

            return stocks

        except Exception as e:
            logger.warning(f"获取板块 [{sector_name}] 成分股失败: {e}")
            return []

    def get_hot_board_stocks(
        self,
        board_top_n: int = 5,
        stock_top_n: int = 10,
        position_threshold: float = 40.0,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        底部蓄力策略：找到低位+大资金流入的板块，返回其成分股

        Returns:
            (accumulation_stocks, []) — 蓄力股列表，第二个元素保留为空以兼容接口
        """
        sectors = self.find_accumulation_sectors(
            position_threshold=position_threshold,
            top_n=board_top_n,
        )

        if not sectors:
            logger.warning("未找到底部蓄力板块")
            return [], []

        all_stocks: List[Dict] = []
        seen_codes: Set[str] = set()

        for sector in sectors:
            stocks = self.get_sector_stocks(sector.name)
            for s in stocks:
                if s["code"] not in seen_codes:
                    seen_codes.add(s["code"])
                    all_stocks.append(s)

        logger.info(f"蓄力板块合计 {len(all_stocks)} 只股票（去重后）")

        return all_stocks, []

    # ===================== 静态池 =====================

    def get_scan_pool(self) -> List[str]:
        """获取扫描池（合并去重）"""
        pool: Set[str] = set()

        if self.config.scan_stock_list:
            pool.update(self.config.scan_stock_list)
            logger.info(f"扫描池: 加载配置股票 {len(self.config.scan_stock_list)} 只")

        if not pool and self.config.stock_list:
            pool.update(self.config.stock_list)
            logger.info(f"扫描池: 回退到自选股 {len(self.config.stock_list)} 只")

        result = sorted(pool)
        logger.info(f"静态扫描池: {len(result)} 只股票")
        return result

    def get_board_stocks(self, board_name: str) -> List[str]:
        """获取板块成分股代码列表"""
        try:
            import akshare as ak
            try:
                df = ak.stock_board_industry_cons_em(symbol=board_name)
                if df is not None and not df.empty:
                    col = "代码" if "代码" in df.columns else df.columns[1]
                    codes = df[col].astype(str).tolist()
                    logger.info(f"板块 [{board_name}] 成分股: {len(codes)} 只")
                    return codes
            except Exception:
                pass

            try:
                df = ak.stock_board_concept_cons_em(symbol=board_name)
                if df is not None and not df.empty:
                    col = "代码" if "代码" in df.columns else df.columns[1]
                    codes = df[col].astype(str).tolist()
                    logger.info(f"概念板块 [{board_name}] 成分股: {len(codes)} 只")
                    return codes
            except Exception:
                pass

            logger.warning(f"板块 [{board_name}] 未找到成分股")
            return []
        except ImportError:
            logger.warning("akshare 未安装，无法获取板块成分股")
            return []
        except Exception as e:
            logger.error(f"获取板块 [{board_name}] 成分股异常: {e}")
            return []

    def build_full_pool(self) -> List[str]:
        """
        构建完整扫描池

        策略：
        1. 底部蓄力板块 -> 获取成分股
        2. 合并配置的静态扫描池
        3. 去重
        """
        pool: Set[str] = set()

        # 1. 动态池：底部蓄力板块的股票
        acc_stocks, _ = self.get_hot_board_stocks(board_top_n=5)
        for stock in acc_stocks:
            pool.add(stock["code"])

        if pool:
            logger.info(f"动态扫描池: {len(pool)} 只股票")
        else:
            logger.info("动态扫描池为空，回退到静态扫描池")
            static = self.get_scan_pool()
            pool.update(static)

        # 2. 追加配置的板块成分股
        if self.config.scan_boards:
            for board in self.config.scan_boards:
                stocks = self.get_board_stocks(board)
                pool.update(stocks)

        result = sorted(pool)
        logger.info(f"完整扫描池: {len(result)} 只股票")
        return result
