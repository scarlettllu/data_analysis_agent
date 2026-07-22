"""Abstract data connector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ColumnInfo:
    name: str
    dtype: str
    nullable: bool = True
    sample_values: list[Any] = field(default_factory=list)
    description: str = ""


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = field(default_factory=list)


class BaseConnector(ABC):
    """Base class for all data connectors."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Return available table names."""

    @abstractmethod
    def get_table_info(self, table: str) -> TableInfo:
        """Return schema info for a table."""

    @abstractmethod
    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return DataFrame."""

    @abstractmethod
    def read_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        """Read full or limited table."""

    def get_all_schemas(self) -> dict[str, TableInfo]:
        return {t: self.get_table_info(t) for t in self.list_tables()}

    def __enter__(self) -> BaseConnector:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
