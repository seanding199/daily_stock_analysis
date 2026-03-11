# -*- coding: utf-8 -*-
"""
股票池服务

提供推荐选股的候选股票来源：
1. 每日涨跌幅前3+后3板块的成分股，按涨跌幅取前10+后10
2. 配置文件自定义扫描池 (SCAN_STOCK_LIST)
3. 自选股列表 (STOCK_LIST) 兜底
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

from src.config import get_config

logger = logging.getLogger(__name__)


class StockPoolService:
    """股票池管理"""

    def __init__(self, config=None):
        self.config = config or get_config()

    def get_hot_board_stocks(
        self,
        board_top_n: int = 3,
        stock_top_n: int = 10,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        获取每日涨跌幅前N和后N板块中，涨幅/跌幅排名前M的股票

        Returns:
            (gainers, losers) — 每个元素是 {'code': str, 'name': str, 'change_pct': float, 'board': str}
        """
        try:
            import akshare as ak
            import pandas as pd
            from data_provider import DataFetcherManager

            dfm = DataFetcherManager()
            rankings = dfm.get_sector_rankings(n=board_top_n)
            if not rankings:
                logger.warning("获取板块排行失败，无法构建动态扫描池")
                return [], []

            top_sectors, bottom_sectors = rankings
            all_sectors = top_sectors + bottom_sectors
            logger.info(
                f"涨幅前{board_top_n}: {[s['name'] for s in top_sectors]} | "
                f"跌幅前{board_top_n}: {[s['name'] for s in bottom_sectors]}"
            )

            # 收集所有板块成分股（带涨跌幅）
            all_stocks: List[Dict] = []
            seen_codes: Set[str] = set()

            for sector in all_sectors:
                board_name = sector['name']
                try:
                    df = ak.stock_board_industry_cons_em(symbol=board_name)
                    if df is None or df.empty:
                        continue

                    # 识别列名
                    code_col = '代码' if '代码' in df.columns else None
                    name_col = '名称' if '名称' in df.columns else None
                    chg_col = None
                    for c in ['涨跌幅', '涨幅']:
                        if c in df.columns:
                            chg_col = c
                            break

                    if not code_col or not chg_col:
                        logger.debug(f"板块 [{board_name}] 列名不匹配: {df.columns.tolist()}")
                        continue

                    df[chg_col] = pd.to_numeric(df[chg_col], errors='coerce')
                    df = df.dropna(subset=[chg_col])

                    for _, row in df.iterrows():
                        code = str(row[code_col]).strip()
                        if code in seen_codes:
                            continue
                        # 排除 ST
                        stock_name = str(row.get(name_col, '')) if name_col else ''
                        if 'ST' in stock_name.upper():
                            continue
                        # 排除北交所
                        if code.startswith('8') or code.startswith('9'):
                            continue

                        seen_codes.add(code)
                        all_stocks.append({
                            'code': code,
                            'name': stock_name,
                            'change_pct': float(row[chg_col]),
                            'board': board_name,
                        })

                except Exception as e:
                    logger.warning(f"获取板块 [{board_name}] 成分股失败: {e}")
                    continue

            if not all_stocks:
                return [], []

            # 按涨跌幅排序，取涨幅前N和跌幅前N
            all_stocks.sort(key=lambda x: x['change_pct'], reverse=True)
            gainers = all_stocks[:stock_top_n]
            losers = all_stocks[-stock_top_n:]

            logger.info(
                f"动态扫描池: 涨幅前{stock_top_n} + 跌幅前{stock_top_n}，"
                f"合计 {len(gainers) + len(losers)} 只（去重后）"
            )
            return gainers, losers

        except ImportError:
            logger.warning("akshare 未安装，无法获取板块成分股")
            return [], []
        except Exception as e:
            logger.error(f"构建动态扫描池异常: {e}")
            return [], []

    def get_scan_pool(self) -> List[str]:
        """
        获取扫描池（合并去重）

        优先级：
        1. SCAN_STOCK_LIST（配置的静态扫描池）
        2. 如果为空，回退到自选股列表
        """
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
                    col = '代码' if '代码' in df.columns else df.columns[1]
                    codes = df[col].astype(str).tolist()
                    logger.info(f"板块 [{board_name}] 成分股: {len(codes)} 只")
                    return codes
            except Exception:
                pass

            try:
                df = ak.stock_board_concept_cons_em(symbol=board_name)
                if df is not None and not df.empty:
                    col = '代码' if '代码' in df.columns else df.columns[1]
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
        1. 获取涨跌幅前3+后3板块 -> 取涨幅前10+跌幅前10的股票
        2. 合并配置的静态扫描池和板块扫描
        3. 去重
        """
        pool: Set[str] = set()

        # 1. 动态池：涨跌幅板块 Top 股票
        gainers, losers = self.get_hot_board_stocks(
            board_top_n=3,
            stock_top_n=10,
        )
        for stock in gainers + losers:
            pool.add(stock['code'])

        if pool:
            logger.info(f"动态扫描池: {len(pool)} 只股票")
        else:
            # 动态池为空时回退到静态池
            logger.info("动态扫描池为空，回退到静态扫描池")
            static = self.get_scan_pool()
            pool.update(static)

        # 2. 追加配置的板块成分股（如有）
        if self.config.scan_boards:
            for board in self.config.scan_boards:
                stocks = self.get_board_stocks(board)
                pool.update(stocks)

        result = sorted(pool)
        logger.info(f"完整扫描池: {len(result)} 只股票")
        return result
