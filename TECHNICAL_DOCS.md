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

## 🛠️ 关键技术点与问题解决

### 1. PyArrow 序列化错误 (Serialization Error)
*   **问题**: Streamlit 在渲染 DataFrame 时，如果列中包含混合类型 (如既有数字又有字符串)，会抛出 `pyarrow.lib.ArrowInvalid`。
*   **解决**: 引入 `safe_dataframe(df)` 辅助函数。在调用 `st.dataframe` 前，该函数会将所有 `object` 类型的列强制转换为 `string` 类型，确保类型一致性。

### 2. 财务图表时间轴排序
*   **问题**: 财务报表数据转置后，索引为日期字符串，直接绘图会导致 X 轴乱序。
*   **解决**: 使用 `pd.to_datetime()` 将索引转换为时间对象，并进行 `sort_index()` 排序，确保 Plotly 能正确按时间顺序绘制柱状图。

### 3. 风险对冲模块 (Risk Hedging)
*   **实现**: 在 "投资组合助手" 页面，系统首先获取当前市场主要指数的实时数据，将其作为 Context 注入到 Prompt 中。
*   **Prompt 设计**: 要求 LLM 输出结构化的 Markdown 格式，包含 "市场风险评估" 和具体的 "对冲策略" (逻辑、标的、操作建议)。

### 4. 实时数据源切换
*   **策略**: 优先使用 AkShare 的 `stock_board_industry_name_em` (东方财富) 获取行业热点，使用 `stock_hsgt_fund_flow_summary_em` 获取北向资金流向，替代了早期的静态示例数据。

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
