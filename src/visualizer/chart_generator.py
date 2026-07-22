"""Chart generation with Plotly and auto interpretation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .chart_selector import ChartSelector, ChartType


@dataclass
class ChartResult:
    figure: go.Figure | None
    chart_type: ChartType
    interpretation: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ChartGenerator:
    def __init__(self):
        self.selector = ChartSelector()

    def generate(
        self,
        df: pd.DataFrame,
        intent: str = "",
        x: str | None = None,
        y: str | None = None,
        chart_type: ChartType | None = None,
    ) -> ChartResult:
        if df is None or df.empty:
            return ChartResult(None, ChartType.TABLE, "无数据可供可视化。")

        # Forecast result with confidence bands
        if {"predicted", "lower", "upper"}.issubset(df.columns):
            date_col = x or next((c for c in df.columns if c not in ("predicted", "lower", "upper")), None)
            fig = go.Figure()
            if date_col:
                fig.add_trace(go.Scatter(x=df[date_col], y=df["upper"], mode="lines", line=dict(width=0), showlegend=False))
                fig.add_trace(go.Scatter(x=df[date_col], y=df["lower"], mode="lines", fill="tonexty", fillcolor="rgba(59,130,246,0.15)", line=dict(width=0), name="95% 区间"))
                fig.add_trace(go.Scatter(x=df[date_col], y=df["predicted"], mode="lines+markers", name="预测值", line=dict(color="#2563eb")))
            fig.update_layout(title="预测趋势（含置信区间）", hovermode="x unified")
            interpretation = self._interpret(df, ChartType.LINE, date_col, "predicted")
            return ChartResult(fig, ChartType.LINE, interpretation, metadata={"x": date_col, "y": "predicted", "rows": len(df)})

        if chart_type is None:
            chart_type, auto_x, auto_y = self.selector.select(df, intent)
            x = x or auto_x
            y = y or auto_y
        else:
            if x is None or y is None:
                _, auto_x, auto_y = self.selector.select(df, intent)
                x = x or auto_x
                y = y or auto_y

        fig = self._build_figure(df, chart_type, x, y)
        interpretation = self._interpret(df, chart_type, x, y)
        return ChartResult(
            figure=fig,
            chart_type=chart_type,
            interpretation=interpretation,
            metadata={"x": x, "y": y, "rows": len(df)},
        )

    def _build_figure(
        self, df: pd.DataFrame, chart_type: ChartType, x: str | None, y: str | None
    ) -> go.Figure | None:
        if chart_type == ChartType.TABLE:
            return None
        if chart_type == ChartType.LINE and x and y:
            return px.line(df, x=x, y=y, title=f"{y} 趋势")
        if chart_type == ChartType.BAR and x and y:
            return px.bar(df, x=x, y=y, title=f"按 {x} 的 {y}")
        if chart_type == ChartType.PIE and x and y:
            return px.pie(df, names=x, values=y, title=f"{y} 占比（按 {x}）")
        if chart_type == ChartType.SCATTER and x and y:
            return px.scatter(df, x=x, y=y, title=f"{x} vs {y}")
        if chart_type == ChartType.HEATMAP and x and y:
            numeric = df.select_dtypes(include="number").columns.tolist()
            if len(numeric) >= 2:
                pivot = df.pivot_table(index=x, values=numeric[:5], aggfunc="mean")
                return px.imshow(pivot, title="热力图", aspect="auto")
        return px.bar(df, x=x or df.columns[0], y=y or df.columns[-1])

    def _interpret(
        self, df: pd.DataFrame, chart_type: ChartType, x: str | None, y: str | None
    ) -> str:
        if df.empty:
            return "数据为空。"
        parts = [f"共 {len(df)} 条记录。"]

        if y and y in df.columns and pd.api.types.is_numeric_dtype(df[y]):
            total = df[y].sum()
            max_row = df.loc[df[y].idxmax()]
            min_row = df.loc[df[y].idxmin()]
            parts.append(f"{y} 合计 {total:,.2f}。")
            if x and x in df.columns:
                parts.append(
                    f"最高: {x}={max_row[x]} ({max_row[y]:,.2f})；"
                    f"最低: {x}={min_row[x]} ({min_row[y]:,.2f})。"
                )
            avg = df[y].mean()
            parts.append(f"均值 {avg:,.2f}。")

        if chart_type == ChartType.LINE and x and y and x in df.columns:
            sorted_df = df.sort_values(x)
            if len(sorted_df) >= 2:
                first_val = sorted_df[y].iloc[0]
                last_val = sorted_df[y].iloc[-1]
                change = last_val - first_val
                pct = (change / first_val * 100) if first_val else 0
                parts.append(f"从 {sorted_df[x].iloc[0]} 到 {sorted_df[x].iloc[-1]}，{y} 变化 {change:+,.2f}（{pct:+.1f}%）。")

        return " ".join(parts)
