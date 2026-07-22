"""Core agent orchestrator — ties all modules into analysis loop."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from src.automl.forecaster import TimeSeriesForecaster
from src.automl.quality_checker import QualityChecker
from src.dashboard.generator import DashboardGenerator
from src.data_connector.base import BaseConnector
from src.executor.python_executor import PythonExecutor
from src.executor.sql_executor import SQLExecutor
from src.planner.attribution import AttributionAnalyzer
from src.planner.task_planner import AnalysisPlan, TaskPlanner, TaskType
from src.provenance.tracker import ProvenanceTracker
from src.schema_manager.schema_reader import SchemaReader
from src.schema_manager.semantic_layer import SemanticLayer
from src.visualizer.chart_generator import ChartGenerator, ChartResult


@dataclass
class AgentResponse:
    success: bool
    answer: str
    data: pd.DataFrame | None = None
    chart: ChartResult | None = None
    plan: AnalysisPlan | None = None
    provenance_md: str = ""
    dashboard_config: Any = None
    forecast_result: Any = None
    quality_report: Any = None
    sql: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """End-to-end analysis agent."""

    def __init__(self, connector: BaseConnector, data_source_name: str = ""):
        self.connector = connector
        self.connector.connect()
        self.data_source = data_source_name or str(getattr(connector, "file_path", "database"))
        self.schema_reader = SchemaReader(connector)
        self.semantic = SemanticLayer(connector)
        self.sql_executor = SQLExecutor(connector)
        self.python_executor = PythonExecutor()
        self.planner = TaskPlanner()
        self.chart_gen = ChartGenerator()
        self.attribution = AttributionAnalyzer()
        self.forecaster = TimeSeriesForecaster()
        self.quality_checker = QualityChecker()
        self.dashboard_gen = DashboardGenerator(connector)

    def analyze(self, question: str) -> AgentResponse:
        schema_text = self.schema_reader.get_schema_text()
        semantic_ctx = self.semantic.build_context_block()
        plan = self.planner.plan(question, schema_text, semantic_ctx)
        tracker = ProvenanceTracker(question, self.data_source)
        tracker.add_step("任务规划", "plan", plan.rationale)

        handlers = {
            TaskType.QUERY: self._handle_query,
            TaskType.QUALITY: self._handle_quality,
            TaskType.ATTRIBUTION: self._handle_attribution,
            TaskType.FORECAST: self._handle_forecast,
            TaskType.DASHBOARD: self._handle_dashboard,
            TaskType.GENERAL: self._handle_query,
        }
        handler = handlers.get(plan.task_type, self._handle_query)
        response = handler(question, plan, tracker, schema_text, semantic_ctx)
        response.plan = plan
        response.provenance_md = tracker.get().to_markdown()
        return response

    def _handle_query(
        self, question: str, plan: AnalysisPlan, tracker: ProvenanceTracker,
        schema_text: str, semantic_ctx: str,
    ) -> AgentResponse:
        sql = self._generate_sql(question, schema_text, semantic_ctx)
        tracker.add_step("生成 SQL", "sql", "根据 schema 生成查询", sql)

        result = self.sql_executor.execute(sql)
        if not result.success:
            fixed_sql = self._try_fix_sql(sql, result.error, schema_text)
            if fixed_sql:
                tracker.add_step("SQL 修复重试", "sql", result.error_hint, fixed_sql)
                result = self.sql_executor.execute(fixed_sql)
                sql = fixed_sql

        if not result.success:
            tracker.set_conclusion(f"查询失败: {result.error}. {result.error_hint}")
            return AgentResponse(
                success=False,
                answer=f"执行失败: {result.error}\n\n修复建议: {result.error_hint}",
                sql=sql,
                error=result.error,
            )

        df = result.data
        chart = self.chart_gen.generate(df, intent=question)
        fields = self._extract_fields_from_sql(sql)
        tracker.add_step("执行查询", "execute", f"返回 {len(df)} 行", sql, fields)
        tracker.add_evidence({"rows": len(df), "columns": list(df.columns)})

        answer = self._generate_answer(question, df, chart, sql)
        tracker.set_conclusion(answer)

        return AgentResponse(
            success=True,
            answer=answer,
            data=df,
            chart=chart,
            sql=sql,
        )

    def _handle_quality(
        self, question: str, plan: AnalysisPlan, tracker: ProvenanceTracker,
        schema_text: str, semantic_ctx: str,
    ) -> AgentResponse:
        table = self.connector.list_tables()[0]
        df = self.connector.read_table(table)
        report = self.quality_checker.check(df)
        tracker.add_step(
            "数据质量检测",
            "python",
            report.summary,
            fields_used=list(df.columns),
        )
        tracker.add_evidence(
            {
                "missing_pct": {k: v for k, v in report.missing_summary.items() if v > 0},
                "duplicate_rows": report.duplicate_count,
                "outlier_cols": list(report.outlier_summary.keys()),
            }
        )
        tracker.set_conclusion(report.summary)

        quality_df = self.quality_checker.to_dataframe(report)
        missing_df = pd.DataFrame(
            [{"字段": k, "缺失率%": v} for k, v in report.missing_summary.items() if v > 0]
        )

        return AgentResponse(
            success=True,
            answer=report.summary + "\n\n" + "\n".join(f"- {i}" for i in report.issues),
            data=quality_df,
            quality_report=report,
            metadata={"missing_df": missing_df, "raw_df": df.head(100)},
        )

    def _handle_attribution(
        self, question: str, plan: AnalysisPlan, tracker: ProvenanceTracker,
        schema_text: str, semantic_ctx: str,
    ) -> AgentResponse:
        table = self.connector.list_tables()[0]
        df = self.connector.read_table(table)

        params = self._detect_attribution_params(question, df, schema_text)
        metric = params.get("metric")
        date_col = params.get("date_col")

        if not metric or not date_col:
            return AgentResponse(
                success=False,
                answer="无法识别归因所需的指标列或日期列，请检查数据 schema。",
                error="missing columns",
            )

        result = self.attribution.analyze(
            df,
            metric_col=metric,
            date_col=date_col,
            current_period=(params["current_start"], params["current_end"]),
            previous_period=(params["previous_start"], params["previous_end"]),
        )
        attr_df = self.attribution.to_dataframe(result)
        chart = self.chart_gen.generate(attr_df.head(15), intent="柱状图", chart_type=None)

        tracker.add_step(
            "归因分析", "python",
            f"对比 {params['previous_start']}~{params['previous_end']} vs {params['current_start']}~{params['current_end']}",
            fields_used=[metric, date_col],
        )
        for ev in result.evidence[:5]:
            tracker.add_evidence(ev)
        tracker.set_conclusion(result.conclusion)

        return AgentResponse(
            success=True,
            answer=result.conclusion,
            data=attr_df,
            chart=chart,
            metadata={"attribution": result},
        )

    def _handle_forecast(
        self, question: str, plan: AnalysisPlan, tracker: ProvenanceTracker,
        schema_text: str, semantic_ctx: str,
    ) -> AgentResponse:
        table = self.connector.list_tables()[0]
        df = self.connector.read_table(table)
        horizon = 30
        m = re.search(r"(\d+)\s*天", question)
        if m:
            horizon = int(m.group(1))

        forecast = self.forecaster.forecast(df, horizon=horizon)
        if not forecast.success:
            tracker.set_conclusion(forecast.error)
            return AgentResponse(success=False, answer=forecast.error, error=forecast.error)

        tracker.add_step(
            "预测建模", "python",
            forecast.explanation,
            fields_used=[forecast.date_col, forecast.target_col],
        )
        tracker.add_evidence({"metrics": forecast.metrics, "feature_importance": forecast.feature_importance})
        tracker.set_conclusion(forecast.explanation)

        chart_df = forecast.predictions
        chart = self.chart_gen.generate(chart_df, intent="预测趋势", x=forecast.date_col, y="predicted")

        return AgentResponse(
            success=True,
            answer=forecast.explanation,
            data=forecast.predictions,
            chart=chart,
            forecast_result=forecast,
        )

    def _handle_dashboard(
        self, question: str, plan: AnalysisPlan, tracker: ProvenanceTracker,
        schema_text: str, semantic_ctx: str,
    ) -> AgentResponse:
        config = self.dashboard_gen.auto_generate()
        tracker.add_step("生成仪表板", "dashboard", f"包含 {len(config.kpis)} 个 KPI, {len(config.charts)} 个图表")
        tracker.set_conclusion(f"已生成仪表板配置: {config.title}")

        return AgentResponse(
            success=True,
            answer=f"已自动生成仪表板「{config.title}」，包含筛选器、KPI、图表和数据表。请在仪表板 Tab 查看。",
            dashboard_config=config,
        )

    def _generate_sql(self, question: str, schema_text: str, semantic_ctx: str) -> str:
        if OPENAI_API_KEY:
            sql = self._generate_sql_llm(question, schema_text, semantic_ctx)
            if sql:
                return sql
        return self._generate_sql_rules(question)

    def _generate_sql_llm(self, question: str, schema_text: str, semantic_ctx: str) -> str | None:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
            prompt = f"""Schema:
{schema_text}

{semantic_ctx}

用户问题: {question}

生成 SQLite 兼容 SQL（双引号标识符）。只返回 SQL。"""
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "你是 SQL 专家，只输出可执行 SQL。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            sql = (resp.choices[0].message.content or "").strip()
            sql = re.sub(r"^```\w*\n?", "", sql)
            sql = re.sub(r"\n?```$", "", sql)
            return sql.strip()
        except Exception:
            return None

    def _generate_sql_rules(self, question: str) -> str:
        """Rule-based SQL for demo without LLM."""
        tables = self.connector.list_tables()
        table = tables[0]
        info = self.connector.get_table_info(table)
        cols = [c.name for c in info.columns]
        q = question.lower()

        # Gross margin by category/region
        region_col = next((c for c in cols if c.lower() in ("region", "area", "地区")), None)
        cat_col = next((c for c in cols if c.lower() in ("category", "品类", "product_category")), None)
        gmv_col = next((c for c in cols if c.lower() in ("gmv", "revenue", "sales", "amount")), None)
        cost_col = next((c for c in cols if c.lower() in ("cost", "cogs")), None)
        margin_col = next((c for c in cols if "margin" in c.lower() or "毛利率" in c), None)
        quarter_col = next((c for c in cols if c.lower() in ("quarter", "q", "季度")), None)

        if "毛利率" in question and cat_col:
            if margin_col:
                select = f'"{cat_col}", AVG("{margin_col}") AS avg_margin'
            elif gmv_col and cost_col:
                select = f'"{cat_col}", AVG(("{gmv_col}" - "{cost_col}") / NULLIF("{gmv_col}", 0)) AS gross_margin'
            else:
                select = f'"{cat_col}", COUNT(*) AS cnt'
            where = ""
            if region_col and ("华北" in question or "华东" in question):
                for r in ("华北", "华东", "华南", "华西"):
                    if r in question:
                        where = f' WHERE "{region_col}" = \'{r}\''
            if quarter_col and "q3" in q:
                where += (' AND' if where else ' WHERE') + f' "{quarter_col}" = \'Q3\''
            elif "q3" in q:
                where += (' AND' if where else ' WHERE') + " quarter = 'Q3'"
            group = f' GROUP BY "{cat_col}" ORDER BY 2 DESC'
            return f'SELECT {select} FROM "{table}"{where}{group}'

        if gmv_col and cat_col:
            return f'SELECT "{cat_col}", SUM("{gmv_col}") AS total FROM "{table}" GROUP BY "{cat_col}" ORDER BY 2 DESC'

        return f'SELECT * FROM "{table}" LIMIT 20'

    def _try_fix_sql(self, sql: str, error: str, schema_text: str) -> str | None:
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": f"SQL 执行报错:\n{error}\n\n原 SQL:\n{sql}\n\nSchema:\n{schema_text}\n\n请修复 SQL，只返回 SQL。",
                        }
                    ],
                    temperature=0.1,
                )
                fixed = (resp.choices[0].message.content or "").strip()
                fixed = re.sub(r"^```\w*\n?", "", fixed)
                fixed = re.sub(r"\n?```$", "", fixed)
                return fixed.strip() if fixed else None
            except Exception:
                pass
        return None

    def _detect_attribution_params(self, question: str, df: pd.DataFrame, schema_text: str) -> dict[str, str]:
        date_col, metric_col = self.forecaster.detect_columns(df)

        if OPENAI_API_KEY:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": f"问题: {question}\nSchema:\n{schema_text}\n\n返回 JSON: metric, date_col, current_start, current_end, previous_start, previous_end (YYYY-MM-DD)",
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                params = json.loads(resp.choices[0].message.content or "{}")
                if params.get("metric"):
                    return params
            except Exception:
                pass

        # Rule-based defaults for sample data
        df_dates = pd.to_datetime(df[date_col]) if date_col else pd.Series()
        max_date = df_dates.max()
        if "10月" in question or "oct" in question.lower():
            cur_start, cur_end = "2024-10-01", "2024-10-31"
            prev_start, prev_end = "2024-09-01", "2024-09-30"
        else:
            cur_end = max_date.strftime("%Y-%m-%d") if pd.notna(max_date) else "2024-10-31"
            cur_start = (max_date - pd.Timedelta(days=30)).strftime("%Y-%m-%d") if pd.notna(max_date) else "2024-10-01"
            prev_end = (pd.to_datetime(cur_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            prev_start = (pd.to_datetime(prev_end) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")

        return {
            "metric": metric_col or "gmv",
            "date_col": date_col or "order_date",
            "current_start": cur_start,
            "current_end": cur_end,
            "previous_start": prev_start,
            "previous_end": prev_end,
        }

    def _generate_answer(self, question: str, df: pd.DataFrame, chart: ChartResult, sql: str) -> str:
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                preview = df.head(10).to_string()
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": f"问题: {question}\n\n数据:\n{preview}\n\n图表解读: {chart.interpretation}\n\n请给出简洁分析结论，引用具体数据。",
                        }
                    ],
                    temperature=0.3,
                )
                return resp.choices[0].message.content or chart.interpretation
            except Exception:
                pass
        return f"查询完成，共 {len(df)} 行结果。\n\n{chart.interpretation}"

    @staticmethod
    def _extract_fields_from_sql(sql: str) -> list[str]:
        return list(set(re.findall(r'"(\w+)"', sql)))
