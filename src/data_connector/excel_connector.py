"""Excel file connector."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .base import BaseConnector, ColumnInfo, TableInfo


class ExcelConnector(BaseConnector):
    def __init__(self, file_path: str | Path, sheet_name: str | int = 0):
        self.file_path = Path(file_path)
        self.sheet_name = sheet_name
        self._df: pd.DataFrame | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None
        self.table_name = self._resolve_table_name()

    def _resolve_table_name(self) -> str:
        if isinstance(self.sheet_name, str):
            return self.sheet_name.replace(" ", "_")
        return f"{self.file_path.stem}_sheet{self.sheet_name}"

    def connect(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Excel not found: {self.file_path}")
        self._df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
        self._conn = duckdb.connect(":memory:")
        self._conn.register(self.table_name, self._df)

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def list_tables(self) -> list[str]:
        return [self.table_name]

    def get_table_info(self, table: str) -> TableInfo:
        df = self.read_table(table, limit=100)
        columns = []
        for col in df.columns:
            sample = df[col].dropna().head(5).tolist()
            columns.append(
                ColumnInfo(
                    name=col,
                    dtype=str(df[col].dtype),
                    nullable=bool(df[col].isna().any()),
                    sample_values=sample,
                )
            )
        return TableInfo(
            name=table,
            columns=columns,
            row_count=len(df) if self._df is not None else 0,
            sample_rows=df.head(5).to_dict(orient="records"),
        )

    def execute_query(self, sql: str) -> pd.DataFrame:
        if not self._conn:
            self.connect()
        return self._conn.execute(sql).fetchdf()

    def read_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        sql = f'SELECT * FROM "{table}"'
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.execute_query(sql)
