# -*- coding: utf-8 -*-
"""
交易日历工具

判断当前日期是否为 A 股交易日。
优先使用 chinese_calendar 库（包含节假日信息），
回退到简单的周末判断。
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


def is_trading_day(d: date = None) -> bool:
    """
    判断指定日期是否为 A 股交易日。

    Args:
        d: 日期，默认今天

    Returns:
        True 表示是交易日
    """
    if d is None:
        d = date.today()

    # 周末一定不是交易日
    if d.weekday() >= 5:
        return False

    try:
        from chinese_calendar import is_holiday
        return not is_holiday(d)
    except ImportError:
        logger.debug("chinese_calendar 未安装，仅按周末判断交易日")
        return True  # 工作日默认视为交易日
    except Exception as e:
        logger.warning(f"交易日判断异常: {e}")
        return True
