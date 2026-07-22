"""AutoML module — forecasting and regression."""

from .forecaster import ForecastResult, TimeSeriesForecaster
from .quality_checker import QualityReport, QualityChecker

__all__ = ["TimeSeriesForecaster", "ForecastResult", "QualityChecker", "QualityReport"]
