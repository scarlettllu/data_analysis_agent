"""Automatic attribution analysis — dimension drill-down and contribution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ContributionItem:
    dimension: str
    value: str
    current_value: float
    previous_value: float
    change: float
    change_pct: float
    contribution_pct: float


@dataclass
class AttributionResult:
    metric: str
    overall_change: float
    overall_change_pct: float
    contributions: list[ContributionItem] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    conclusion: str = ""


class AttributionAnalyzer:
    """Compute dimension contributions for metric changes."""

    DEFAULT_DIMENSIONS = ["channel", "region", "category", "user_type", "platform"]

    def analyze(
        self,
        df: pd.DataFrame,
        metric_col: str,
        date_col: str,
        current_period: tuple[str, str],
        previous_period: tuple[str, str],
        dimensions: list[str] | None = None,
    ) -> AttributionResult:
        dims = dimensions or [d for d in self.DEFAULT_DIMENSIONS if d in df.columns]
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])

        cur_start, cur_end = pd.to_datetime(current_period[0]), pd.to_datetime(current_period[1])
        prev_start, prev_end = pd.to_datetime(previous_period[0]), pd.to_datetime(previous_period[1])

        cur_df = df[(df[date_col] >= cur_start) & (df[date_col] <= cur_end)]
        prev_df = df[(df[date_col] >= prev_start) & (df[date_col] <= prev_end)]

        cur_total = float(cur_df[metric_col].sum())
        prev_total = float(prev_df[metric_col].sum())
        overall_change = cur_total - prev_total
        overall_change_pct = (overall_change / prev_total * 100) if prev_total else 0.0

        contributions: list[ContributionItem] = []
        evidence: list[dict[str, Any]] = []

        for dim in dims:
            if dim not in df.columns:
                continue
            cur_grp = cur_df.groupby(dim)[metric_col].sum()
            prev_grp = prev_df.groupby(dim)[metric_col].sum()
            all_keys = set(cur_grp.index) | set(prev_grp.index)

            for key in all_keys:
                cur_val = float(cur_grp.get(key, 0))
                prev_val = float(prev_grp.get(key, 0))
                change = cur_val - prev_val
                change_pct = (change / prev_val * 100) if prev_val else 0.0
                contrib_pct = (change / overall_change * 100) if overall_change else 0.0
                item = ContributionItem(
                    dimension=dim,
                    value=str(key),
                    current_value=cur_val,
                    previous_value=prev_val,
                    change=change,
                    change_pct=change_pct,
                    contribution_pct=contrib_pct,
                )
                contributions.append(item)
                evidence.append(
                    {
                        "dimension": dim,
                        "value": str(key),
                        "current": cur_val,
                        "previous": prev_val,
                        "change": change,
                        "contribution_pct": round(contrib_pct, 2),
                    }
                )

        contributions.sort(key=lambda x: abs(x.contribution_pct), reverse=True)
        top = contributions[:5]
        conclusion_parts = []
        for item in top:
            direction = "下降" if item.change < 0 else "上升"
            conclusion_parts.append(
                f"{item.dimension}={item.value} 贡献 {item.contribution_pct:.1f}%"
                f"（{direction} {abs(item.change):,.0f}，从 {item.previous_value:,.0f} 到 {item.current_value:,.0f}）"
            )

        conclusion = (
            f"{metric_col} 整体变化 {overall_change:+,.0f}（{overall_change_pct:+.1f}%）。"
            + "主要驱动因素: " + "; ".join(conclusion_parts)
            if conclusion_parts
            else f"{metric_col} 变化 {overall_change:+,.0f}，未发现显著维度差异。"
        )

        return AttributionResult(
            metric=metric_col,
            overall_change=overall_change,
            overall_change_pct=overall_change_pct,
            contributions=contributions[:20],
            evidence=evidence[:20],
            conclusion=conclusion,
        )

    def to_dataframe(self, result: AttributionResult) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "维度": c.dimension,
                    "取值": c.value,
                    "当期": c.current_value,
                    "上期": c.previous_value,
                    "变化": c.change,
                    "变化率%": round(c.change_pct, 2),
                    "贡献度%": round(c.contribution_pct, 2),
                }
                for c in result.contributions
            ]
        )
