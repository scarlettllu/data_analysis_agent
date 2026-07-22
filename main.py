"Streamlit entry point for Data Analysis Agent."
from __future__ import annotations
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DATA_DIR, OPENAI_API_KEY
from src.agent.orchestrator import AgentOrchestrator
from src.data_connector.factory import create_connector
from src.schema_manager.schema_reader import SchemaReader
from src.schema_manager.semantic_layer import SemanticLayer

st.set_page_config(
    page_title="数据分析 Agent",
    page_icon="📊",
    layout="wide",
)

st.title("📊 数据分析 Agent MVP")
st.caption(
    "CSV 上传 → Schema 识别 → 自然语言转 SQL → **SQLite 执行** → 表格/图表/简析 | "
    "参考 ADA / MindsDB / Basedash：Schema 感知 · 执行闭环 · 可溯源可信分析"
)

PIPELINE = ["① 上传 CSV", "② Schema", "③ NL→SQL", "④ SQLite", "⑤ 结果与溯源"]
st.markdown(" → ".join(PIPELINE))

# Sidebar — data source
with st.sidebar:
    st.header("数据源")
    source_type = st.radio("来源类型", ["示例数据", "上传文件", "SQLite"])

    connector = None
    source_name = ""

    if source_type == "示例数据":
        sample_path = DATA_DIR / "sample_sales.csv"
        if sample_path.exists():
            connector = create_connector(sample_path)
            source_name = str(sample_path)
            st.success("已加载 sample_sales.csv")
        else:
            st.warning("示例数据不存在，请运行: python scripts/gen_sample.py")

    elif source_type == "上传文件":
        uploaded = st.file_uploader("CSV / Excel", type=["csv", "xlsx", "xls"])
        if uploaded:
            save_path = DATA_DIR / uploaded.name
            DATA_DIR.mkdir(exist_ok=True)
            save_path.write_bytes(uploaded.getvalue())
            connector = create_connector(save_path)
            source_name = uploaded.name
            st.caption("CSV 已写入内存 SQLite，可直接 NL→SQL 查询")

    elif source_type == "SQLite":
        db_path = st.text_input("SQLite 路径", value=str(DATA_DIR / "demo.db"))
        p = Path(db_path)
        if not p.exists() and (DATA_DIR / "sample_sales.csv").exists():
            st.caption("demo.db 不存在，可运行: python scripts/gen_sqlite_demo.py")
        if p.exists():
            connector = create_connector(p)
            source_name = db_path

    st.divider()
    llm_status = "✅ 已配置 LLM" if OPENAI_API_KEY else "⚠️ 未配置 LLM（规则模式）"
    st.info(llm_status)
    if not OPENAI_API_KEY:
        st.caption("复制 .env.example 为 .env 并填入 API Key 可启用 LLM")

    st.divider()
    st.markdown("**示例问题**")
    examples = [
        "查询华北区 Q3 各品类毛利率",
        "检测这个数据集的数据质量",
        "为什么 10 月 GMV 下降 15%？",
        "根据这份销售数据预测未来 30 天销量",
        "生成一个销售经营仪表板",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:10]}", use_container_width=True):
            st.session_state["question"] = ex

if connector is None:
    st.info("请在左侧选择或上传数据源。")
    st.stop()

# Persist connector for Streamlit reruns
st.session_state["active_connector"] = connector
st.session_state["active_source"] = source_name

def _backend_label(conn) -> str:
    if hasattr(conn, "execution_backend"):
        return conn.execution_backend
    if hasattr(conn, "db_path"):
        return f"SQLite 文件 ({getattr(conn, 'db_path', '')})"
    return "SQLite / 数据引擎"

backend = _backend_label(connector)
st.session_state["execution_backend"] = backend

# Quick quality snapshot (trust baseline)
from src.automl.quality_checker import QualityChecker

_preview_table = connector.list_tables()[0]
_preview_df = connector.read_table(_preview_table)
_quick_qr = QualityChecker().check(_preview_df)
with st.expander("🔍 数据质量快览（缺失 / 重复 / 异常）", expanded=False):
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("质量评分", f"{_quick_qr.score}/100")
    q2.metric("行数", f"{_quick_qr.total_rows:,}")
    q3.metric("重复行", _quick_qr.duplicate_count)
    q4.metric("执行引擎", backend)
    if _quick_qr.issues:
        st.markdown("**发现的问题**")
        for issue in _quick_qr.issues[:8]:
            st.write(f"- {issue}")
    else:
        st.success("未发现明显质量问题（基于全表或采样）")

# Schema preview
with st.expander("Schema 与业务语义", expanded=False):
    schema_reader = SchemaReader(connector)
    semantic = SemanticLayer(connector)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Schema")
        st.code(schema_reader.get_schema_text())
    with col2:
        st.subheader("业务语义映射")
        st.markdown(semantic.build_context_block())

# Main tabs
tab_chat, tab_dashboard, tab_schema = st.tabs(["💬 分析对话", "📈 仪表板", "🗂️ Schema"])

with tab_chat:
    question = st.text_area(
        "输入分析问题",
        value=st.session_state.get("question", ""),
        height=80,
        placeholder="例如：查询华北区 Q3 各品类毛利率",
    )

    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("请输入问题")
        else:
            with st.spinner("Agent 正在分析..."):
                agent = AgentOrchestrator(connector, source_name)
                response = agent.analyze(question.strip())

            if response.plan:
                with st.expander("📋 任务规划", expanded=True):
                    st.write(f"**任务类型**: {response.plan.task_type.value}")
                    st.write(response.plan.rationale)
                    for step in response.plan.steps:
                        st.write(f"{step.step_id}. [{step.action}] {step.description}")

            if response.success:
                st.success("分析完成")

                trust1, trust2, trust3 = st.columns(3)
                trust1.markdown(f"**数据源**\n\n`{source_name}`")
                trust2.markdown(f"**执行引擎**\n\n`{backend}`")
                trust3.markdown(
                    f"**任务类型**\n\n`{response.plan.task_type.value if response.plan else 'query'}`"
                )

                if response.sql:
                    st.markdown("### 生成的 SQL（可审计）")
                    st.code(response.sql, language="sql")

                st.markdown("### 结论")
                st.markdown(response.answer)

                if response.data is not None and not response.data.empty:
                    st.markdown("### 数据结果")
                    st.dataframe(response.data, use_container_width=True)

                if response.chart and response.chart.figure:
                    st.markdown("### 可视化")
                    st.plotly_chart(response.chart.figure, use_container_width=True)
                    st.info(f"📖 图表解读: {response.chart.interpretation}")

                if response.forecast_result:
                    fc = response.forecast_result
                    st.markdown("### 模型评估")
                    mcols = st.columns(len(fc.metrics))
                    for i, (k, v) in enumerate(fc.metrics.items()):
                        mcols[i].metric(k, f"{v:,.3f}")
                    if fc.feature_importance:
                        st.markdown("**特征重要性**")
                        st.bar_chart(pd.Series(fc.feature_importance))

                if response.quality_report:
                    qr = response.quality_report
                    st.markdown("### 数据健康报告")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("质量评分", f"{qr.score}/100")
                    c2.metric("总行数", f"{qr.total_rows:,}")
                    c3.metric("总列数", qr.total_columns)
                    c4.metric("重复行", qr.duplicate_count)

                    qcol1, qcol2 = st.columns(2)
                    with qcol1:
                        st.markdown("**缺失值检测**")
                        miss = {k: v for k, v in qr.missing_summary.items() if v > 0}
                        if miss:
                            st.bar_chart(pd.Series(miss), horizontal=True)
                        else:
                            st.success("无缺失值")
                    with qcol2:
                        st.markdown("**异常值检测 (IQR)**")
                        if qr.outlier_summary:
                            outlier_pct = {k: v["pct"] for k, v in qr.outlier_summary.items()}
                            st.bar_chart(pd.Series(outlier_pct), horizontal=True)
                        else:
                            st.success("无明显异常值")

                    if qr.type_issues:
                        st.markdown("**字段类型问题**")
                        st.dataframe(
                            pd.DataFrame([{"字段": k, "问题": v} for k, v in qr.type_issues.items()]),
                            use_container_width=True,
                            hide_index=True,
                        )

                    if qr.issues:
                        st.markdown("**问题清单**")
                        for issue in qr.issues:
                            st.write(f"- {issue}")

                if response.metadata.get("attribution"):
                    attr = response.metadata["attribution"]
                    st.markdown("### 证据链")
                    st.write(
                        f"指标 **{attr.metric}** 整体变化 "
                        f"**{attr.overall_change:+,.0f}**（{attr.overall_change_pct:+.1f}%）"
                    )
                    for ev in attr.evidence[:8]:
                        st.write(
                            f"- `{ev['dimension']}={ev['value']}`: "
                            f"贡献 **{ev['contribution_pct']}%** "
                            f"（{ev['previous']:,.0f} → {ev['current']:,.0f}）"
                        )


                st.markdown("### 📜 分析依据与溯源")
                st.markdown(response.provenance_md)
            else:
                st.error(response.answer or response.error)

with tab_dashboard:
    st.subheader("经营仪表板")
    from src.dashboard.generator import DashboardGenerator

    dash_gen = DashboardGenerator(connector)
    config = dash_gen.auto_generate()
    table = connector.list_tables()[0]

    filter_values = {}
    if config.filters:
        fcols = st.columns(len(config.filters))
        for i, f in enumerate(config.filters):
            opts = ["全部"] + f.config.get("options", [])
            filter_values[f.config["column"]] = fcols[i].selectbox(f.title, opts)

    df = dash_gen.render_data(config, table, filter_values)

    if config.kpis:
        kpi_cols = st.columns(len(config.kpis))
        for i, kpi in enumerate(config.kpis):
            col_name = kpi.config["column"]
            kpi_cols[i].metric(kpi.title, f"{df[col_name].sum():,.0f}")

    if config.charts:
        from src.visualizer.chart_generator import ChartGenerator

        cg = ChartGenerator()
        for chart_w in config.charts:
            result = cg.generate(
                df,
                x=chart_w.config.get("x"),
                y=chart_w.config.get("y"),
                intent=chart_w.config.get("chart_type", ""),
            )
            if result.figure:
                st.plotly_chart(result.figure, use_container_width=True)
                st.caption(result.interpretation)

    st.markdown("### 明细数据")
    st.dataframe(df.head(200), use_container_width=True)
with tab_schema:
    schema = SchemaReader(connector).get_schema_summary()
    for tbl in schema["tables"]:
        st.subheader(f"📋 {tbl['name']} ({tbl['row_count']} 行)")
        df_cols = pd.DataFrame(tbl["columns"])
        # 把所有object类型列强制转为字符串，消除日期/数字混类型报错
        for col in df_cols.select_dtypes(include=["object"]).columns:
            df_cols[col] = df_cols[col].astype(str)
        st.dataframe(df_cols, use_container_width=True)

        if tbl.get("sample_rows"):
            st.markdown("**样例数据**")
            df_sample = pd.DataFrame(tbl["sample_rows"])
            for col in df_sample.select_dtypes(include=["object"]).columns:
                df_sample[col] = df_sample[col].astype(str)
            st.dataframe(df_sample, use_container_width=True)