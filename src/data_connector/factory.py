"""Connector factory."""
from __future__ import annotations

from pathlib import Path

from .base import BaseConnector
from .csv_sqlite_connector import CsvSQLiteConnector
from .excel_connector import ExcelConnector
from .sqlite_connector import SQLiteConnector


def create_connector(source: str | Path, **kwargs) -> BaseConnector:
    path = Path(source)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return CsvSQLiteConnector(path, table_name=kwargs.get("table_name"))
    if suffix in (".xlsx", ".xls"):
        return ExcelConnector(path, sheet_name=kwargs.get("sheet_name", 0))
    if suffix in (".db", ".sqlite", ".sqlite3"):
        return SQLiteConnector(path)

    raise ValueError(f"Unsupported data source: {source}")
