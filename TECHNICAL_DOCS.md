# 技术实现文档 (Technical Documentation)

## 🏗️ 架构概览
本项目采用典型的 **Streamlit** 单页应用架构。后端逻辑与前端展示紧密耦合，利用 Python 的强大生态进行数据处理与分析。

### 核心模块
1.  **数据层 (Data Layer)**
    *   **AkShare**: 作为核心数据接口库，负责获取 A 股实时行情、历史 K 线、财务报表、个股资料、行业成分股等数据。
    *   **Requests/BeautifulSoup**: 用于补充爬取 AkShare 暂未覆盖的特定数据 (如部分股吧评论或特定格式的公告)。
    *   **Pandas**: 用于所有数据的清洗、转换、计算 (如均线计算、财务指标转置)。

2.  **逻辑层 (Logic Layer)**
    *   **`investment_research.py`**: 包含主要的业务逻辑与页面布局控制。
    *   **`agents.py`**: 实现了基于角色的 AI 分析系统。
        *   `BaseAgent`: 基类，定义通用属性。
        *   `FundamentalAnalyst`: 专注于财务数据与估值分析。
        *   `TechnicalAnalyst`: 专注于 K 线形态与技术指标分析。
        *   `NewsAnalyst`: 专注于舆情与公告解读。
        *   `RiskManager`: 专注于风险提示与仓位建议。
    *   **`llm_utils.py`**: 封装了与大模型 (Qwen-2.5-7B) 的交互逻辑，使用 OpenAI SDK 格式进行调用。

3.  **展示层 (Presentation Layer)**
    *   **Streamlit**: 负责构建 Web 界面 (Sidebar, Tabs, Columns, Metrics)。
    *   **Plotly**: 负责绘制交互式图表 (K 线图、柱状图、Treemap、散点图)。

## 🔧 关键技术细节

### 1. 数据缓存机制
为了提高响应速度并避免频繁请求导致 IP 被封，项目中大量使用了 Streamlit 的缓存装饰器 `@st.cache_data`。
*   `get_stock_list`: 缓存 24 小时 (股票列表变动不频繁)。
*   `get_industry_peers`: 缓存 1 小时 (行业数据相对稳定)。
*   `get_market_indices`: 缓存 1 分钟 (保证行情实时性)。

### 2. PyArrow 兼容性处理
Streamlit 底层使用 Arrow 进行数据传输。由于金融数据中常包含混合类型 (如股票代码 '000001' 可能被误判为数字)，我们在数据处理阶段显式地将代码列转换为 `string` 类型，避免 `ArrowInvalid` 错误。
```python
peers['代码'] = peers['代码'].astype(str)
```

### 3. AI 多智能体工作流
AI 分析流程如下：
1.  **上下文收集**: 程序自动聚合当前的行情、财务、行业、新闻数据，转换为 Markdown 格式。
2.  **Prompt 构建**: 为每个 Agent 构建特定的 System Prompt，注入角色设定与任务目标。
3.  **并行/串行调用**: 依次调用 LLM API 获取各角色的分析结果。
4.  **综合汇总**: 最后由 "CIO" (首席投资官) 角色汇总所有分析，生成最终建议。

### 4. 风险对冲策略生成
利用 LLM 的推理能力，结合当前市场指数 (Context)，动态生成结构化的对冲策略。Prompt 中明确要求了输出格式 (Markdown 列表)，以保证前端展示的整洁性。

## 📦 依赖库说明
*   `streamlit`: Web 应用框架。
*   `akshare`: 开源财经数据接口。
*   `pandas`: 数据分析。
*   `plotly`: 交互式绘图。
*   `openai`: 调用兼容 OpenAI 协议的大模型接口。
*   `requests`, `beautifulsoup4`: 辅助爬虫。

## 🔮 未来扩展方向
*   **异步处理**: 引入 `asyncio` 优化 AI 分析的并发速度。
*   **更多数据源**: 接入更多高频或深度数据接口。
*   **用户账户系统**: 保存用户的自选股与历史分析记录。
