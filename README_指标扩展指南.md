# 📊 股票智能分析系统 - 指标扩展指南

## 🎯 概述

本指南详细说明了当前系统已有的技术指标和宏观指标，以及建议新增的指标及其实现方法。

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `指标分析与扩展建议.md` | 完整的指标分析和扩展建议文档 |
| `示例_布林带指标实现.py` | 布林带（BOLL）指标完整实现示例 |
| `示例_北向资金数据获取.py` | 北向资金数据获取与分析示例 |

## ✅ 当前系统能力一览

### 技术指标（已实现）
- ✅ **均线系统**：MA5/10/20/60，多空排列，乖离率
- ✅ **MACD**：DIF/DEA/BAR，金叉死叉，零轴判断
- ✅ **RSI**：RSI(6/12/24)，超买超卖，背离识别
- ✅ **量价分析**：成交量、量比、换手率、量价关系
- ✅ **筹码分布**：筹码集中度、盈亏比例、成本分布
- ✅ **趋势判断**：强弱判断、支撑压力位识别

### 宏观指标（已实现）
- ✅ **大盘指数**：上证/深证/创业板实时数据
- ✅ **市场统计**：涨跌家数、涨跌停统计、成交额
- ✅ **板块分析**：领涨/领跌板块 TOP5
- ✅ **舆情情报**：实时新闻搜索（Tavily/SerpAPI）

## 🚀 核心推荐扩展（第一阶段）

### 技术指标扩展

#### 1. 布林带（BOLL）⭐⭐⭐⭐⭐
**优先级**：🔴 最高

**价值**：
- 判断价格波动区间
- 识别超买超卖
- 捕捉突破信号
- 布林带收窄预示变盘

**实现难度**：⭐⭐ 简单

**参考实现**：`示例_布林带指标实现.py`

---

#### 2. KDJ 指标 ⭐⭐⭐⭐⭐
**优先级**：🔴 最高

**价值**：
- 短线买卖点判断
- 比 RSI 更敏感
- 金叉死叉信号明确

**实现难度**：⭐⭐ 简单

**实现要点**：
```python
# 计算公式
RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) * 100
K = RSV 的 M1 日移动平均
D = K 的 M2 日移动平均  
J = 3K - 2D

# 标准参数
N = 9, M1 = 3, M2 = 3
```

---

#### 3. ATR（平均真实波幅）⭐⭐⭐⭐⭐
**优先级**：🔴 最高

**价值**：
- 衡量价格波动性
- 科学设置止损止盈
- 风险管理必备

**实现难度**：⭐⭐ 简单

**实现要点**：
```python
# 真实波幅计算
TR = max(
    最高价 - 最低价,
    abs(最高价 - 昨收),
    abs(最低价 - 昨收)
)
ATR = TR 的 14 日指数移动平均

# 应用
止损位 = 买入价 - 2 * ATR
止盈位 = 买入价 + 3 * ATR
```

---

### 宏观指标扩展

#### 4. 北向资金 ⭐⭐⭐⭐⭐
**优先级**：🔴 最高

**价值**：
- 追踪外资流向
- 判断市场情绪
- 挖掘外资重仓股
- 预判市场走势

**实现难度**：⭐⭐ 简单

**参考实现**：`示例_北向资金数据获取.py`

**数据源**：
```python
import akshare as ak

# 每日流入数据
df = ak.stock_em_hsgt_north_net_flow_in(symbol="北向资金")

# 外资重仓股
holdings = ak.stock_em_hsgt_hold_stock(market="北向", indicator="持股数量")
```

---

#### 5. 融资融券 ⭐⭐⭐⭐⭐
**优先级**：🔴 最高

**价值**：
- 监控杠杆资金
- 判断市场情绪
- 个股活跃度
- 融资余额创新高 = 看多

**实现难度**：⭐⭐ 简单

**数据源**：
```python
import akshare as ak

# 两融余额
df_margin = ak.stock_margin_sse(date="20260210")

# 个股融资融券
df_detail = ak.stock_margin_detail_sse(symbol="600519", date="20260210")
```

**监控指标**：
- 融资余额变化
- 融资买入额
- 融券卖出量
- 两融占流通市值比例

---

## 📋 实施建议

### 阶段一：核心扩展（1-2周）
**目标**：补齐核心技术指标和资金面数据

| 任务 | 预计工时 | 价值 |
|------|---------|------|
| 布林带（BOLL） | 2小时 | ⭐⭐⭐⭐⭐ |
| KDJ 指标 | 3小时 | ⭐⭐⭐⭐⭐ |
| ATR 波动率 | 2小时 | ⭐⭐⭐⭐⭐ |
| 北向资金 | 4小时 | ⭐⭐⭐⭐⭐ |
| 融资融券 | 4小时 | ⭐⭐⭐⭐⭐ |

**总工时**：约 15 小时

---

### 阶段二：深度分析（2-3周）
**目标**：增强资金面和机构行为追踪

| 任务 | 预计工时 | 价值 |
|------|---------|------|
| VWAP 均价线 | 2小时 | ⭐⭐⭐⭐ |
| OBV 能量潮 | 2小时 | ⭐⭐⭐⭐ |
| 龙虎榜数据 | 6小时 | ⭐⭐⭐⭐⭐ |
| 主力资金流向 | 6小时 | ⭐⭐⭐⭐⭐ |
| CCI 指标 | 3小时 | ⭐⭐⭐⭐ |

**总工时**：约 19 小时

---

## 🔧 代码集成建议

### 1. 目录结构
```
src/
├── indicators/           # 新增：技术指标模块
│   ├── __init__.py
│   ├── base.py          # 基础指标类
│   ├── boll.py          # 布林带
│   ├── kdj.py           # KDJ指标
│   ├── atr.py           # ATR波动率
│   ├── vwap.py          # VWAP
│   └── obv.py           # OBV能量潮
│
├── macro/               # 新增：宏观数据模块
│   ├── __init__.py
│   ├── base.py          # 基础数据类
│   ├── north_flow.py    # 北向资金
│   ├── margin.py        # 融资融券
│   ├── lhb.py           # 龙虎榜
│   └── fund_flow.py     # 主力资金
│
└── stock_analyzer.py    # 扩展原有分析器
```

### 2. 集成到现有分析流程

**修改 `src/stock_analyzer.py`**：
```python
from src.indicators.boll import BOLLIndicator
from src.indicators.kdj import KDJIndicator
from src.indicators.atr import ATRIndicator

class StockTrendAnalyzer:
    def __init__(self):
        # 现有指标
        self.macd = ...
        self.rsi = ...
        
        # 新增指标
        self.boll = BOLLIndicator()
        self.kdj = KDJIndicator()
        self.atr = ATRIndicator()
    
    def analyze(self, df: pd.DataFrame):
        # 现有分析
        result = self._analyze_ma(df)
        result.macd = self._analyze_macd(df)
        result.rsi = self._analyze_rsi(df)
        
        # 新增分析
        result.boll = self.boll.calculate(df)
        result.kdj = self.kdj.calculate(df)
        result.atr = self.atr.calculate(df)
        
        return result
```

**修改 `src/core/pipeline.py`**：
```python
from src.macro.north_flow import NorthFlowAnalyzer
from src.macro.margin import MarginAnalyzer

class StockAnalysisPipeline:
    def __init__(self):
        # 现有模块
        self.trend_analyzer = StockTrendAnalyzer()
        
        # 新增宏观分析
        self.north_flow = NorthFlowAnalyzer()
        self.margin_analyzer = MarginAnalyzer()
    
    def analyze_stock(self, code: str):
        # 技术分析
        tech_result = self.trend_analyzer.analyze(df)
        
        # 宏观数据
        north_flow_data = self.north_flow.get_daily_flow()
        margin_data = self.margin_analyzer.get_margin_data(code)
        
        # 整合到AI分析
        analysis_context = {
            'technical': tech_result,
            'north_flow': north_flow_data,
            'margin': margin_data,
        }
        
        return self.analyzer.analyze(analysis_context)
```

### 3. AI 决策仪表盘增强

**新的分析维度**：
```
🎯 决策仪表盘（增强版）

【技术面】
✅ 趋势：多头排列（MA5>MA10>MA20）
✅ MACD：零轴上金叉（看多）
⚠️ 布林带：接近上轨，注意回调风险
✅ KDJ：J值60（中性偏多）
✅ ATR：波动率适中（风险可控）

【资金面】
✅ 北向资金：连续5日净流入，累计80亿
✅ 融资买入：近3日持续增加
✅ 主力资金：大单净流入500万
⚠️ 量比：1.2（略显放量）

【风险提示】
⚠️ 乖离率5.2%（略高，不建议追高）
⚠️ 布林带上轨接近，存在回调风险

【操作建议】
💡 建议：观望，等待回调至MA5或布林带中轨
💰 买入价：16.50元（MA5支撑位）
🛑 止损价：15.80元（2倍ATR）
🎯 目标价：18.20元（布林带上轨）
```

---

## 📊 数据源配置

### AkShare（推荐，免费）
```python
pip install akshare

import akshare as ak

# 北向资金
df_north = ak.stock_em_hsgt_north_net_flow_in(symbol="北向资金")

# 融资融券
df_margin = ak.stock_margin_sse(date="20260210")

# 龙虎榜
df_lhb = ak.stock_lhb_detail_em(date="20260210")

# 主力资金
df_fund = ak.stock_individual_fund_flow(stock="600519", market="沪深A")
```

### Tushare Pro（付费，高质量）
```python
pip install tushare

import tushare as ts

ts.set_token('your_token')
pro = ts.pro_api()

# 北向资金
df = pro.moneyflow_hsgt(trade_date='20260210')

# 融资融券
df = pro.margin(trade_date='20260210')

# 龙虎榜
df = pro.top_list(trade_date='20260210')
```

---

## 🎓 学习资源

### 技术指标
- 布林带（BOLL）：[百度百科](https://baike.baidu.com/item/布林线)
- KDJ 指标：[百度百科](https://baike.baidu.com/item/KDJ指标)
- ATR 指标：[Investopedia](https://www.investopedia.com/terms/a/atr.asp)

### 数据接口文档
- AkShare：https://akshare.akfamily.xyz/
- Tushare Pro：https://tushare.pro/document/2

### Python 数据分析
- Pandas 官方文档：https://pandas.pydata.org/docs/
- NumPy 官方文档：https://numpy.org/doc/

---

## ❓ 常见问题

### Q1：如何测试新增指标？
A：参考 `示例_布林带指标实现.py` 中的 `example_usage()` 函数，独立测试指标计算逻辑。

### Q2：如何集成到现有系统？
A：按照本文档「代码集成建议」章节的步骤，逐步集成到 `StockTrendAnalyzer` 和 `StockAnalysisPipeline`。

### Q3：数据源选择哪个？
A：
- **免费用户**：推荐 AkShare，完全免费，数据全面
- **专业用户**：推荐 Tushare Pro，数据质量高，但需积分/付费
- **混合使用**：AkShare + Tushare，互为补充

### Q4：如何避免API限流？
A：
- 使用数据缓存（SQLite 数据库）
- 设置请求间隔（`time.sleep()`）
- 批量获取数据，减少请求次数

---

## 📞 技术支持

如有疑问，请提交 Issue 到项目 GitHub：
https://github.com/seanding199/daily_stock_analysis

---

**文档版本**：v1.0  
**更新日期**：2026-02-10  
**作者**：AI Assistant
