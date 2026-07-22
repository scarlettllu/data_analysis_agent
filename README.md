# 数据分析 Agent MVP

面向企业数据分析场景的智能 Agent，实现 **自然语言输入 → 数据连接 → Schema 感知 → 自动执行 → 返回结果/图表/报告/应用** 的完整闭环。

参考 ADA、MindsDB、Basedash 的设计理念，而非仅生成 SQL/Python 代码。

## 核心能力

| 能力 | 说明 |
|------|------|
| 数据连接与执行闭环 | CSV / Excel / SQLite，自动执行 SQL/Python，错误解释与修复 |
| Schema 感知与语义层 | 自动读取 schema，业务同义词映射（销售额 → gmv/revenue） |
| 多步任务规划与归因 | 复杂问题自动拆解，GMV 下降自动按维度下钻与贡献度计算 |
| 自动可视化 | 根据数据结构选择图表，生成引用具体数据点的解读 |
| AutoML 预测 | 自动识别日期/目标列，GradientBoosting 时序预测 + 评估指标 |
| 仪表板生成 | Streamlit 仪表板，含筛选器、KPI、图表、数据表 |
| 结果可信度 | 展示数据来源、SQL、使用字段、证据链 |

## 项目结构

```
data-analysis-agent/
├── main.py                 # Streamlit 入口
├── config.py               # 全局配置
├── requirements.txt
├── data/
│   └── sample_sales.csv    # 示例销售数据
├── scripts/
│   └── gen_sample.py       # 生成更完整的示例数据
└── src/
    ├── data_connector/     # 数据连接（CSV/Excel/SQLite/MySQL/PG 预留）
    ├── schema_manager/     # Schema 摘要 + 业务语义层
    ├── executor/           # SQL/Python 执行器
    ├── planner/            # 任务规划 + 归因分析
    ├── visualizer/         # 自动图表选择与生成
    ├── automl/             # 预测建模 + 数据质量检测
    ├── dashboard/          # 仪表板配置生成
    ├── provenance/         # 分析溯源与证据链
    └── agent/              # Agent 编排器（核心）
```

## 快速开始

### 1. 安装依赖

```bash
cd data-analysis-agent
pip install -r requirements.txt
```

### 2. 配置 LLM（可选）

```bash
copy .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY（支持 OpenAI 兼容 API）
```

未配置 LLM 时，Agent 使用规则引擎模式，仍可完成基础分析。

### 3. 启动

```bash
streamlit run main.py
```

浏览器打开 `http://localhost:8501`

### 4. 示例问题

- 「查询华北区 Q3 各品类毛利率」
- 「检测这个数据集的数据质量」
- 「为什么 10 月 GMV 下降 15%？」
- 「根据这份销售数据预测未来 30 天销量」
- 「生成一个销售经营仪表板」

## 架构设计

```
用户自然语言
    │
    ▼
TaskPlanner ──→ 识别任务类型（查询/质量/归因/预测/仪表板）
    │
    ▼
SchemaReader + SemanticLayer ──→ 字段映射，避免幻觉
    │
    ▼
AgentOrchestrator
    ├── SQLExecutor / PythonExecutor ──→ 自动执行
    ├── AttributionAnalyzer ──→ 维度下钻 + 贡献度
    ├── TimeSeriesForecaster ──→ AutoML 预测
    ├── ChartGenerator ──→ 自动可视化 + 解读
    ├── DashboardGenerator ──→ 仪表板
    └── ProvenanceTracker ──→ 溯源与证据链
    │
    ▼
Streamlit UI ──→ 结果 / 图表 / 报告 / 仪表板
```

## 模块说明

### data_connector

- `CsvSQLiteConnector` — CSV 上传后载入内存 SQLite 执行
- `ExcelConnector` — pandas + DuckDB
- `SQLiteConnector` — SQLAlchemy
- `MySQLConnector` / `PostgreSQLConnector` — 预留扩展接口

### schema_manager

- `SchemaReader` — 表/字段/类型/样例值摘要
- `SemanticLayer` — 业务同义词映射，如「销售额」→ `gmv`

### executor

- `SQLExecutor` — 执行 SQL，错误解释与修复建议
- `PythonExecutor` — 安全沙箱执行分析代码

### planner

- `TaskPlanner` — 多步任务规划（LLM 或规则）
- `AttributionAnalyzer` — 自动归因与贡献度计算

### visualizer

- `ChartSelector` — 根据数据结构自动选图表类型
- `ChartGenerator` — Plotly 图表 + 数据点级解读

### automl

- `TimeSeriesForecaster` — 滞后特征 + GradientBoosting
- `QualityChecker` — 缺失值/重复/异常值检测

## 扩展方向

- [ ] 接入 MySQL / PostgreSQL 生产数据库
- [ ] 支持多表 JOIN 与关系图谱
- [ ] 增加 Prophet / LightGBM 模型选项
- [ ] 仪表板导出为独立 HTML
- [ ] 对话历史与多轮追问
- [ ] 权限管理与 SQL 安全审计

## License

MIT
