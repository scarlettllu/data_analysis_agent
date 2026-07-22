"""Generate Streamlit dashboard configurations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.data_connector.base import BaseConnector
from src.visualizer.chart_generator import ChartGenerator


@dataclass
class DashboardWidget:
    widget_type: str  # kpi | chart | table | filter
    title: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardConfig:
    title: str
    filters: list[DashboardWidget] = field(default_factory=list)
    kpis: list[DashboardWidget] = field(default_factory=list)
    charts: list[DashboardWidget] = field(default_factory=list)
    tables: list[DashboardWidget] = field(default_factory=list)


class DashboardGenerator:
    def __init__(self, connector: BaseConnector):
        self.connector = connector
        self.chart_gen = ChartGenerator()

    def auto_generate(self, table: str | None = None) -> DashboardConfig:
        tables = self.connector.list_tables()
        table = table or tables[0]
        info = self.connector.get_table_info(table)
        df = self.connector.read_table(table, limit=5000)

        numeric = [c.name for c in info.columns if "int" in c.dtype or "float" in c.dtype]
        cats = [c.name for c in info.columns if c.name not in numeric]

        filters = []
        for cat in cats[:3]:
            unique = df[cat].dropna().unique()
            if len(unique) <= 20:
                filters.append(
                    DashboardWidget("filter", cat, {"column": cat, "options": unique.tolist()})
                )

        kpis = []
        for num in numeric[:4]:
            kpis.append(
                DashboardWidget("kpi", num, {"column": num, "agg": "sum", "value": float(df[num].sum())})
            )

        charts = []
        if cats and numeric:
            charts.append(
                DashboardWidget(
                    "chart",
                    f"{numeric[0]} by {cats[0]}",
                    {"x": cats[0], "y": numeric[0], "chart_type": "bar"},
                )
            )
        date_cols = [c for c in df.columns if "date" in c.lower() or "dt" in c.lower()]
        if date_cols and numeric:
            charts.append(
                DashboardWidget(
                    "chart",
                    f"{numeric[0]} 趋势",
                    {"x": date_cols[0], "y": numeric[0], "chart_type": "line"},
                )
            )

        tables = [DashboardWidget("table", table, {"columns": [c.name for c in info.columns]})]

        return DashboardConfig(
            title=f"{table} 经营仪表板",
            filters=filters,
            kpis=kpis,
            charts=charts,
            tables=tables,
        )

    def render_data(
        self, config: DashboardConfig, table: str, filter_values: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        df = self.connector.read_table(table)
        if filter_values:
            for col, val in filter_values.items():
                if val and val != "全部" and col in df.columns:
                    df = df[df[col] == val]
        return df
