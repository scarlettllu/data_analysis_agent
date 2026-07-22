"""Time series forecasting with sklearn."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


@dataclass
class ForecastResult:
    success: bool
    predictions: pd.DataFrame | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)
    date_col: str = ""
    target_col: str = ""
    horizon: int = 30
    explanation: str = ""
    error: str = ""


class TimeSeriesForecaster:
    """MVP forecaster using lag features + GradientBoosting."""

    def detect_columns(self, df: pd.DataFrame) -> tuple[str | None, str | None]:
        date_col = None
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_col = col
                break
            if col.lower() in ("date", "order_date", "dt", "day", "日期"):
                date_col = col
                break
        if date_col is None:
            for col in df.columns:
                try:
                    pd.to_datetime(df[col].head(10))
                    date_col = col
                    break
                except (ValueError, TypeError):
                    continue

        target_col = None
        for name in ("gmv", "sales", "revenue", "quantity", "qty", "amount", "销量", "销售额"):
            for col in df.columns:
                if col.lower() == name and pd.api.types.is_numeric_dtype(df[col]):
                    target_col = col
                    break
            if target_col:
                break
        if target_col is None:
            numeric = df.select_dtypes(include="number").columns.tolist()
            target_col = numeric[0] if numeric else None

        return date_col, target_col

    def forecast(
        self,
        df: pd.DataFrame,
        date_col: str | None = None,
        target_col: str | None = None,
        horizon: int = 30,
    ) -> ForecastResult:
        try:
            date_col = date_col or self.detect_columns(df)[0]
            target_col = target_col or self.detect_columns(df)[1]
            if not date_col or not target_col:
                return ForecastResult(
                    success=False,
                    error="无法自动识别日期列或目标列，请手动指定。",
                )

            ts = df[[date_col, target_col]].copy()
            ts[date_col] = pd.to_datetime(ts[date_col])
            ts = ts.sort_values(date_col).groupby(date_col, as_index=False)[target_col].sum()

            ts["lag_1"] = ts[target_col].shift(1)
            ts["lag_7"] = ts[target_col].shift(7)
            ts["lag_14"] = ts[target_col].shift(14)
            ts["rolling_7"] = ts[target_col].rolling(7).mean()
            ts["day_of_week"] = ts[date_col].dt.dayofweek
            ts["month"] = ts[date_col].dt.month
            ts = ts.dropna()

            features = ["lag_1", "lag_7", "lag_14", "rolling_7", "day_of_week", "month"]
            X = ts[features]
            y = ts[target_col]

            if len(ts) < 20:
                return ForecastResult(success=False, error="数据量不足（需要至少 20 个时间点）。")

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            model = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            metrics = {
                "MAE": float(mean_absolute_error(y_test, y_pred)),
                "RMSE": float(np.sqrt(mean_squared_error(y_test, y_pred))),
                "R2": float(r2_score(y_test, y_pred)),
            }
            importance = dict(zip(features, model.feature_importances_.tolist()))

            # Future forecast
            last_date = ts[date_col].max()
            future_rows = []
            working = ts.copy()
            for i in range(1, horizon + 1):
                next_date = last_date + pd.Timedelta(days=i)
                last_row = working.iloc[-1]
                feat = {
                    "lag_1": last_row[target_col],
                    "lag_7": working[target_col].iloc[-7] if len(working) >= 7 else last_row[target_col],
                    "lag_14": working[target_col].iloc[-14] if len(working) >= 14 else last_row[target_col],
                    "rolling_7": working[target_col].tail(7).mean(),
                    "day_of_week": next_date.dayofweek,
                    "month": next_date.month,
                }
                pred = float(model.predict(pd.DataFrame([feat]))[0])
                std_err = metrics["MAE"]
                future_rows.append(
                    {
                        date_col: next_date,
                        "predicted": pred,
                        "lower": pred - 1.96 * std_err,
                        "upper": pred + 1.96 * std_err,
                    }
                )
                new_row = {date_col: next_date, target_col: pred, **feat}
                working = pd.concat([working, pd.DataFrame([{**new_row}])], ignore_index=True)

            predictions = pd.DataFrame(future_rows)
            top_feat = max(importance, key=importance.get)
            explanation = (
                f"使用 GradientBoosting 预测未来 {horizon} 天 {target_col}。"
                f"测试集 MAE={metrics['MAE']:,.2f}, R²={metrics['R2']:.3f}。"
                f"最重要特征: {top_feat}（重要性 {importance[top_feat]:.2f}）。"
                f"预测区间基于 ±1.96×MAE 估计。"
            )

            return ForecastResult(
                success=True,
                predictions=predictions,
                metrics=metrics,
                feature_importance=importance,
                date_col=date_col,
                target_col=target_col,
                horizon=horizon,
                explanation=explanation,
            )
        except Exception as e:
            return ForecastResult(success=False, error=str(e))
