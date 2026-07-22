"""Data connector module — unified interface for CSV, Excel, SQLite."""

from .base import BaseConnector, ColumnInfo, TableInfo
from .factory import create_connector

__all__ = ["BaseConnector", "ColumnInfo", "TableInfo", "create_connector"]
