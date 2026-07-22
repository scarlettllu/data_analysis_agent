"""Data quality checking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class QualityReport:
    total_rows: int
    total_columns: int
    missing_summary: dict[str, float]
    duplicate_count: int
    outlier_summary: dict[str, Any]
    type_issues: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    score: float = 100.0
    summary: str = ""


class QualityChecker:
    def check(self, df: pd.DataFrame) -> QualityReport:
        missing = (df.isnull().sum() / len(df) * 100).to_dict()
        duplicate_count = int(df.duplicated().sum())
        outlier_summary: dict[str, Any] = {}
        issues: list[str] = []

        type_issues: dict[str, str] = {}
        for col in df.columns:
            series = df[col].dropna()
            if series.empty:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            if series.dtype == object:
                numeric_like = pd.to_numeric(series, errors="coerce")
                ratio = numeric_like.notna().mean()
                if ratio > 0.8:
                    type_issues[col] = f"应为数值型，当前为文本（{ratio*100:.0f}% 可解析为数字）"
                elif any(k in col.lower() for k in ("date", "dt", "time", "日期")):
                    parsed = pd.to_datetime(series, errors="coerce")
                    if parsed.notna().mean() > 0.8:
                        type_issues[col] = "应为日期型，当前为文本"

        numeric_cols = df.select_dtypes(include="number").columns
        for col in numeric_cols:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = df[(df[col] < lower) | (df[col] > upper)]
            if len(outliers) > 0:
                outlier_summary[col] = {
                    "count": len(outliers),
                    "pct": round(len(outliers) / len(df) * 100, 2),
                }

        for col, pct in missing.items():
            if pct > 30:
                issues.append(f"字段 {col} 缺失率 {pct:.1f}%（偏高）")
            elif pct > 0:
                issues.append(f"字段 {col} 缺失率 {pct:.1f}%")

        if duplicate_count > 0:
            issues.append(f"发现 {duplicate_count} 条重复记录")

        for col, info in outlier_summary.items():
            if info["pct"] > 5:
                issues.append(f"字段 {col} 异常值占比 {info['pct']}%")

        for col, msg in type_issues.items():
            issues.append(f"字段 {col} 类型问题: {msg}")

        score = 100.0
        score -= min(30, sum(p for p in missing.values()) / len(missing) if missing else 0)
        score -= min(20, duplicate_count / len(df) * 100 if len(df) else 0)
        score -= min(20, sum(v["pct"] for v in outlier_summary.values()))
        score -= min(10, len(type_issues) * 3)
        score = max(0, round(score, 1))

        summary = (
            f"数据质量评分 {score}/100。"
            f"共 {len(df)} 行 {len(df.columns)} 列，"
            f"重复 {duplicate_count} 条。"
            + (" 主要问题: " + "; ".join(issues[:5]) if issues else " 未发现严重问题。")
        )

        return QualityReport(
            total_rows=len(df),
            total_columns=len(df.columns),
            missing_summary={k: round(v, 2) for k, v in missing.items()},
            duplicate_count=duplicate_count,
            outlier_summary=outlier_summary,
            type_issues=type_issues,
            issues=issues,
            score=score,
            summary=summary,
        )

    def to_dataframe(self, report: QualityReport) -> pd.DataFrame:
        rows = [
            {"检查项": "总行数", "结果": report.total_rows},
            {"检查项": "总列数", "结果": report.total_columns},
            {"检查项": "重复行", "结果": report.duplicate_count},
            {"检查项": "质量评分", "结果": report.score},
        ]
        for col, pct in report.missing_summary.items():
            if pct > 0:
                rows.append({"检查项": f"缺失-{col}", "结果": f"{pct}%"})
        for col, msg in report.type_issues.items():
            rows.append({"检查项": f"类型-{col}", "结果": msg})
        return pd.DataFrame(rows)
