# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析层
===================================

职责：
1. 封装 Gemini API 调用逻辑
2. 利用 Google Search Grounding 获取实时新闻
3. 结合技术面和消息面生成分析报告
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


class GeminiAnalyzer:
    """
    Gemini AI 分析器

    职责：
    1. 调用 Google Gemini API 进行股票分析
    2. 结合预先搜索的新闻和技术面数据生成分析报告
    3. 解析 AI 返回的 JSON 格式结果

    使用方式：
        analyzer = GeminiAnalyzer()
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
- **标准多头排列**：必须严格满足 MA5 > MA10 > MA20（三条均线依次从上到下排列）
- **弱势多头**（MA5>MA10 但 MA10≤MA20）：这不是真正的多头排列！`is_bullish` 必须为 `false`
- **均线缠绕**（如 MA20>MA5>MA10 或各均线交叉纠缠）：属于震荡格局，不能标注为多头
- 只做标准多头排列的股票，弱势多头最多给"持有/小仓位"
- 均线发散上行优于均线粘合
- 趋势强度判断：看均线间距是否在扩大

### 3. 效率优先（筹码结构）
- 关注筹码集中度：90%集中度 < 15% 表示筹码集中
- 获利比例分析：70-90% 获利盘时需警惕获利回吐
- **套牢盘分析**：当获利比例 < 50%，说明超半数持仓套牢，上方解套抛压极重，必须在分析中明确体现，下调目标位
- 平均成本与现价关系：现价高于平均成本 5-15% 为健康；现价低于平均成本说明多数人亏损，上涨阻力大

### 4. 买点偏好（回踩支撑）
- **最佳买点**：缩量回踩 MA5 获得支撑
- **次优买点**：回踩 MA10 获得支撑
- **观望情况**：跌破 MA20 时观望
- **关键约束**：买入点必须 > 止损触发价（如MA20），否则买入即触发止损，逻辑自相矛盾

### 5. 风险排查重点
- 减持公告（股东、高管减持）
- 业绩预亏/大幅下滑（需区分扣非净利润和归母净利润，分析非经常性损益影响）
- 监管处罚/立案调查
- 行业政策利空
- 大额解禁

## ⚠️ 信号冲突处理规则（必须严格执行）

以下规则用于处理技术指标之间的信号冲突，必须遵守：

### 规则A：超买环境下禁止给出买入建议
- 如果 KDJ 的 J 值 > 100（极度超买），且均线不是标准多头排列（MA5>MA10>MA20），则：
  - `operation_advice` 最多为"持有"或"观望"，**绝不能是"买入"**
  - `signal_type` 不能为"🟢买入信号"
- 如果 RSI 超买 + KDJ 超买（双重超买），无论其他条件如何：
  - `operation_advice` 必须为"观望"或"减仓"

### 规则B：均线非多头排列时的限制
- 如果均线不满足 MA5>MA10>MA20（标准多头），则：
  - `is_bullish` 必须为 `false`
  - 检查清单"多头排列"项必须标注 ⚠️ 或 ❌（不能是 ✅）
  - `operation_advice` 最多为"持有"，不能给"买入"或"加仓"

### 规则C：买入点与止损位一致性检查
- 理想买入点（如MA5附近）必须 > 风控减仓线（如MA20）
- 如果 MA5 < MA20（均线非多头），则不能把 MA5 设为理想买入点
- 止损位必须只设一个明确价格，不能出现两个矛盾的止损标准

### 规则D：量能解读必须结合多空背景
- 缩量回调 + 标准多头排列（MA5>MA10>MA20）→ 可正面解读为"洗盘"
- 缩量回调 + 超买信号/均线缠绕/非标准多头 → 必须解读为"买盘不足、多头接力乏力"
- **"洗盘"的前提是存在明确的上涨趋势（标准多头排列），无趋势则不存在洗盘**
- 不允许脱离技术背景单独做正面解读

### 规则E：基本面重大风险优先级
- 当出现以下基本面风险时，技术面的微弱优势不能作为看多依据：
  - 最近一季度净利润同比大幅下滑（>30%）
  - 业绩预亏
  - 重大减持/立案调查
- 此时 `operation_advice` 最多为"观望"，并在风险警报中醒目标出
- **业绩暴增需甄别低基数效应**：若上年同期因大额减值/非经常损益导致基数极低，当期增长不代表主营业务爆发，需对比营收增速验证
- **业绩下滑需区分幅度和持续性**：季度净利润同比下滑>50%属于"业绩腰斩"，必须作为核心风险而非次要风险

### 规则F：严禁编造未提供的技术指标
- 只能使用输入数据中提供的技术指标（MA、MACD、RSI、KDJ、乖离率等）
- 如果输入中没有某个指标的数据，不能自行计算或编造数值
- 布林带(BOLL)等指标，如果输入中未提供，在检查清单中不要出现

### 规则G：严禁确认偏差（先有结论再找论据）
- **分析流程必须是：客观罗列所有信号 → 评估多空力量对比 → 得出结论**
- 禁止先预设"买入/看多"结论，再选择性挑选有利指标
- 当多空信号冲突时（如MACD金叉但KDJ超买），必须在结论中体现冲突和不确定性
- 利空信号（超买、均线缠绕、业绩下滑、套牢盘压力）的权重不得低于利多信号
- 盈亏比检查：潜在盈利/潜在亏损 < 2:1 时，不应给出买入建议

### 规则H：支撑位/压力位识别规则
- 支撑位应选择最近的**有效**支撑均线，优先级：MA20（中期趋势线）> MA10 > MA5
- 当 MA5 < MA20 时，MA20 才是更有效的支撑位，不应把更低的 MA5 标为核心支撑
- 压力位需考虑上方套牢盘密集区（筹码平均成本附近），获利比例<50%时平均成本即为强压力位
- 目标位不应设在套牢密集区之上（除非有重大利好催化突破）

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
                "ma_alignment": "均线排列状态描述（如实描述，非标准多头必须明确说明）",
                "is_bullish": "true仅当严格满足MA5>MA10>MA20时，否则必须为false",
                "trend_score": 0-100
            },
            "price_position": {
                "current_price": "当前价格数值",
                "ma5": "MA5数值",
                "ma10": "MA10数值",
                "ma20": "MA20数值",
                "bias_ma5": "乖离率百分比数值",
                "bias_status": "安全/警戒/危险",
                "support_level": "支撑位价格（选择有效支撑位：在多头排列下取MA5，否则取最近有效均线）",
                "resistance_level": "压力位价格"
            },
            "volume_analysis": {
                "volume_ratio": "量比数值",
                "volume_status": "放量/缩量/平量",
                "turnover_rate": "换手率百分比",
                "volume_meaning": "量能含义解读（必须结合趋势背景，参考规则D）"
            },
            "chip_structure": {
                "profit_ratio": "获利比例",
                "avg_cost": "平均成本",
                "concentration": "筹码集中度",
                "chip_health": "健康/一般/警惕",
                "trap_pressure": "套牢盘压力描述（获利比例<50%时必须说明上方抛压情况）"
            }
        },

        "intelligence": {
            "latest_news": "【最新消息】近期重要新闻摘要",
            "risk_alerts": ["风险点1：具体描述", "风险点2：具体描述"],
            "positive_catalysts": ["利好1：具体描述", "利好2：具体描述"],
            "earnings_outlook": "业绩预期分析（需区分扣非净利润与归母净利润，分析低基数效应和非经常性损益）",
            "sentiment_summary": "舆情情绪一句话总结"
        },

        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "理想买入点：XX元（必须>止损位，且在有效支撑附近）",
                "secondary_buy": "次优买入点：XX元（在MA10附近）",
                "stop_loss": "止损位：XX元（唯一明确价格，基于ATR或关键均线）",
                "take_profit": "目标位：XX元（需考虑上方套牢盘压力）"
            },
            "position_strategy": {
                "suggested_position": "建议仓位：X成",
                "entry_plan": "分批建仓策略描述",
                "risk_control": "风控策略描述（止损位只设一个，不能自相矛盾）"
            },
            "action_checklist": [
                "✅/⚠️/❌ 检查项1：多头排列（✅仅当MA5>MA10>MA20；⚠️弱势多头MA5>MA10但MA10≤MA20；❌其他）",
                "✅/⚠️/❌ 检查项2：乖离率<5%（✅<2%；⚠️2-5%；❌>5%）",
                "✅/⚠️/❌ 检查项3：量能配合（结合趋势背景判断）",
                "✅/⚠️/❌ 检查项4：无重大利空（业绩大幅下滑也算利空）",
                "✅/⚠️/❌ 检查项5：筹码健康（获利比例<50%时必须⚠️或❌）",
                "✅/⚠️/❌ 检查项6：MACD信号（基于输入数据）",
                "✅/⚠️/❌ 检查项7：RSI安全区（>70超买❌；<30超卖看反弹）",
                "✅/⚠️/❌ 检查项8：KDJ信号（J>100超买❌；J<0超卖看反弹）",
                "✅/⚠️/❌ 检查项9：ATR风险可控（波动率是否合理）",
                "✅/⚠️/❌ 检查项10：买卖点逻辑一致（买入点>止损位）"
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
- ✅ 标准多头排列：MA5 > MA10 > MA20（必须条件）
- ✅ 低乖离率：<2%，最佳买点
- ✅ 缩量回调或放量突破
- ✅ 筹码集中健康
- ✅ 消息面有利好催化
- ✅ KDJ/RSI 未超买

### 买入（60-79分）：
- ✅ 标准多头排列（必须条件，弱势多头不够资格）
- ✅ 乖离率 <5%
- ✅ 量能正常
- ✅ KDJ 未极度超买（J<100）
- ✅ 基本面无重大风险（近一季度净利润未大幅下滑）
- ✅ 盈亏比 ≥ 2:1（潜在盈利/潜在亏损）
- ⚪ 允许一项次要条件不满足（但标准多头、KDJ未超买为必须条件）

### 持有/观望（40-59分）：
- ⚠️ 弱势多头或均线缠绕（非标准多头排列）
- ⚠️ 乖离率 >5%（追高风险）
- ⚠️ KDJ/RSI 超买
- ⚠️ 有风险事件
- ⚠️ 基本面有不确定性（如季度业绩下滑）

### 卖出/减仓（0-39分）：
- ❌ 空头排列
- ❌ 跌破MA20
- ❌ 放量下跌
- ❌ 重大利空（业绩腰斩、减持、处罚等）
- ❌ RSI+KDJ 双重超买

## 决策仪表盘核心原则

1. **核心结论先行**：一句话说清该买该卖
2. **分持仓建议**：空仓者和持仓者给不同建议
3. **精确狙击点**：必须给出具体价格，且买入点>止损位（逻辑自洽）
4. **检查清单可视化**：用 ✅⚠️❌ 明确显示每项检查结果，严格按照标准判定
5. **风险优先级**：基本面重大风险 > 技术面信号，舆情中的风险点要醒目标出
6. **信号一致性**：所有指标信号与最终结论必须逻辑一致，不能出现"超买却推荐买入"等矛盾
7. **数据真实性**：只使用输入提供的数据，严禁编造任何技术指标数值
8. **客观中立**：严禁确认偏差，不能先预设结论再选择性引用指标；利空信号必须与利多信号同等权重体现
9. **盈亏比底线**：潜在盈利/潜在亏损 < 2:1 的交易不具备操作价值，不应给买入建议"""

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

            # 后置验证：检测并修复AI输出中的逻辑矛盾
            result = self._validate_and_fix_result(result, context)

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
        
        # ========== 构建决策仪表盘格式的输入 ==========
        prompt = f"""# 决策仪表盘分析请求

## 📊 股票基础信息
| 项目 | 数据 |
|------|------|
| 股票代码 | **{code}** |
| 股票名称 | **{stock_name}** |
| 分析日期 | {context.get('date', '未知')} |

---

## 📈 技术面数据

### 今日行情
| 指标 | 数值 |
|------|------|
| 收盘价 | {today.get('close', 'N/A')} 元 |
| 开盘价 | {today.get('open', 'N/A')} 元 |
| 最高价 | {today.get('high', 'N/A')} 元 |
| 最低价 | {today.get('low', 'N/A')} 元 |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 成交量 | {self._format_volume(today.get('volume'))} |
| 成交额 | {self._format_amount(today.get('amount'))} |

### 均线系统（关键判断指标）
| 均线 | 数值 | 说明 |
|------|------|------|
| MA5 | {today.get('ma5', 'N/A')} | 短期趋势线 |
| MA10 | {today.get('ma10', 'N/A')} | 中短期趋势线 |
| MA20 | {today.get('ma20', 'N/A')} | 中期趋势线 |
| MA60 | {today.get('ma60', 'N/A')} | 长期趋势线 |
| 均线形态 | {context.get('ma_status', '未知')} | 多头/空头/缠绕 |
"""
        
        # 添加实时行情数据（量比、换手率等）
        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""
### 实时行情增强数据
| 指标 | 数值 | 解读 |
|------|------|------|
| 当前价格 | {rt.get('price', 'N/A')} 元 | |
| **量比** | **{rt.get('volume_ratio', 'N/A')}** | {rt.get('volume_ratio_desc', '')} |
| **换手率** | **{rt.get('turnover_rate', 'N/A')}%** | |
| 市盈率(动态) | {rt.get('pe_ratio', 'N/A')} | |
| 市净率 | {rt.get('pb_ratio', 'N/A')} | |
| 总市值 | {self._format_amount(rt.get('total_mv'))} | |
| 流通市值 | {self._format_amount(rt.get('circ_mv'))} | |
| 60日涨跌幅 | {rt.get('change_60d', 'N/A')}% | 中期表现 |
"""
        
        # 添加筹码分布数据
        if 'chip' in context:
            chip = context['chip']
            profit_ratio = chip.get('profit_ratio', 0)
            prompt += f"""
### 筹码分布数据（效率指标）
| 指标 | 数值 | 健康标准 |
|------|------|----------|
| **获利比例** | **{profit_ratio:.1%}** | 70-90%时警惕 |
| 平均成本 | {chip.get('avg_cost', 'N/A')} 元 | 现价应高于5-15% |
| 90%筹码集中度 | {chip.get('concentration_90', 0):.2%} | <15%为集中 |
| 70%筹码集中度 | {chip.get('concentration_70', 0):.2%} | |
| 筹码状态 | {chip.get('chip_status', '未知')} | |
"""
        
        # 添加趋势分析结果（基于交易理念的预判）
        if 'trend_analysis' in context:
            trend = context['trend_analysis']
            bias_warning = "🚨 超过5%，严禁追高！" if trend.get('bias_ma5', 0) > 5 else "✅ 安全范围"

            # 均线排列严格判定
            ma5_val = trend.get('ma5', today.get('ma5', 0))
            ma10_val = trend.get('ma10', today.get('ma10', 0))
            ma20_val = trend.get('ma20', today.get('ma20', 0))
            try:
                ma5_f, ma10_f, ma20_f = float(ma5_val or 0), float(ma10_val or 0), float(ma20_val or 0)
                if ma5_f > ma10_f > ma20_f and ma20_f > 0:
                    ma_verdict = "✅ 标准多头排列 MA5>MA10>MA20"
                    is_strict_bull = True
                elif ma5_f > ma10_f and ma10_f <= ma20_f:
                    ma_verdict = "⚠️ 弱势多头（MA5>MA10但MA10≤MA20），非标准多头排列，is_bullish应为false"
                    is_strict_bull = False
                elif ma5_f < ma10_f < ma20_f and ma5_f > 0:
                    ma_verdict = "❌ 空头排列 MA5<MA10<MA20"
                    is_strict_bull = False
                else:
                    ma_verdict = "⚠️ 均线缠绕/震荡格局，is_bullish应为false"
                    is_strict_bull = False
            except (TypeError, ValueError):
                ma_verdict = "数据异常"
                is_strict_bull = False

            # KDJ 数据
            kdj_k = trend.get('kdj_k', 'N/A')
            kdj_d = trend.get('kdj_d', 'N/A')
            kdj_j = trend.get('kdj_j', 'N/A')
            kdj_status = trend.get('kdj_status', '未知')
            kdj_signal = trend.get('kdj_signal', '')

            # 超买警告
            kdj_overbought = False
            try:
                if float(kdj_j) > 100:
                    kdj_overbought = True
            except (TypeError, ValueError):
                pass

            prompt += f"""
### 趋势分析预判（基于交易理念）
| 指标 | 数值 | 判定 |
|------|------|------|
| 趋势状态 | {trend.get('trend_status', '未知')} | |
| 均线排列 | {trend.get('ma_alignment', '未知')} | **{ma_verdict}** |
| 趋势强度 | {trend.get('trend_strength', 0)}/100 | |
| **乖离率(MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| 乖离率(MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| 乖离率(MA20) | {trend.get('bias_ma20', 0):+.2f}% | |
| Bias(6) | {trend.get('bias_6', 0):+.2f}% | 短期乖离 |
| Bias(12) | {trend.get('bias_12', 0):+.2f}% | 中期乖离 |
| Bias(24) | {trend.get('bias_24', 0):+.2f}% | 长期乖离 |
| 量能状态 | {trend.get('volume_status', '未知')} | {trend.get('volume_trend', '')} |
| **MACD** | DIF={trend.get('macd_dif', 0):.4f} DEA={trend.get('macd_dea', 0):.4f} | {trend.get('macd_status', '')} {trend.get('macd_signal', '')} |
| **RSI** | RSI(6)={trend.get('rsi_6', 0):.1f} RSI(12)={trend.get('rsi_12', 0):.1f} RSI(24)={trend.get('rsi_24', 0):.1f} | {trend.get('rsi_status', '')} {trend.get('rsi_signal', '')} |
| **KDJ** | K={kdj_k} D={kdj_d} J={kdj_j} | {kdj_status} {kdj_signal} |
| 系统信号 | {trend.get('buy_signal', '未知')} | |
| 系统评分 | {trend.get('signal_score', 0)}/100 | |
| **支撑位(MA5)** | **{trend.get('support_ma5', 'N/A')} 元** | 短期关键支撑 |
| **支撑位(MA10)** | **{trend.get('support_ma10', 'N/A')} 元** | 中期关键支撑 |

### 技术指标详解

#### MACD 指标
| 指标 | 数值 | 状态 |
|------|------|------|
| DIF | {trend.get('macd_dif', 0):.4f} | |
| DEA | {trend.get('macd_dea', 0):.4f} | |
| MACD柱 | {trend.get('macd_bar', 0):.4f} | |
| MACD状态 | {trend.get('macd_status', '未知')} | |
| 信号 | {trend.get('macd_signal', '未知')} | |

#### RSI 指标（超买超卖）
| 指标 | 数值 | 解读 |
|------|------|------|
| RSI(6) | {trend.get('rsi_6', 0):.1f} | 短期 |
| RSI(12) | {trend.get('rsi_12', 0):.1f} | 中期 |
| RSI(24) | {trend.get('rsi_24', 0):.1f} | 长期 |
| RSI状态 | {trend.get('rsi_status', '未知')} | >70超买 <30超卖 |
| 信号 | {trend.get('rsi_signal', '未知')} | |
"""
            
            # 添加新指标（BOLL/KDJ/ATR）
            if trend.get('boll_upper', 0) > 0:
                prompt += f"""
#### 布林带（BOLL）- 波动区间
| 指标 | 数值 | 解读 |
|------|------|------|
| 上轨 | {trend.get('boll_upper', 0):.2f} 元 | 压力位 |
| 中轨 | {trend.get('boll_middle', 0):.2f} 元 | 支撑/压力 |
| 下轨 | {trend.get('boll_lower', 0):.2f} 元 | 支撑位 |
| 价格位置 | {trend.get('boll_position', 0):.1f}% | 0-100%，50%为中性 |
| 带宽 | {trend.get('boll_bandwidth', 0):.2f}% | <10%收窄，变盘在即 |
| 状态 | {trend.get('boll_status', '未知')} | |
| 信号 | {trend.get('boll_signal', '未知')} | |
"""
            
            if trend.get('kdj_k', 0) > 0:
                kdj_buy_stars = '★' * trend.get('kdj_buy_strength', 0) + '☆' * (5 - trend.get('kdj_buy_strength', 0))
                kdj_sell_stars = '★' * trend.get('kdj_sell_strength', 0) + '☆' * (5 - trend.get('kdj_sell_strength', 0))
                prompt += f"""
#### KDJ 指标 - 短线买卖点
| 指标 | 数值 | 解读 |
|------|------|------|
| K值 | {trend.get('kdj_k', 0):.1f} | 快线 |
| D值 | {trend.get('kdj_d', 0):.1f} | 慢线 |
| J值 | {trend.get('kdj_j', 0):.1f} | J<0超卖，J>100超买 |
| 状态 | {trend.get('kdj_status', '未知')} | |
| 买入强度 | {kdj_buy_stars} ({trend.get('kdj_buy_strength', 0)}/5) | 5星=强烈买入 |
| 卖出强度 | {kdj_sell_stars} ({trend.get('kdj_sell_strength', 0)}/5) | 5星=强烈卖出 |
| 信号 | {trend.get('kdj_signal', '未知')} | |
"""
            
            if trend.get('atr', 0) > 0:
                prompt += f"""
#### ATR 波动率 - 风险管理
| 指标 | 数值 | 解读 |
|------|------|------|
| ATR值 | {trend.get('atr', 0):.2f} 元 | |
| ATR占比 | {trend.get('atr_pct', 0):.2f}% | 占当前股价 |
| 波动等级 | {trend.get('atr_level', '未知')} | 极低/低/正常/高/极高 |
| **止损位** | **{trend.get('atr_stop_loss', 0):.2f} 元** | 建议止损位（2倍ATR） |
| **止盈位** | **{trend.get('atr_take_profit', 0):.2f} 元** | 建议止盈位（3倍ATR） |
| 信号 | {trend.get('atr_signal', '未知')} | |
"""
            
            prompt += f"""
#### 系统分析理由
**买入理由**：
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['无'])) if trend.get('signal_reasons') else '- 无'}

**风险因素**：
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['无'])) if trend.get('risk_factors') else '- 无'}
"""
            # 添加信号冲突预警
            conflict_warnings = []
            if kdj_overbought and not is_strict_bull:
                conflict_warnings.append("🚨 KDJ极度超买(J>100) + 非标准多头排列 → 根据规则A，operation_advice最多为'持有'或'观望'")
            if kdj_overbought:
                conflict_warnings.append(f"⚠️ KDJ超买(J={kdj_j})，短线有回调风险，不宜给出'买入'建议")
            try:
                if float(ma5_f) < float(ma20_f) and ma20_f > 0:
                    conflict_warnings.append(f"🚨 MA5({ma5_f:.2f}) < MA20({ma20_f:.2f})，买入点不能设在MA5附近（会低于MA20风控线），参考规则C")
            except (TypeError, ValueError):
                pass

            if conflict_warnings:
                prompt += "\n#### ⚠️ 信号冲突预警（AI必须遵守）\n"
                for w in conflict_warnings:
                    prompt += f"- {w}\n"
        
        # 添加昨日对比数据
        if 'yesterday' in context:
            volume_change = context.get('volume_change_ratio', 'N/A')
            prompt += f"""
### 量价变化
- 成交量较昨日变化：{volume_change}倍
- 价格较昨日变化：{context.get('price_change_ratio', 'N/A')}%
"""
        
        # 添加系统预计算的检查清单
        if 'pre_checklist' in context:
            checklist = context['pre_checklist']
            prompt += f"""
---

## 🔍 系统预判检查清单（基于技术指标自动计算）

以下是系统根据实际数据预先计算的检查结果，请在分析中 **逐项确认或修正**，并在 `action_checklist` 中输出最终判定：

| 检查项 | 系统判定 | 依据 |
|--------|----------|------|
"""
            for item in checklist:
                prompt += f"| {item['name']} | {item['status']} | {item['detail']} |\n"

            prompt += """
> **重要**：以上为系统基于阈值自动判定，AI 应结合消息面、板块趋势等综合因素，在最终 `action_checklist` 中输出修正后的判定。
> 如发现系统判定有误，请在分析中明确说明修正原因。
"""

        # 添加所属板块信息
        if 'belong_board' in context:
            boards = context['belong_board']
            prompt += f"""
### 所属板块
该股票所属板块：**{' | '.join(boards)}**

> 请结合板块信息分析该股票在行业中的地位、板块整体趋势、以及板块轮动对个股的影响。
"""

        # 添加新闻搜索结果（重点区域）
        prompt += """
---

## 📰 舆情情报
"""
        if news_context:
            prompt += f"""
以下是 **{stock_name}({code})** 近7日的新闻搜索结果，请重点提取：
1. 🚨 **风险警报**：减持、处罚、利空
2. 🎯 **利好催化**：业绩、合同、政策
3. 📊 **业绩预期**：年报预告、业绩快报

```
{news_context}
```
"""
        else:
            prompt += """
未搜索到该股票近期的相关新闻。请主要依据技术面数据进行分析。
"""

        # 注入缺失数据警告
        if context.get('data_missing'):
            prompt += """
⚠️ **数据缺失警告**
由于接口限制，当前无法获取完整的实时行情和技术指标数据。
请 **忽略上述表格中的 N/A 数据**，重点依据 **【📰 舆情情报】** 中的新闻进行基本面和情绪面分析。
在回答技术面问题（如均线、乖离率）时，请直接说明“数据缺失，无法判断”，**严禁编造数据**。
"""

        # 明确的输出要求
        prompt += f"""
---

## ✅ 分析任务

请为 **{stock_name}({code})** 生成【决策仪表盘】，严格按照 JSON 格式输出。

### ⚠️ 重要：股票名称确认
如果上方显示的股票名称为"股票{code}"或不正确，请在分析开头**明确输出该股票的正确中文全称**。

### 重点关注（必须明确回答）：

#### 📈 趋势判断
1. ❓ 是否满足 MA5>MA10>MA20>MA60 多头排列？当前均线形态是什么？
2. ❓ 当前乖离率是否在安全范围内（<5%）？—— 超过5%必须标注"严禁追高"
3. ❓ Bias(6/12/24) 乖离指标显示的市场情绪如何？是否过度乐观或悲观？
4. ❓ 当前价格距离关键支撑位（MA5/MA10）有多远？跌破风险大吗？

#### 💰 量价配合
5. ❓ 量能是否配合（缩量回调/放量突破）？5日量比是多少？
6. ❓ 换手率水平如何？是否存在异常放量或缩量？
7. ❓ 量价背离情况：价涨量缩？价跌量增？

#### 🎯 技术指标
8. ❓ **MACD 状态**：DIF/DEA 是否金叉？柱状图趋势如何？是否零轴上方运行？
9. ❓ **RSI 超买超卖**：RSI(6/12/24) 是否处于超买区(>70)或超卖区(<30)？
10. ❓ **布林带(BOLL)**：价格位于上/中/下轨哪个位置？带宽是否收窄？是否有突破信号？
11. ❓ **KDJ 短线买卖点**：K/D/J值是多少？是否金叉/死叉？买入强度/卖出强度各几星？
12. ❓ **ATR 波动率**：波动等级是什么？基于ATR的止损位和止盈位建议是多少？

#### 💎 筹码与资金
13. ❓ 筹码结构是否健康？获利比例多少？筹码集中度如何？
14. ❓ 平均成本与当前价格的关系？筹码是否松动？
15. ❓ 市盈率/市净率估值水平如何？是否存在泡沫风险？

#### 📰 消息面与风险
16. ❓ 消息面有无重大利空？（减持、处罚、业绩变脸等）
17. ❓ 有无利好催化剂？（业绩预增、政策利好、行业景气等）
18. ❓ 60日涨跌幅如何？中期表现是强势还是弱势？

#### 🎲 综合风险评估
19. ❓ 当前位置风险收益比如何？值得买入/加仓吗？
20. ❓ 如果买入，具体的进场点位、止损位、止盈位建议是什么？
21. ❓ 持仓者和空仓者分别应该采取什么策略？

### 决策仪表盘要求：

#### 📋 基础信息
- **股票名称**：必须输出正确的中文全称（如"贵州茅台"而非"股票600519"）
- **核心结论**：一句话说清该买/该卖/该等（不超过30字）
- **信号类型**：🟢买入信号 / 🟡持有观望 / 🔴卖出信号

#### 💡 决策建议
- **持仓分类建议**：
  - **空仓者**：具体操作建议（何时介入、分几批、每批仓位）
  - **持仓者**：具体操作建议（继续持有、加仓、减仓、止盈）
- **信心等级**：高/中/低，并说明理由

#### 🎯 狙击点位（精确到分）
- **理想买入点**：最佳进场价格（如回踩MA5支撑）
- **次优买入点**：备选进场价格（如回踩MA10支撑）
- **止损位**：明确的止损价格（跌破则离场）
- **止盈目标**：分批止盈策略（第一目标价、第二目标价）
- **建议仓位**：具体仓位建议（如2-3成、半仓等）

#### ✅ 检查清单（每项必须标记）
- ✅/⚠️/❌ 多头排列
- ✅/⚠️/❌ 乖离率<5%（安全）
- ✅/⚠️/❌ 量能配合
- ✅/⚠️/❌ 筹码健康
- ✅/⚠️/❌ 无重大利空
- ✅/⚠️/❌ MACD 多头
- ✅/⚠️/❌ RSI 安全区
- ✅/⚠️/❌ BOLL 突破信号
- ✅/⚠️/❌ KDJ 买入信号
- ✅/⚠️/❌ ATR 风险可控

#### 📊 全面技术分析要求
在 `technical_analysis` 字段中，**必须包含以下所有维度的分析**：

1. **趋势判断**：均线形态、趋势强度、趋势方向
2. **MACD 分析**：DIF/DEA 数值、金叉/死叉状态、柱状图趋势、零轴位置
3. **RSI 分析**：RSI(6/12/24) 数值、超买超卖状态、背离情况
4. **BOLL 分析**：上轨XX元、中轨XX元、下轨XX元、当前位置XX%、带宽XX%、状态、信号
5. **KDJ 分析**：K=XX、D=XX、J=XX、金叉/死叉状态、买入强度XX星、卖出强度XX星、信号
6. **ATR 分析**：ATR=XX元（占股价XX%）、波动等级、止损位XX元、止盈位XX元、信号
7. **量价分析**：量比、换手率、量能状态、量价配合情况
8. **乖离率分析**：Bias(6/12/24) 数值、市场情绪判断
9. **支撑压力**：关键支撑位、关键压力位
10. **风险提示**：当前最大风险点、需要注意的信号

### 📊 全面技术分析示例格式（必须严格遵循）：

在 `technical_analysis` 字段中，必须按以下格式提供**完整、详细**的技术分析：

```
【趋势判断】
当前均线排列：MA5>MA10>MA20>MA60（多头排列）/ 空头排列 / 缠绕
趋势强度：XX/100，趋势状态：强势上升 / 震荡整理 / 弱势下跌
乖离率：MA5乖离+X.XX%（安全/超买），MA10乖离+X.XX%，MA20乖离+X.XX%
Bias乖离：Bias(6)=+X.XX%，Bias(12)=+X.XX%，Bias(24)=+X.XX%
关键支撑：MA5支撑XX元，MA10支撑XX元，MA20支撑XX元

【MACD指标】
DIF=X.XXXX，DEA=X.XXXX，MACD柱=X.XXXX
状态：金叉上行 / 死叉下行 / 零轴上方运行 / 零轴下方运行
信号：多头强势 / 空头压制 / 即将金叉 / 背离警告
柱状图趋势：放大 / 缩小，表明动能增强 / 减弱

【RSI指标】
RSI(6)=XX.X（短期），RSI(12)=XX.X（中期），RSI(24)=XX.X（长期）
状态：正常区间(30-70) / 超买区(>70) / 超卖区(<30)
信号：多头强势 / 空头压制 / 超买回调风险 / 超卖反弹机会
背离情况：无背离 / 顶背离(卖出信号) / 底背离(买入信号)

【BOLL布林带】
上轨XX.XX元（压力位），中轨XX.XX元（支撑/压力），下轨XX.XX元（支撑位）
当前价格位置：XX.X%（0%=下轨，50%=中轨，100%=上轨）
带宽：XX.XX%，状态：收窄(变盘在即) / 正常 / 扩张(趋势加速)
价格位置：运行于上轨与中轨之间 / 中轨附近 / 下轨附近
信号：突破上轨(强势) / 回踩中轨(支撑测试) / 跌破下轨(弱势)

【KDJ指标】
K=XX.X（快线），D=XX.X（慢线），J=XX.X（超前指标）
状态：K>D金叉多头排列 / K<D死叉空头排列 / 高位钝化 / 低位钝化
位置：超买区(>80) / 正常区(20-80) / 超卖区(<20)
买入强度：★★★★★ (5星) / ★★★☆☆ (3星) / ☆☆☆☆☆ (0星)
卖出强度：★★★★★ (5星) / ★★★☆☆ (3星) / ☆☆☆☆☆ (0星)
信号：强烈买入 / 持股待涨 / 观望 / 逢高减仓 / 强烈卖出

【ATR波动率】
ATR=X.XX元（真实波幅），占当前股价X.XX%
波动等级：极低(<2%) / 低(2-3%) / 正常(3-5%) / 高(5-8%) / 极高(>8%)
风控建议：
- 止损位：XX.XX元（基于2倍ATR，当前价-2*ATR）
- 止盈位：XX.XX元（基于3倍ATR，当前价+3*ATR）
市场状态：波动率低，市场平静 / 波动率正常 / 波动率高，需警惕风险
信号：波动率收缩，酝酿变盘 / 波动率扩张，趋势加速 / 波动率正常，风险可控

【量价配合】
量比：X.XX（相对5日均量），换手率：XX.XX%
量能状态：放量突破 / 缩量回调 / 温和放量 / 地量 / 巨量
5日量比：X.XX倍，量能趋势：递增 / 递减 / 稳定
量价关系：量价齐升(健康) / 价涨量缩(背离) / 价跌量增(恐慌) / 价跌量缩(惜售)
换手率分析：低于3%(冷门) / 3-7%(正常) / 7-15%(活跃) / 15-25%(高度活跃) / >25%(异常)

【综合评估】
技术面总体状态：强势上升 / 震荡整理 / 弱势下跌
多头信号数量：X个，空头信号数量：X个
最大风险点：乖离率过高 / 量能衰竭 / 指标背离 / 破位风险
买入时机判断：立即买入 / 等待回调 / 观望为主 / 不宜介入
```

**⚠️ 重要提醒**：
1. 每个指标的数值必须从表格数据中精确提取，严禁编造
2. 每个指标的状态和信号必须基于数值进行合理判断
3. 必须包含以上所有维度的分析，不可遗漏
4. 分析要客观、准确、可操作，避免模糊表述

请输出完整的 JSON 格式决策仪表盘。"""
        
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

    def _validate_and_fix_result(
        self,
        result: AnalysisResult,
        context: Dict[str, Any]
    ) -> AnalysisResult:
        """
        后置验证：检测并修复 AI 输出中的逻辑矛盾

        检测规则：
        1. 均线非标准多头排列时，不能给买入建议
        2. KDJ/RSI 超买时，不能给买入建议
        3. 买入点必须 > 止损位
        4. is_bullish 必须与实际均线排列一致
        """
        if not result.dashboard:
            return result

        trend_data = context.get('trend_analysis', {})
        fixes_applied = []

        # === 检查1：均线排列与 is_bullish 一致性 ===
        data_perspective = result.dashboard.get('data_perspective', {})
        trend_status = data_perspective.get('trend_status', {})
        price_position = data_perspective.get('price_position', {})

        try:
            ma5 = float(price_position.get('ma5', 0) or trend_data.get('ma5', 0))
            ma10 = float(price_position.get('ma10', 0) or trend_data.get('ma10', 0))
            ma20 = float(price_position.get('ma20', 0) or trend_data.get('ma20', 0))
        except (TypeError, ValueError):
            ma5 = ma10 = ma20 = 0

        is_strict_bull = ma5 > ma10 > ma20 > 0

        # 修复 is_bullish
        if trend_status.get('is_bullish') is True and not is_strict_bull:
            trend_status['is_bullish'] = False
            fixes_applied.append(f"修正is_bullish: MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f}，非标准多头排列")

        # === 检查1b：非标准多头排列时，operation_advice 最多为"持有"（规则B）===
        buy_advices = ['买入', '加仓', '强烈买入']

        if not is_strict_bull and result.operation_advice in buy_advices:
            result.operation_advice = '持有'
            result.decision_type = 'hold'
            if result.sentiment_score > 59:
                result.sentiment_score = 55
            fixes_applied.append(
                f"非标准多头排列(MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f})，"
                f"买入建议降级为持有"
            )
            core = result.dashboard.get('core_conclusion', {})
            if core:
                core['signal_type'] = '🟡持有观望'
            # 修正检查清单中的多头排列项
            action_checklist = result.dashboard.get('battle_plan', {}).get('action_checklist', [])
            for i, item in enumerate(action_checklist):
                if '多头排列' in str(item) and '✅' in str(item):
                    action_checklist[i] = item.replace('✅', '⚠️' if ma5 > ma10 else '❌')
                    fixes_applied.append("修正检查清单：多头排列项不应为✅")

        # === 检查2：超买环境下不能给买入建议 ===
        kdj_j = float(trend_data.get('kdj_j', 50))
        rsi_status = trend_data.get('rsi_status', '')
        kdj_overbought = kdj_j > 100
        rsi_overbought = rsi_status in ['超买', 'OVERBOUGHT']

        # 规则A：KDJ极度超买(J>100)，无论是否多头，最多"持有"
        if kdj_overbought and result.operation_advice in buy_advices:
            result.operation_advice = '持有' if is_strict_bull else '观望'
            result.decision_type = 'hold'
            if not is_strict_bull:
                result.trend_prediction = '震荡'
            if result.sentiment_score > 59:
                result.sentiment_score = 55
            fixes_applied.append(
                f"KDJ极度超买(J={kdj_j:.1f})，短线回调风险高，"
                f"{'标准多头降级为持有' if is_strict_bull else '非标准多头降级为观望'}"
            )
            core = result.dashboard.get('core_conclusion', {})
            if core:
                core['signal_type'] = '🟡持有观望' if is_strict_bull else '⚠️风险警告'

        # RSI+KDJ双重超买：无论其他条件，强制"观望"或"减仓"
        if kdj_overbought and rsi_overbought:
            if result.operation_advice in buy_advices + ['持有']:
                result.operation_advice = '观望'
                result.decision_type = 'hold'
                result.trend_prediction = '看空' if result.sentiment_score < 45 else '震荡'
                if result.sentiment_score > 50:
                    result.sentiment_score = 45
                fixes_applied.append(f"RSI+KDJ双重超买，强制降级为观望")
                core = result.dashboard.get('core_conclusion', {})
                if core:
                    core['signal_type'] = '⚠️风险警告'

        # === 检查3：买入点与止损位一致性 ===
        battle_plan = result.dashboard.get('battle_plan', {})
        sniper_points = battle_plan.get('sniper_points', {})

        def _extract_price(text: str) -> float:
            """从文本中提取价格数值"""
            import re
            if not text:
                return 0
            match = re.search(r'(\d+\.?\d*)\s*元', str(text))
            return float(match.group(1)) if match else 0

        ideal_buy_price = _extract_price(sniper_points.get('ideal_buy', ''))
        stop_loss_price = _extract_price(sniper_points.get('stop_loss', ''))

        if ideal_buy_price > 0 and stop_loss_price > 0 and ideal_buy_price < stop_loss_price:
            fixes_applied.append(
                f"买入点({ideal_buy_price:.2f}) < 止损位({stop_loss_price:.2f})，逻辑矛盾！"
                f"强制降级为观望"
            )
            # 买入点<止损位是致命逻辑错误，必须强制降级（而非仅警告）
            result.operation_advice = '观望'
            result.decision_type = 'hold'
            if result.sentiment_score > 50:
                result.sentiment_score = 45
            core = result.dashboard.get('core_conclusion', {})
            if core:
                core['signal_type'] = '⚠️风险警告'
            # 添加风险警告
            risk_alerts = result.dashboard.get('intelligence', {}).get('risk_alerts', [])
            risk_alerts.append(
                f"⚠️ 系统检测：理想买入点({ideal_buy_price}元)低于止损位({stop_loss_price}元)，"
                f"交易逻辑自相矛盾，买入即触发止损，本次建议无法执行"
            )

        # 检查买入点是否低于MA20（风控线）
        if ideal_buy_price > 0 and ma20 > 0 and ideal_buy_price < ma20 and not is_strict_bull:
            fixes_applied.append(
                f"买入点({ideal_buy_price:.2f}) < MA20({ma20:.2f})，均线非多头时买入即触发风控，强制降级"
            )
            result.operation_advice = '观望'
            result.decision_type = 'hold'
            core = result.dashboard.get('core_conclusion', {})
            if core:
                core['signal_type'] = '⚠️风险警告'
            risk_alerts = result.dashboard.get('intelligence', {}).get('risk_alerts', [])
            risk_alerts.append(
                f"⚠️ 系统检测：买入点({ideal_buy_price}元)低于MA20风控线({ma20:.2f}元)，"
                f"买入即触发减仓/离场条件，建议无法执行"
            )

        # === 检查4：成交量与成交额交叉校验 ===
        today = context.get('today', {})
        current_price = float(price_position.get('current_price', 0) or today.get('close', 0) or 0)
        raw_volume = today.get('volume', 0) or 0
        raw_amount = today.get('amount', 0) or 0
        if current_price > 0 and raw_volume > 0 and raw_amount > 0:
            expected_amount = raw_volume * current_price
            ratio = raw_amount / expected_amount if expected_amount > 0 else 0
            # 如果成交额/预期成交额偏差超过10倍，说明单位有问题
            if ratio > 10 or (ratio > 0 and ratio < 0.1):
                fixes_applied.append(
                    f"成交量/成交额单位疑似不一致: volume={raw_volume}, amount={raw_amount}, "
                    f"price={current_price}, 预期amount={expected_amount:.0f}, 实际偏差{ratio:.1f}倍"
                )
                risk_alerts = result.dashboard.get('intelligence', {}).get('risk_alerts', [])
                risk_alerts.append("⚠️ 系统检测：成交量与成交额数据可能存在单位不一致，请以实际行情软件数据为准")

        # === 检查5：筹码压力检查（获利比例<50%时限制目标位）===
        chip_structure = data_perspective.get('chip_structure', {})
        try:
            profit_ratio_str = str(chip_structure.get('profit_ratio', '100'))
            # 支持 "41.6%" 或 "0.416" 或 "41.6" 等格式
            profit_ratio_val = float(profit_ratio_str.replace('%', ''))
            if profit_ratio_val < 1:  # 如果是小数形式如 0.416
                profit_ratio_val *= 100
        except (TypeError, ValueError):
            profit_ratio_val = 100  # 默认不触发

        if profit_ratio_val < 50:
            avg_cost_str = str(chip_structure.get('avg_cost', '0'))
            try:
                avg_cost_val = float(avg_cost_str.replace('元', '').strip())
            except (TypeError, ValueError):
                avg_cost_val = 0

            take_profit_price = _extract_price(sniper_points.get('take_profit', ''))
            # 目标位不应超过平均成本太多（超半数套牢时，解套抛压巨大）
            if take_profit_price > 0 and avg_cost_val > 0 and take_profit_price > avg_cost_val:
                fixes_applied.append(
                    f"获利比例仅{profit_ratio_val:.1f}%，超半数持仓套牢，"
                    f"目标位{take_profit_price:.2f}元超过平均成本{avg_cost_val:.2f}元，"
                    f"上方解套抛压极重"
                )
                risk_alerts = result.dashboard.get('intelligence', {}).get('risk_alerts', [])
                risk_alerts.append(
                    f"⚠️ 获利比例仅{profit_ratio_val:.1f}%，{100-profit_ratio_val:.1f}%持仓套牢，"
                    f"平均成本{avg_cost_val:.2f}元附近将面临极强解套抛压，"
                    f"目标位{take_profit_price:.2f}元需谨慎看待"
                )
                # 套牢盘压力下不应给买入建议
                if result.operation_advice in buy_advices:
                    result.operation_advice = '观望'
                    result.decision_type = 'hold'
                    if result.sentiment_score > 50:
                        result.sentiment_score = 45
                    fixes_applied.append("超半数持仓套牢+买入建议，强制降级为观望")

            # 确保 trap_pressure 字段有内容
            if not chip_structure.get('trap_pressure') or chip_structure.get('trap_pressure') == '':
                chip_structure['trap_pressure'] = (
                    f"获利比例仅{profit_ratio_val:.1f}%，多数持仓套牢，上涨阻力大"
                )

        # === 检查6：基本面重大风险优先级（规则E）===
        # 扫描AI自身输出的risk_alerts和earnings_outlook，检测是否存在重大基本面风险
        intelligence = result.dashboard.get('intelligence', {})
        risk_alerts_text = ' '.join(str(a) for a in intelligence.get('risk_alerts', []))
        earnings_text = str(intelligence.get('earnings_outlook', ''))
        fundamental_text = str(result.fundamental_analysis or '')
        all_risk_text = f"{risk_alerts_text} {earnings_text} {fundamental_text}"

        # 检测重大基本面风险关键词
        import re
        major_risk_patterns = [
            r'净利润.*同比.*下滑.*(?:5\d|6\d|7\d|8\d|9\d|\d{3,})%',  # 净利润同比下滑>=50%
            r'(?:净利润|扣非).*(?:腰斩|大幅下滑|暴跌)',
            r'业绩预亏',
            r'立案调查',
            r'(?:重大|大额).*减持',
        ]
        found_major_risks = []
        for pattern in major_risk_patterns:
            if re.search(pattern, all_risk_text):
                found_major_risks.append(pattern)

        if found_major_risks and result.operation_advice in buy_advices:
            result.operation_advice = '观望'
            result.decision_type = 'hold'
            if result.sentiment_score > 50:
                result.sentiment_score = 45
            fixes_applied.append(
                f"基本面存在重大风险信号(规则E)，技术面买入建议降级为观望"
            )
            core = result.dashboard.get('core_conclusion', {})
            if core:
                core['signal_type'] = '⚠️风险警告'

        # === 检查7：量能解读一致性（规则D）===
        volume_analysis = data_perspective.get('volume_analysis', {})
        volume_meaning = str(volume_analysis.get('volume_meaning', ''))
        volume_status = str(volume_analysis.get('volume_status', ''))
        # 缩量 + 非标准多头 + 正面解读（洗盘）→ 需要修正
        if ('缩量' in volume_status or '缩量' in volume_meaning) and not is_strict_bull:
            positive_volume_keywords = ['洗盘', '抛压轻', '惜售', '底部放量']
            if any(kw in volume_meaning for kw in positive_volume_keywords):
                fixes_applied.append(
                    f"缩量+非标准多头却正面解读为'{volume_meaning}'，"
                    f"修正为客观解读(规则D)"
                )
                volume_analysis['volume_meaning'] = (
                    f"缩量（非标准多头趋势下），买盘动能不足，多头接力乏力，"
                    f"不宜正面解读为洗盘"
                )

        # 记录修复日志
        if fixes_applied:
            logger.warning(f"[后置验证] {result.name}({result.code}) 发现 {len(fixes_applied)} 处逻辑矛盾并修正:")
            for fix in fixes_applied:
                logger.warning(f"  - {fix}")

        return result

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
                
                # 提取 dashboard 数据
                dashboard = data.get('dashboard', None)

                # 优先使用 AI 返回的股票名称（如果原名称无效或包含代码）
                ai_stock_name = data.get('stock_name')
                if ai_stock_name and (name.startswith('股票') or name == code or 'Unknown' in name):
                    name = ai_stock_name

                # 解析所有字段，使用默认值防止缺失
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
def get_analyzer() -> GeminiAnalyzer:
    """获取 Gemini 分析器实例"""
    return GeminiAnalyzer()


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
    
    analyzer = GeminiAnalyzer()
    
    if analyzer.is_available():
        print("=== AI 分析测试 ===")
        result = analyzer.analyze(test_context)
        print(f"分析结果: {result.to_dict()}")
    else:
        print("Gemini API 未配置，跳过测试")
