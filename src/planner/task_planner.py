"""Multi-step task planning for complex analysis questions."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


class TaskType(str, Enum):
    QUERY = "query"
    QUALITY = "quality"
    ATTRIBUTION = "attribution"
    FORECAST = "forecast"
    DASHBOARD = "dashboard"
    GENERAL = "general"


@dataclass
class AnalysisStep:
    step_id: int
    description: str
    action: str  # sql | python | visualize | report
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisPlan:
    task_type: TaskType
    question: str
    steps: list[AnalysisStep]
    rationale: str = ""


class TaskPlanner:
    """Plan multi-step analysis from natural language."""

    ATTRIBUTION_KEYWORDS = ["为什么", "原因", "下降", "上升", "归因", "贡献"]
    FORECAST_KEYWORDS = ["预测", "forecast", "未来", "趋势"]
    QUALITY_KEYWORDS = ["质量", "缺失", "异常", "重复", "空值"]
    DASHBOARD_KEYWORDS = ["仪表板", "dashboard", "看板", "面板"]

    def plan(self, question: str, schema_text: str, semantic_context: str = "") -> AnalysisPlan:
        task_type = self._detect_task_type(question)

        if OPENAI_API_KEY:
            llm_plan = self._plan_with_llm(question, schema_text, semantic_context, task_type)
            if llm_plan:
                return llm_plan

        return self._plan_rule_based(question, task_type, schema_text)

    def _detect_task_type(self, question: str) -> TaskType:
        q = question.lower()
        if any(k in question for k in self.ATTRIBUTION_KEYWORDS):
            return TaskType.ATTRIBUTION
        if any(k in question for k in self.FORECAST_KEYWORDS):
            return TaskType.FORECAST
        if any(k in question for k in self.QUALITY_KEYWORDS):
            return TaskType.QUALITY
        if any(k in question for k in self.DASHBOARD_KEYWORDS):
            return TaskType.DASHBOARD
        if any(w in q for w in ["查询", "统计", "多少", "select", "各"]):
            return TaskType.QUERY
        return TaskType.GENERAL

    def _plan_rule_based(self, question: str, task_type: TaskType, schema_text: str) -> AnalysisPlan:
        steps: list[AnalysisStep] = []

        if task_type == TaskType.ATTRIBUTION:
            steps = [
                AnalysisStep(1, "获取基准期与对比期总体指标", "sql", {"focus": "overall"}),
                AnalysisStep(2, "按渠道维度下钻", "sql", {"dimension": "channel"}),
                AnalysisStep(3, "按地区维度下钻", "sql", {"dimension": "region"}),
                AnalysisStep(4, "按品类维度下钻", "sql", {"dimension": "category"}),
                AnalysisStep(5, "计算各维度贡献度", "python", {"action": "contribution"}),
                AnalysisStep(6, "生成归因可视化", "visualize", {"chart": "waterfall"}),
                AnalysisStep(7, "输出证据链结论", "report", {}),
            ]
        elif task_type == TaskType.FORECAST:
            steps = [
                AnalysisStep(1, "识别日期列与目标列", "python", {"action": "detect_columns"}),
                AnalysisStep(2, "数据预处理与特征工程", "python", {"action": "preprocess"}),
                AnalysisStep(3, "训练预测模型", "python", {"action": "train"}),
                AnalysisStep(4, "生成预测结果与评估指标", "python", {"action": "predict"}),
                AnalysisStep(5, "可视化预测曲线", "visualize", {"chart": "line"}),
            ]
        elif task_type == TaskType.QUALITY:
            steps = [
                AnalysisStep(1, "统计缺失值比例", "python", {"check": "missing"}),
                AnalysisStep(2, "检测重复记录", "python", {"check": "duplicate"}),
                AnalysisStep(3, "识别异常值", "python", {"check": "outlier"}),
                AnalysisStep(4, "生成质量报告", "report", {}),
            ]
        elif task_type == TaskType.DASHBOARD:
            steps = [
                AnalysisStep(1, "分析数据结构确定 KPI", "python", {"action": "detect_kpi"}),
                AnalysisStep(2, "生成核心指标查询", "sql", {}),
                AnalysisStep(3, "构建仪表板页面", "dashboard", {}),
            ]
        else:
            steps = [
                AnalysisStep(1, "理解问题并生成 SQL", "sql", {"question": question}),
                AnalysisStep(2, "执行查询", "sql", {"execute": True}),
                AnalysisStep(3, "自动可视化", "visualize", {}),
                AnalysisStep(4, "生成解读", "report", {}),
            ]

        return AnalysisPlan(
            task_type=task_type,
            question=question,
            steps=steps,
            rationale=f"基于规则识别任务类型: {task_type.value}",
        )

    def _plan_with_llm(
        self, question: str, schema_text: str, semantic_context: str, task_type: TaskType
    ) -> AnalysisPlan | None:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
            prompt = f"""你是数据分析 Agent 的任务规划器。根据用户问题和 schema 制定多步分析计划。

用户问题: {question}
任务类型: {task_type.value}

Schema:
{schema_text}

{semantic_context}

返回 JSON:
{{
  "rationale": "规划理由",
  "steps": [
    {{"step_id": 1, "description": "...", "action": "sql|python|visualize|report|dashboard", "params": {{}}}}
  ]
}}"""
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            steps = [
                AnalysisStep(
                    s.get("step_id", i + 1),
                    s.get("description", ""),
                    s.get("action", "sql"),
                    s.get("params", {}),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            return AnalysisPlan(
                task_type=task_type,
                question=question,
                steps=steps,
                rationale=data.get("rationale", ""),
            )
        except Exception:
            return None
