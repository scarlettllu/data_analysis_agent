"""Automatic chart type selection based on data shape."""
from __future__ import annotations

from enum import Enum

import pandas as pd


class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"


class ChartSelector:
    def select(self, df: pd.DataFrame, intent: str = "") -> tuple[ChartType, str | None, str | None]:
        if df is None or df.empty:
            return ChartType.TABLE, None, None

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        datetime_cols = [
            c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])
        ]
        if not datetime_cols:
            for c in df.columns:
                if df[c].dtype == object:
                    try:
                        pd.to_datetime(df[c].head(20))
                        datetime_cols.append(c)
                    except (ValueError, TypeError):
                        pass

        intent_lower = intent.lower()
        if "占比" in intent or "比例" in intent or "pie" in intent_lower:
            if cat_cols and numeric_cols:
                return ChartType.PIE, cat_cols[0], numeric_cols[0]
        if "趋势" in intent or "forecast" in intent_lower or "预测" in intent:
            if datetime_cols and numeric_cols:
                return ChartType.LINE, datetime_cols[0], numeric_cols[0]
        if "相关" in intent or "scatter" in intent_lower:
            if len(numeric_cols) >= 2:
                return ChartType.SCATTER, numeric_cols[0], numeric_cols[1]
        if "热力" in intent or "heatmap" in intent_lower:
            if len(numeric_cols) >= 2 and cat_cols:
                return ChartType.HEATMAP, cat_cols[0], numeric_cols[0]

        if datetime_cols and numeric_cols:
            return ChartType.LINE, datetime_cols[0], numeric_cols[0]
        if cat_cols and numeric_cols:
            if len(df) <= 8:
                return ChartType.PIE, cat_cols[0], numeric_cols[0]
            return ChartType.BAR, cat_cols[0], numeric_cols[0]
        if len(numeric_cols) >= 2:
            return ChartType.SCATTER, numeric_cols[0], numeric_cols[1]
        return ChartType.TABLE, None, None
