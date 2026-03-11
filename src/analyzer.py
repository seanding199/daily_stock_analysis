# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析层
===================================

职责：
1. 封装 AI API 调用逻辑（OpenAI 兼容接口）
2. 结合技术面和消息面生成分析报告
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from json_repair import repair_json

from src.config import get_config

logger = logging.getLogger(__name__)


# 股票名称映射（常见股票）
STOCK_NAME_MAP = {
    # === A股 ===
    '600519': '贵州茅台',
    '000001': '平安银行',
    '300750': '宁德时代',
    '002594': '比亚迪',
    '600036': '招商银行',
    '601318': '中国平安',
    '000858': '五粮液',
    '600276': '恒瑞医药',
    '601012': '隆基绿能',
    '002475': '立讯精密',
    '300059': '东方财富',
    '002415': '海康威视',
    '600900': '长江电力',
    '601166': '兴业银行',
    '600028': '中国石化',

    # === 美股 ===
    'AAPL': '苹果',
    'TSLA': '特斯拉',
    'MSFT': '微软',
    'GOOGL': '谷歌A',
    'GOOG': '谷歌C',
    'AMZN': '亚马逊',
    'NVDA': '英伟达',
    'META': 'Meta',
    'AMD': 'AMD',
    'INTC': '英特尔',
    'BABA': '阿里巴巴',
    'PDD': '拼多多',
    'JD': '京东',
    'BIDU': '百度',
    'NIO': '蔚来',
    'XPEV': '小鹏汽车',
    'LI': '理想汽车',
    'COIN': 'Coinbase',
    'MSTR': 'MicroStrategy',

    # === 港股 (5位数字) ===
    '00700': '腾讯控股',
    '03690': '美团',
    '01810': '小米集团',
    '09988': '阿里巴巴',
    '09618': '京东集团',
    '09888': '百度集团',
    '01024': '快手',
    '00981': '中芯国际',
    '02015': '理想汽车',
    '09868': '小鹏汽车',
    '00005': '汇丰控股',
    '01299': '友邦保险',
    '00941': '中国移动',
    '00883': '中国海洋石油',
}


def get_stock_name_multi_source(
    stock_code: str,
    context: Optional[Dict] = None,
    data_manager = None
) -> str:
    """
    多来源获取股票中文名称

    获取策略（按优先级）：
    1. 从传入的 context 中获取（realtime 数据）
    2. 从静态映射表 STOCK_NAME_MAP 获取
    3. 从 DataFetcherManager 获取（各数据源）
    4. 返回默认名称（股票+代码）

    Args:
        stock_code: 股票代码
        context: 分析上下文（可选）
        data_manager: DataFetcherManager 实例（可选）

    Returns:
        股票中文名称
    """
    # 1. 从上下文获取（实时行情数据）
    if context:
        # 优先从 stock_name 字段获取
        if context.get('stock_name'):
            name = context['stock_name']
            if name and not name.startswith('股票'):
                return name

        # 其次从 realtime 数据获取
        if 'realtime' in context and context['realtime'].get('name'):
            return context['realtime']['name']

    # 2. 从静态映射表获取
    if stock_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[stock_code]

    # 3. 从数据源获取
    if data_manager is None:
        try:
            from data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except Exception as e:
            logger.debug(f"无法初始化 DataFetcherManager: {e}")

    if data_manager:
        try:
            name = data_manager.get_stock_name(stock_code)
            if name:
                # 更新缓存
                STOCK_NAME_MAP[stock_code] = name
                return name
        except Exception as e:
            logger.debug(f"从数据源获取股票名称失败: {e}")

    # 4. 返回默认名称
    return f'股票{stock_code}'


@dataclass
class AnalysisResult:
    """
    AI 分析结果数据类 - 决策仪表盘版

    封装 Gemini 返回的分析结果，包含决策仪表盘和详细分析
    """
    code: str
    name: str

    # ========== 核心指标 ==========
    sentiment_score: int  # 综合评分 0-100 (>70强烈看多, >60看多, 40-60震荡, <40看空)
    trend_prediction: str  # 趋势预测：强烈看多/看多/震荡/看空/强烈看空
    operation_advice: str  # 操作建议：买入/加仓/持有/减仓/卖出/观望
    decision_type: str = "hold"  # 决策类型：buy/hold/sell（用于统计）
    confidence_level: str = "中"  # 置信度：高/中/低

    # ========== 决策仪表盘 (新增) ==========
    dashboard: Optional[Dict[str, Any]] = None  # 完整的决策仪表盘数据

    # ========== 走势分析 ==========
    trend_analysis: str = ""  # 走势形态分析（支撑位、压力位、趋势线等）
    short_term_outlook: str = ""  # 短期展望（1-3日）
    medium_term_outlook: str = ""  # 中期展望（1-2周）

    # ========== 技术面分析 ==========
    technical_analysis: str = ""  # 技术指标综合分析
    ma_analysis: str = ""  # 均线分析（多头/空头排列，金叉/死叉等）
    volume_analysis: str = ""  # 量能分析（放量/缩量，主力动向等）
    pattern_analysis: str = ""  # K线形态分析

    # ========== 基本面分析 ==========
    fundamental_analysis: str = ""  # 基本面综合分析
    sector_position: str = ""  # 板块地位和行业趋势
    company_highlights: str = ""  # 公司亮点/风险点

    # ========== 情绪面/消息面分析 ==========
    news_summary: str = ""  # 近期重要新闻/公告摘要
    market_sentiment: str = ""  # 市场情绪分析
    hot_topics: str = ""  # 相关热点话题

    # ========== 综合分析 ==========
    analysis_summary: str = ""  # 综合分析摘要
    key_points: str = ""  # 核心看点（3-5个要点）
    risk_warning: str = ""  # 风险提示
    buy_reason: str = ""  # 买入/卖出理由

    # ========== 元数据 ==========
    market_snapshot: Optional[Dict[str, Any]] = None  # 当日行情快照（展示用）
    raw_response: Optional[str] = None  # 原始响应（调试用）
    search_performed: bool = False  # 是否执行了联网搜索
    data_sources: str = ""  # 数据来源说明
    success: bool = True
    error_message: Optional[str] = None

    # ========== 价格数据（分析时快照）==========
    current_price: Optional[float] = None  # 分析时的股价
    change_pct: Optional[float] = None     # 分析时的涨跌幅(%)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'sentiment_score': self.sentiment_score,
            'trend_prediction': self.trend_prediction,
            'operation_advice': self.operation_advice,
            'decision_type': self.decision_type,
            'confidence_level': self.confidence_level,
            'dashboard': self.dashboard,  # 决策仪表盘数据
            'trend_analysis': self.trend_analysis,
            'short_term_outlook': self.short_term_outlook,
            'medium_term_outlook': self.medium_term_outlook,
            'technical_analysis': self.technical_analysis,
            'ma_analysis': self.ma_analysis,
            'volume_analysis': self.volume_analysis,
            'pattern_analysis': self.pattern_analysis,
            'fundamental_analysis': self.fundamental_analysis,
            'sector_position': self.sector_position,
            'company_highlights': self.company_highlights,
            'news_summary': self.news_summary,
            'market_sentiment': self.market_sentiment,
            'hot_topics': self.hot_topics,
            'analysis_summary': self.analysis_summary,
            'key_points': self.key_points,
            'risk_warning': self.risk_warning,
            'buy_reason': self.buy_reason,
            'market_snapshot': self.market_snapshot,
            'search_performed': self.search_performed,
            'success': self.success,
            'error_message': self.error_message,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
        }

    def get_core_conclusion(self) -> str:
        """获取核心结论（一句话）"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)
        return self.analysis_summary

    def get_position_advice(self, has_position: bool = False) -> str:
        """获取持仓建议"""
        if self.dashboard and 'core_conclusion' in self.dashboard:
            pos_advice = self.dashboard['core_conclusion'].get('position_advice', {})
            if has_position:
                return pos_advice.get('has_position', self.operation_advice)
            return pos_advice.get('no_position', self.operation_advice)
        return self.operation_advice

    def get_sniper_points(self) -> Dict[str, str]:
        """获取狙击点位"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('sniper_points', {})
        return {}

    def get_checklist(self) -> List[str]:
        """获取检查清单"""
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('action_checklist', [])
        return []

    def get_risk_alerts(self) -> List[str]:
        """获取风险警报"""
        if self.dashboard and 'intelligence' in self.dashboard:
            return self.dashboard['intelligence'].get('risk_alerts', [])
        return []

    def get_emoji(self) -> str:
        """根据操作建议返回对应 emoji"""
        emoji_map = {
            '买入': '🟢',
            '加仓': '🟢',
            '强烈买入': '💚',
            '持有': '🟡',
            '观望': '⚪',
            '减仓': '🟠',
            '卖出': '🔴',
            '强烈卖出': '❌',
        }
        advice = self.operation_advice or ''
        # Direct match first
        if advice in emoji_map:
            return emoji_map[advice]
        # Handle compound advice like "卖出/观望" — use the first part
        for part in advice.replace('/', '|').split('|'):
            part = part.strip()
            if part in emoji_map:
                return emoji_map[part]
        # Score-based fallback
        score = self.sentiment_score
        if score >= 80:
            return '💚'
        elif score >= 65:
            return '🟢'
        elif score >= 55:
            return '🟡'
        elif score >= 45:
            return '⚪'
        elif score >= 35:
            return '🟠'
        else:
            return '🔴'

    def get_confidence_stars(self) -> str:
        """返回置信度星级"""
        star_map = {'高': '⭐⭐⭐', '中': '⭐⭐', '低': '⭐'}
        return star_map.get(self.confidence_level, '⭐⭐')


class AIAnalyzer:
    """
    AI 分析器（OpenAI 兼容接口）

    职责：
    1. 调用 Google Gemini API 进行股票分析
    2. 结合预先搜索的新闻和技术面数据生成分析报告
    3. 解析 AI 返回的 JSON 格式结果

    使用方式：
        analyzer = AIAnalyzer()
        result = analyzer.analyze(context, news_context)
    """

    # ========================================
    # 系统提示词 - 决策仪表盘 v2.0
    # ========================================
    # 输出格式升级：从简单信号升级为决策仪表盘
    # 核心模块：核心结论 + 数据透视 + 舆情情报 + 作战计划
    # ========================================

    SYSTEM_PROMPT = """你是一位专注于趋势交易的 A 股投资分析师，负责生成专业的【决策仪表盘】分析报告。

## 核心交易理念（必须严格遵守）

### 1. 严进策略（不追高）
- **绝对不追高**：当股价偏离 MA5 超过 5% 时，坚决不买入
- **乖离率公式**：(现价 - MA5) / MA5 × 100%
- 乖离率 < 2%：最佳买点区间
- 乖离率 2-5%：可小仓介入
- 乖离率 > 5%：严禁追高！直接判定为"观望"

### 2. 趋势交易（顺势而为）
- **多头排列必须条件**：MA5 > MA10 > MA20
- 只做多头排列的股票，空头排列坚决不碰
- 均线发散上行优于均线粘合
- 趋势强度判断：看均线间距是否在扩大

### 3. 效率优先（筹码结构）
- 关注筹码集中度：90%集中度 < 15% 表示筹码集中
- 获利比例分析：70-90% 获利盘时需警惕获利回吐
- 平均成本与现价关系：现价高于平均成本 5-15% 为健康

### 4. 买点偏好（回踩支撑）
- **最佳买点**：缩量回踩 MA5 获得支撑
- **次优买点**：回踩 MA10 获得支撑
- **观望情况**：跌破 MA20 时观望

### 5. 风险排查重点
- 减持公告（股东、高管减持）
- 业绩预亏/大幅下滑
- 监管处罚/立案调查
- 行业政策利空
- 大额解禁

## 输出格式：决策仪表盘 JSON

请严格按照以下 JSON 格式输出，这是一个完整的【决策仪表盘】：

```json
{
    "stock_name": "股票中文名称",
    "sentiment_score": 0-100整数,
    "trend_prediction": "强烈看多/看多/震荡/看空/强烈看空",
    "operation_advice": "买入/加仓/持有/减仓/卖出/观望",
    "decision_type": "buy/hold/sell",
    "confidence_level": "高/中/低",

    "dashboard": {
        "core_conclusion": {
            "one_sentence": "一句话核心结论（30字以内，直接告诉用户做什么）",
            "signal_type": "🟢买入信号/🟡持有观望/🔴卖出信号/⚠️风险警告",
            "time_sensitivity": "立即行动/今日内/本周内/不急",
            "position_advice": {
                "no_position": "空仓者建议：具体操作指引",
                "has_position": "持仓者建议：具体操作指引"
            }
        },

        "data_perspective": {
            "trend_status": {
                "ma_alignment": "均线排列状态描述",
                "is_bullish": true/false,
                "trend_score": 0-100
            },
            "price_position": {
                "current_price": 当前价格数值,
                "ma5": MA5数值,
                "ma10": MA10数值,
                "ma20": MA20数值,
                "bias_ma5": 乖离率百分比数值,
                "bias_status": "安全/警戒/危险",
                "support_level": 支撑位价格,
                "resistance_level": 压力位价格
            },
            "volume_analysis": {
                "volume_ratio": 量比数值,
                "volume_status": "放量/缩量/平量",
                "turnover_rate": 换手率百分比,
                "volume_meaning": "量能含义解读（如：缩量回调表示抛压减轻）"
            },
            "chip_structure": {
                "profit_ratio": 获利比例,
                "avg_cost": 平均成本,
                "concentration": 筹码集中度,
                "chip_health": "健康/一般/警惕"
            }
        },

        "intelligence": {
            "latest_news": "【最新消息】近期重要新闻摘要",
            "risk_alerts": ["风险点1：具体描述", "风险点2：具体描述"],
            "positive_catalysts": ["利好1：具体描述", "利好2：具体描述"],
            "earnings_outlook": "业绩预期分析（基于年报预告、业绩快报等）",
            "sentiment_summary": "舆情情绪一句话总结"
        },

        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "理想买入点：XX元（在MA5附近）",
                "secondary_buy": "次优买入点：XX元（在MA10附近）",
                "stop_loss": "止损位：XX元（跌破MA20或X%）",
                "take_profit": "目标位：XX元（前高/整数关口）"
            },
            "position_strategy": {
                "suggested_position": "建议仓位：X成",
                "entry_plan": "分批建仓策略描述",
                "risk_control": "风控策略描述"
            },
            "action_checklist": [
                "✅/⚠️/❌ 检查项1：多头排列 (MA5>MA10>MA20)",
                "✅/⚠️/❌ 检查项2：乖离率<5%（当前X%）",
                "✅/⚠️/❌ 检查项3：量能配合（量比X）",
                "✅/⚠️/❌ 检查项4：无重大利空（结合消息面）",
                "✅/⚠️/❌ 检查项5：筹码健康（获利比例X%）",
                "✅/⚠️/❌ 检查项6：MACD 多头（DIF/DEA状态）",
                "✅/⚠️/❌ 检查项7：RSI 安全区（当前X）",
                "✅/⚠️/❌ 检查项8：BOLL 突破信号",
                "✅/⚠️/❌ 检查项9：KDJ 买入信号",
                "✅/⚠️/❌ 检查项10：ATR 风险可控（波动率X%）"
            ]
        }
    },

    "analysis_summary": "100字综合分析摘要",
    "key_points": "3-5个核心看点，逗号分隔",
    "risk_warning": "风险提示",
    "buy_reason": "操作理由，引用交易理念",

    "trend_analysis": "走势形态分析",
    "short_term_outlook": "短期1-3日展望",
    "medium_term_outlook": "中期1-2周展望",
    "technical_analysis": "技术面综合分析",
    "ma_analysis": "均线系统分析",
    "volume_analysis": "量能分析",
    "pattern_analysis": "K线形态分析",
    "fundamental_analysis": "基本面分析",
    "sector_position": "板块行业分析",
    "company_highlights": "公司亮点/风险",
    "news_summary": "新闻摘要",
    "market_sentiment": "市场情绪",
    "hot_topics": "相关热点",

    "search_performed": true/false,
    "data_sources": "数据来源说明"
}
```

## 评分标准

### 强烈买入（80-100分）：
- ✅ 多头排列：MA5 > MA10 > MA20
- ✅ 低乖离率：<2%，最佳买点
- ✅ 缩量回调或放量突破
- ✅ 筹码集中健康
- ✅ 消息面有利好催化

### 买入（60-79分）：
- ✅ 多头排列或弱势多头
- ✅ 乖离率 <5%
- ✅ 量能正常
- ⚪ 允许一项次要条件不满足

### 观望（40-59分）：
- ⚠️ 乖离率 >5%（追高风险）
- ⚠️ 均线缠绕趋势不明
- ⚠️ 有风险事件

### 卖出/减仓（0-39分）：
- ❌ 空头排列
- ❌ 跌破MA20
- ❌ 放量下跌
- ❌ 重大利空

## 决策仪表盘核心原则

1. **核心结论先行**：一句话说清该买该卖
2. **分持仓建议**：空仓者和持仓者给不同建议
3. **精确狙击点**：必须给出具体价格，不说模糊的话
4. **检查清单可视化**：用 ✅⚠️❌ 明确显示每项检查结果
5. **风险优先级**：舆情中的风险点要醒目标出"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 AI 分析器（OpenAI 兼容 API）

        Args:
            api_key: 已废弃，保留参数兼容性，实际从配置读取 OpenAI API Key
        """
        self._model = None
        self._current_model_name = None  # 当前使用的模型名称
        self._use_openai = False  # 是否使用 OpenAI 兼容 API
        self._openai_client = None  # OpenAI 客户端

        self._init_openai()

        if not self._openai_client:
            logger.warning("未配置 OpenAI API Key，AI 分析功能将不可用")

    def _init_openai(self) -> None:
        """
        初始化 OpenAI 兼容 API

        支持所有 OpenAI 格式的 API，包括：
        - OpenAI 官方
        - DeepSeek
        - 通义千问
        - Moonshot 等
        """
        config = get_config()

        # 检查 OpenAI API Key 是否有效（过滤占位符）
        openai_key_valid = (
            config.openai_api_key and
            not config.openai_api_key.startswith('your_') and
            len(config.openai_api_key) > 10
        )

        if not openai_key_valid:
            logger.debug("OpenAI 兼容 API 未配置或配置无效")
            return

        # 分离 import 和客户端创建，以便提供更准确的错误信息
        try:
            from openai import OpenAI
        except ImportError:
            logger.error("未安装 openai 库，请运行: pip install openai")
            return

        try:
            # base_url 可选，不填则使用 OpenAI 官方默认地址
            client_kwargs = {"api_key": config.openai_api_key}
            if config.openai_base_url and config.openai_base_url.startswith('http'):
                client_kwargs["base_url"] = config.openai_base_url

            self._openai_client = OpenAI(**client_kwargs)
            self._current_model_name = config.openai_model
            self._use_openai = True
            logger.info(f"OpenAI 兼容 API 初始化成功 (base_url: {config.openai_base_url}, model: {config.openai_model})")
        except ImportError as e:
            # 依赖缺失（如 socksio）
            if 'socksio' in str(e).lower() or 'socks' in str(e).lower():
                logger.error(f"OpenAI 客户端需要 SOCKS 代理支持，请运行: pip install httpx[socks] 或 pip install socksio")
            else:
                logger.error(f"OpenAI 依赖缺失: {e}")
        except Exception as e:
            error_msg = str(e).lower()
            if 'socks' in error_msg or 'socksio' in error_msg or 'proxy' in error_msg:
                logger.error(f"OpenAI 代理配置错误: {e}，如使用 SOCKS 代理请运行: pip install httpx[socks]")
            else:
                logger.error(f"OpenAI 兼容 API 初始化失败: {e}")

    def is_available(self) -> bool:
        """检查分析器是否可用"""
        return self._openai_client is not None

    def _call_openai_api(self, prompt: str, generation_config: dict) -> str:
        """
        调用 OpenAI 兼容 API

        Args:
            prompt: 提示词
            generation_config: 生成配置

        Returns:
            响应文本
        """
        config = get_config()
        max_retries = config.ai_max_retries
        base_delay = config.ai_retry_delay

        def _build_base_request_kwargs() -> dict:
            kwargs = {
                "model": self._current_model_name,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": generation_config.get('temperature', config.openai_temperature),
            }
            return kwargs

        def _is_unsupported_param_error(error_message: str, param_name: str) -> bool:
            lower_msg = error_message.lower()
            return ('400' in lower_msg or "unsupported parameter" in lower_msg or "unsupported param" in lower_msg) and param_name in lower_msg

        if not hasattr(self, "_token_param_mode"):
            self._token_param_mode = {}

        max_output_tokens = generation_config.get('max_output_tokens', 8192)
        model_name = self._current_model_name
        mode = self._token_param_mode.get(model_name, "max_tokens")

        def _kwargs_with_mode(mode_value):
            kwargs = _build_base_request_kwargs()
            if mode_value is not None:
                kwargs[mode_value] = max_output_tokens
            return kwargs

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(f"[OpenAI] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    time.sleep(delay)

                try:
                    response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                except Exception as e:
                    error_str = str(e)
                    if mode == "max_tokens" and _is_unsupported_param_error(error_str, "max_tokens"):
                        mode = "max_completion_tokens"
                        self._token_param_mode[model_name] = mode
                        response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                    elif mode == "max_completion_tokens" and _is_unsupported_param_error(error_str, "max_completion_tokens"):
                        mode = None
                        self._token_param_mode[model_name] = mode
                        response = self._openai_client.chat.completions.create(**_kwargs_with_mode(mode))
                    else:
                        raise

                if response and response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                else:
                    raise ValueError("OpenAI API 返回空响应")
                    
            except Exception as e:
                error_str = str(e)
                is_rate_limit = '429' in error_str or 'rate' in error_str.lower() or 'quota' in error_str.lower()
                
                if is_rate_limit:
                    logger.warning(f"[OpenAI] API 限流，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")
                else:
                    logger.warning(f"[OpenAI] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")
                
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("OpenAI API 调用失败，已达最大重试次数")
    
    def _call_api_with_retry(self, prompt: str, generation_config: dict) -> str:
        """
        调用 AI API，带有重试机制

        Args:
            prompt: 提示词
            generation_config: 生成配置

        Returns:
            响应文本
        """
        return self._call_openai_api(prompt, generation_config)
    
    def analyze(
        self, 
        context: Dict[str, Any],
        news_context: Optional[str] = None
    ) -> AnalysisResult:
        """
        分析单只股票
        
        流程：
        1. 格式化输入数据（技术面 + 新闻）
        2. 调用 Gemini API（带重试和模型切换）
        3. 解析 JSON 响应
        4. 返回结构化结果
        
        Args:
            context: 从 storage.get_analysis_context() 获取的上下文数据
            news_context: 预先搜索的新闻内容（可选）
            
        Returns:
            AnalysisResult 对象
        """
        code = context.get('code', 'Unknown')
        config = get_config()
        
        # 请求前增加延时（防止连续请求触发限流）
        request_delay = config.ai_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM] 请求前等待 {request_delay:.1f} 秒...")
            time.sleep(request_delay)
        
        # 优先从上下文获取股票名称（由 main.py 传入）
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            # 备选：从 realtime 中获取
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                # 最后从映射表获取
                name = STOCK_NAME_MAP.get(code, f'股票{code}')
        
        # 如果模型不可用，返回默认结果
        if not self.is_available():
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary='AI 分析功能未启用（未配置 API Key）',
                risk_warning='请配置 OpenAI API Key 后重试',
                success=False,
                error_message='OpenAI API Key 未配置',
            )
        
        try:
            # 格式化输入（包含技术面数据和新闻）
            prompt = self._format_prompt(context, name, news_context)
            
            # 获取模型名称
            model_name = getattr(self, '_current_model_name', None)
            if not model_name:
                model_name = getattr(self._model, '_model_name', 'unknown')
                if hasattr(self._model, 'model_name'):
                    model_name = self._model.model_name
            
            logger.info(f"========== AI 分析 {name}({code}) ==========")
            logger.info(f"[LLM配置] 模型: {model_name}")
            logger.info(f"[LLM配置] Prompt 长度: {len(prompt)} 字符")
            logger.info(f"[LLM配置] 是否包含新闻: {'是' if news_context else '否'}")
            
            # 记录完整 prompt 到日志（INFO级别记录摘要，DEBUG记录完整）
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            logger.info(f"[LLM Prompt 预览]\n{prompt_preview}")
            logger.debug(f"=== 完整 Prompt ({len(prompt)}字符) ===\n{prompt}\n=== End Prompt ===")

            # 设置生成配置（从配置文件读取温度参数）
            config = get_config()
            generation_config = {
                "temperature": config.openai_temperature,
                "max_output_tokens": 8192,
            }

            logger.info("[LLM调用] 开始调用 OpenAI API...")
            
            # 使用带重试的 API 调用
            start_time = time.time()
            response_text = self._call_api_with_retry(prompt, generation_config)
            elapsed = time.time() - start_time

            # 记录响应信息
            logger.info(f"[LLM返回] OpenAI API 响应成功, 耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符")
            
            # 记录响应预览（INFO级别）和完整响应（DEBUG级别）
            response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
            logger.info(f"[LLM返回 预览]\n{response_preview}")
            logger.debug(f"=== OpenAI 完整响应 ({len(response_text)}字符) ===\n{response_text}\n=== End Response ===")
            
            # 解析响应
            result = self._parse_response(response_text, code, name)
            result.raw_response = response_text
            result.search_performed = bool(news_context)
            result.market_snapshot = self._build_market_snapshot(context)

            logger.info(f"[LLM解析] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")
            
            return result
            
        except Exception as e:
            logger.error(f"AI 分析 {name}({code}) 失败: {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary=f'分析过程出错: {str(e)[:100]}',
                risk_warning='分析失败，请稍后重试或手动分析',
                success=False,
                error_message=str(e),
            )
    
    def _format_prompt(
        self, 
        context: Dict[str, Any], 
        name: str,
        news_context: Optional[str] = None
    ) -> str:
        """
        格式化分析提示词（决策仪表盘 v2.0）
        
        包含：技术指标、实时行情（量比/换手率）、筹码分布、趋势分析、新闻
        
        Args:
            context: 技术面数据上下文（包含增强数据）
            name: 股票名称（默认值，可能被上下文覆盖）
            news_context: 预先搜索的新闻内容
        """
        code = context.get('code', 'Unknown')
        
        # 优先使用上下文中的股票名称（从 realtime_quote 获取）
        stock_name = context.get('stock_name', name)
        if not stock_name or stock_name == f'股票{code}':
            stock_name = STOCK_NAME_MAP.get(code, f'股票{code}')
            
        today = context.get('today', {})
        
        # ========== 构建紧凑格式的输入 ==========
        prompt = f"""# {stock_name}({code}) 决策分析 | {context.get('date', '未知')}

## 行情数据
收盘={today.get('close', 'N/A')} 开盘={today.get('open', 'N/A')} 最高={today.get('high', 'N/A')} 最低={today.get('low', 'N/A')} 涨跌幅={today.get('pct_chg', 'N/A')}%
成交量={self._format_volume(today.get('volume'))} 成交额={self._format_amount(today.get('amount'))}
MA5={today.get('ma5', 'N/A')} MA10={today.get('ma10', 'N/A')} MA20={today.get('ma20', 'N/A')} MA60={today.get('ma60', 'N/A')} 均线形态={context.get('ma_status', '未知')}
"""
        
        # 添加实时行情数据
        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""
## 实时增强
现价={rt.get('price', 'N/A')} 量比={rt.get('volume_ratio', 'N/A')}({rt.get('volume_ratio_desc', '')}) 换手率={rt.get('turnover_rate', 'N/A')}%
PE={rt.get('pe_ratio', 'N/A')} PB={rt.get('pb_ratio', 'N/A')} 总市值={self._format_amount(rt.get('total_mv'))} 流通市值={self._format_amount(rt.get('circ_mv'))}
60日涨跌幅={rt.get('change_60d', 'N/A')}%
"""
        
        # 添加筹码分布数据
        if 'chip' in context:
            chip = context['chip']
            profit_ratio = chip.get('profit_ratio', 0)
            prompt += f"""
## 筹码分布
获利比例={profit_ratio:.1%}(70-90%警惕) 平均成本={chip.get('avg_cost', 'N/A')}元 90%集中度={chip.get('concentration_90', 0):.2%} 70%集中度={chip.get('concentration_70', 0):.2%} 状态={chip.get('chip_status', '未知')}
"""
        
        # 添加趋势分析结果
        if 'trend_analysis' in context:
            trend = context['trend_analysis']
            bias_warning = "🚨严禁追高" if trend.get('bias_ma5', 0) > 5 else ""
            prompt += f"""
## 趋势预判
趋势={trend.get('trend_status', '未知')} 排列={trend.get('ma_alignment', '未知')} 强度={trend.get('trend_strength', 0)}/100
乖离率: MA5={trend.get('bias_ma5', 0):+.2f}%{bias_warning} MA10={trend.get('bias_ma10', 0):+.2f}% MA20={trend.get('bias_ma20', 0):+.2f}%
Bias: 6日={trend.get('bias_6', 0):+.2f}% 12日={trend.get('bias_12', 0):+.2f}% 24日={trend.get('bias_24', 0):+.2f}%
量能={trend.get('volume_status', '未知')}({trend.get('volume_trend', '')}) 5日量比={trend.get('volume_ratio_5d', 0):.2f}
系统信号={trend.get('buy_signal', '未知')} 评分={trend.get('signal_score', 0)}/100
支撑: MA5={trend.get('support_ma5', 'N/A')}元 MA10={trend.get('support_ma10', 'N/A')}元

## 技术指标
MACD: DIF={trend.get('macd_dif', 0):.4f} DEA={trend.get('macd_dea', 0):.4f} 柱={trend.get('macd_bar', 0):.4f} 状态={trend.get('macd_status', '未知')} 信号={trend.get('macd_signal', '未知')}
RSI: 6日={trend.get('rsi_6', 0):.1f} 12日={trend.get('rsi_12', 0):.1f} 24日={trend.get('rsi_24', 0):.1f} 状态={trend.get('rsi_status', '未知')} {trend.get('rsi_signal', '')}
"""
            
            # 添加新指标（BOLL/KDJ/ATR）
            if trend.get('boll_upper', 0) > 0:
                prompt += f"BOLL: 上轨={trend.get('boll_upper', 0):.2f} 中轨={trend.get('boll_middle', 0):.2f} 下轨={trend.get('boll_lower', 0):.2f} 位置={trend.get('boll_position', 0):.1f}% 带宽={trend.get('boll_bandwidth', 0):.2f}% 状态={trend.get('boll_status', '未知')} 信号={trend.get('boll_signal', '未知')}\n"

            if trend.get('kdj_k', 0) > 0:
                prompt += f"KDJ: K={trend.get('kdj_k', 0):.1f} D={trend.get('kdj_d', 0):.1f} J={trend.get('kdj_j', 0):.1f} 状态={trend.get('kdj_status', '未知')} 买入强度={trend.get('kdj_buy_strength', 0)}/5 卖出强度={trend.get('kdj_sell_strength', 0)}/5 信号={trend.get('kdj_signal', '未知')}\n"

            if trend.get('atr', 0) > 0:
                prompt += f"ATR: {trend.get('atr', 0):.2f}元(占股价{trend.get('atr_pct', 0):.2f}%) 波动={trend.get('atr_level', '未知')} 止损={trend.get('atr_stop_loss', 0):.2f} 止盈={trend.get('atr_take_profit', 0):.2f} 信号={trend.get('atr_signal', '未知')}\n"
            
            reasons = trend.get('signal_reasons', [])
            risk_factors = trend.get('risk_factors', [])
            if reasons:
                prompt += f"买入理由: {'; '.join(reasons)}\n"
            if risk_factors:
                prompt += f"风险因素: {'; '.join(risk_factors)}\n"
        
        # 添加昨日对比数据
        if 'yesterday' in context:
            prompt += f"较昨日: 量变={context.get('volume_change_ratio', 'N/A')}倍 价变={context.get('price_change_ratio', 'N/A')}%\n"
        
        # 添加系统预计算的检查清单
        if 'pre_checklist' in context:
            checklist = context['pre_checklist']
            prompt += "\n## 系统预判检查清单（请逐项确认或修正，输出到 action_checklist）\n"
            for item in checklist:
                prompt += f"- {item['status']} {item['name']}: {item['detail']}\n"
            prompt += "> 在 action_checklist 中逐项输出全部 10 项修正后判定，有误请说明修正原因。\n"

        # 添加所属板块信息
        if 'belong_board' in context:
            boards = context['belong_board']
            prompt += f"\n所属板块: {' | '.join(boards)}\n"

        # 注入上次分析结论（保持连贯性）
        if 'prev_analysis' in context:
            prev = context['prev_analysis']
            prompt += f"""
## 上次分析结论（{prev.get('date', '未知')}）
评分={prev.get('score', 'N/A')} 趋势={prev.get('trend', 'N/A')} 建议={prev.get('advice', 'N/A')}
摘要: {prev.get('summary', '无')}
> 请对比上次结论，说明观点是否变化及原因。如维持则简要确认，如调整请明确说明变化依据。
"""

        # 添加新闻搜索结果
        if news_context:
            prompt += f"\n## 舆情情报(重点提取:风险警报/利好催化/业绩预期)\n{news_context}\n"
        else:
            prompt += "\n无近期新闻，主要依据技术面分析。\n"

        # 注入缺失数据警告
        if context.get('data_missing'):
            prompt += "\n⚠️ 数据缺失：忽略N/A数据，重点依据舆情分析。技术面无数据时回答\"数据缺失\"，严禁编造。\n"

        # 明确的输出要求
        prompt += f"""
---
## 分析任务

为 **{stock_name}({code})** 生成决策仪表盘 JSON。如名称不正确请修正。

### 必须回答的关键问题：
1. 均线是否多头排列？乖离率是否<5%（超过标注严禁追高）？
2. 量价配合如何？量比/换手率是否异常？有无量价背离？
3. MACD/RSI/BOLL/KDJ/ATR 各指标状态和信号？
4. 筹码结构健康否？估值水平？
5. 消息面有无利空/利好催化？
6. 风险收益比？具体进场/止损/止盈点位？空仓者和持仓者各自策略？

### JSON 输出要求：
- stock_name: 正确中文全称
- sentiment_score: 0-100
- trend_prediction: 强烈看多/看多/震荡/看空/强烈看空
- operation_advice: 买入/加仓/持有/减仓/卖出/观望
- decision_type: buy/hold/sell
- confidence_level: 高/中/低
- dashboard: {{core_conclusion(one_sentence/signal_type/position_advice), data_perspective, sniper_points(ideal_buy/secondary_buy/stop_loss/take_profit/position_size), action_checklist(10项,✅/⚠️/❌)}}
- technical_analysis: 包含趋势/MACD/RSI/BOLL/KDJ/ATR/量价/乖离率/支撑压力/风险的完整分析
- trend_analysis/news_summary/analysis_summary/risk_warning/buy_reason 等文本字段

**规则**：数值从数据精确提取严禁编造；action_checklist 必须输出全部10项；分析客观可操作。

请输出完整 JSON。"""
        
        return prompt
    
    def _format_volume(self, volume: Optional[float]) -> str:
        """格式化成交量显示"""
        if volume is None:
            return 'N/A'
        if volume >= 1e8:
            return f"{volume / 1e8:.2f} 亿股"
        elif volume >= 1e4:
            return f"{volume / 1e4:.2f} 万股"
        else:
            return f"{volume:.0f} 股"
    
    def _format_amount(self, amount: Optional[float]) -> str:
        """格式化成交额显示"""
        if amount is None:
            return 'N/A'
        if amount >= 1e8:
            return f"{amount / 1e8:.2f} 亿元"
        elif amount >= 1e4:
            return f"{amount / 1e4:.2f} 万元"
        else:
            return f"{amount:.0f} 元"

    def _format_percent(self, value: Optional[float]) -> str:
        """格式化百分比显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return 'N/A'

    def _format_price(self, value: Optional[float]) -> str:
        """格式化价格显示"""
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return 'N/A'

    def _build_market_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建当日行情快照（展示用）"""
        today = context.get('today', {}) or {}
        realtime = context.get('realtime', {}) or {}
        yesterday = context.get('yesterday', {}) or {}

        prev_close = yesterday.get('close')
        close = today.get('close')
        high = today.get('high')
        low = today.get('low')

        amplitude = None
        change_amount = None
        if prev_close not in (None, 0) and high is not None and low is not None:
            try:
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
            except (TypeError, ValueError, ZeroDivisionError):
                amplitude = None
        if prev_close is not None and close is not None:
            try:
                change_amount = float(close) - float(prev_close)
            except (TypeError, ValueError):
                change_amount = None

        snapshot = {
            "date": context.get('date', '未知'),
            "close": self._format_price(close),
            "open": self._format_price(today.get('open')),
            "high": self._format_price(high),
            "low": self._format_price(low),
            "prev_close": self._format_price(prev_close),
            "pct_chg": self._format_percent(today.get('pct_chg')),
            "change_amount": self._format_price(change_amount),
            "amplitude": self._format_percent(amplitude),
            "volume": self._format_volume(today.get('volume')),
            "amount": self._format_amount(today.get('amount')),
        }

        if realtime:
            snapshot.update({
                "price": self._format_price(realtime.get('price')),
                "volume_ratio": realtime.get('volume_ratio', 'N/A'),
                "turnover_rate": self._format_percent(realtime.get('turnover_rate')),
                "source": getattr(realtime.get('source'), 'value', realtime.get('source', 'N/A')),
            })

        return snapshot

    def _parse_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """
        解析 Gemini 响应（决策仪表盘版）
        
        尝试从响应中提取 JSON 格式的分析结果，包含 dashboard 字段
        如果解析失败，尝试智能提取或返回默认结果
        """
        try:
            # 清理响应文本：移除 markdown 代码块标记
            cleaned_text = response_text
            if '```json' in cleaned_text:
                cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
            elif '```' in cleaned_text:
                cleaned_text = cleaned_text.replace('```', '')
            
            # 尝试找到 JSON 内容
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]
                
                # 尝试修复常见的 JSON 问题
                json_str = self._fix_json_string(json_str)
                
                data = json.loads(json_str)

                # === 关键字段验证 ===
                critical_fields = ['sentiment_score', 'trend_prediction', 'operation_advice']
                important_fields = ['dashboard', 'technical_analysis', 'analysis_summary', 'confidence_level']

                missing_critical = [f for f in critical_fields if f not in data]
                missing_important = [f for f in important_fields if f not in data]

                if missing_critical:
                    logger.warning(f"[{code}] AI返回缺失关键字段: {missing_critical}，使用默认值（评分可能不准确）")
                if missing_important:
                    logger.info(f"[{code}] AI返回缺失字段: {missing_important}")

                # 验证 sentiment_score 范围
                raw_score = data.get('sentiment_score', 50)
                try:
                    score_val = int(raw_score)
                    if not (0 <= score_val <= 100):
                        logger.warning(f"[{code}] sentiment_score={raw_score} 超出范围，裁剪到 0-100")
                        score_val = max(0, min(100, score_val))
                        data['sentiment_score'] = score_val
                except (TypeError, ValueError):
                    logger.warning(f"[{code}] sentiment_score={raw_score} 无法解析，使用默认值50")
                    data['sentiment_score'] = 50

                # 验证 dashboard.action_checklist 是否完整
                dashboard_data = data.get('dashboard', {})
                if dashboard_data:
                    checklist = dashboard_data.get('action_checklist', [])
                    if isinstance(checklist, list) and len(checklist) < 10:
                        logger.warning(f"[{code}] action_checklist 仅 {len(checklist)} 项（预期10项）")

                # 提取 dashboard 数据
                dashboard = data.get('dashboard', None)

                # 优先使用 AI 返回的股票名称（如果原名称无效或包含代码）
                ai_stock_name = data.get('stock_name')
                if ai_stock_name and (name.startswith('股票') or name == code or 'Unknown' in name):
                    name = ai_stock_name

                # 解析 decision_type，如果没有则根据 operation_advice 推断
                decision_type = data.get('decision_type', '')
                if not decision_type:
                    op = data.get('operation_advice', '持有')
                    if op in ['买入', '加仓', '强烈买入']:
                        decision_type = 'buy'
                    elif op in ['卖出', '减仓', '强烈卖出']:
                        decision_type = 'sell'
                    else:
                        decision_type = 'hold'
                
                return AnalysisResult(
                    code=code,
                    name=name,
                    # 核心指标
                    sentiment_score=int(data.get('sentiment_score', 50)),
                    trend_prediction=data.get('trend_prediction', '震荡'),
                    operation_advice=data.get('operation_advice', '持有'),
                    decision_type=decision_type,
                    confidence_level=data.get('confidence_level', '中'),
                    # 决策仪表盘
                    dashboard=dashboard,
                    # 走势分析
                    trend_analysis=data.get('trend_analysis', ''),
                    short_term_outlook=data.get('short_term_outlook', ''),
                    medium_term_outlook=data.get('medium_term_outlook', ''),
                    # 技术面
                    technical_analysis=data.get('technical_analysis', ''),
                    ma_analysis=data.get('ma_analysis', ''),
                    volume_analysis=data.get('volume_analysis', ''),
                    pattern_analysis=data.get('pattern_analysis', ''),
                    # 基本面
                    fundamental_analysis=data.get('fundamental_analysis', ''),
                    sector_position=data.get('sector_position', ''),
                    company_highlights=data.get('company_highlights', ''),
                    # 情绪面/消息面
                    news_summary=data.get('news_summary', ''),
                    market_sentiment=data.get('market_sentiment', ''),
                    hot_topics=data.get('hot_topics', ''),
                    # 综合
                    analysis_summary=data.get('analysis_summary', '分析完成'),
                    key_points=data.get('key_points', ''),
                    risk_warning=data.get('risk_warning', ''),
                    buy_reason=data.get('buy_reason', ''),
                    # 元数据
                    search_performed=data.get('search_performed', False),
                    data_sources=data.get('data_sources', '技术面数据'),
                    success=True,
                )
            else:
                # 没有找到 JSON，尝试从纯文本中提取信息
                logger.warning(f"无法从响应中提取 JSON，使用原始文本分析")
                return self._parse_text_response(response_text, code, name)
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}，尝试从文本提取")
            return self._parse_text_response(response_text, code, name)
    
    def _fix_json_string(self, json_str: str) -> str:
        """修复常见的 JSON 格式问题"""
        import re
        
        # 移除注释
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 修复尾随逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 确保布尔值是小写
        json_str = json_str.replace('True', 'true').replace('False', 'false')
        
        # fix by json-repair
        json_str = repair_json(json_str)
        
        return json_str
    
    def _parse_text_response(
        self, 
        response_text: str, 
        code: str, 
        name: str
    ) -> AnalysisResult:
        """从纯文本响应中尽可能提取分析信息"""
        # 尝试识别关键词来判断情绪
        sentiment_score = 50
        trend = '震荡'
        advice = '持有'
        
        text_lower = response_text.lower()
        
        # 简单的情绪识别
        positive_keywords = ['看多', '买入', '上涨', '突破', '强势', '利好', '加仓', 'bullish', 'buy']
        negative_keywords = ['看空', '卖出', '下跌', '跌破', '弱势', '利空', '减仓', 'bearish', 'sell']
        
        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)
        
        if positive_count > negative_count + 1:
            sentiment_score = 65
            trend = '看多'
            advice = '买入'
            decision_type = 'buy'
        elif negative_count > positive_count + 1:
            sentiment_score = 35
            trend = '看空'
            advice = '卖出'
            decision_type = 'sell'
        else:
            decision_type = 'hold'
        
        # 截取前500字符作为摘要
        summary = response_text[:500] if response_text else '无分析结果'
        
        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=sentiment_score,
            trend_prediction=trend,
            operation_advice=advice,
            decision_type=decision_type,
            confidence_level='低',
            analysis_summary=summary,
            key_points='JSON解析失败，仅供参考',
            risk_warning='分析结果可能不准确，建议结合其他信息判断',
            raw_response=response_text,
            success=True,
        )
    
    def batch_analyze(
        self, 
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0
    ) -> List[AnalysisResult]:
        """
        批量分析多只股票
        
        注意：为避免 API 速率限制，每次分析之间会有延迟
        
        Args:
            contexts: 上下文数据列表
            delay_between: 每次分析之间的延迟（秒）
            
        Returns:
            AnalysisResult 列表
        """
        results = []
        
        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug(f"等待 {delay_between} 秒后继续...")
                time.sleep(delay_between)
            
            result = self.analyze(context)
            results.append(result)
        
        return results


# 便捷函数
def get_analyzer() -> AIAnalyzer:
    """获取 Gemini 分析器实例"""
    return AIAnalyzer()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟上下文数据
    test_context = {
        'code': '600519',
        'date': '2026-01-09',
        'today': {
            'open': 1800.0,
            'high': 1850.0,
            'low': 1780.0,
            'close': 1820.0,
            'volume': 10000000,
            'amount': 18200000000,
            'pct_chg': 1.5,
            'ma5': 1810.0,
            'ma10': 1800.0,
            'ma20': 1790.0,
            'volume_ratio': 1.2,
        },
        'ma_status': '多头排列 📈',
        'volume_change_ratio': 1.3,
        'price_change_ratio': 1.5,
    }
    
    analyzer = AIAnalyzer()
    
    if analyzer.is_available():
        print("=== AI 分析测试 ===")
        result = analyzer.analyze(test_context)
        print(f"分析结果: {result.to_dict()}")
    else:
        print("AI API 未配置，跳过测试")

# 向后兼容别名
GeminiAnalyzer = AIAnalyzer
