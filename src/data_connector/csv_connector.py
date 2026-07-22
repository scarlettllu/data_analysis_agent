"""CSV file connector."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .base import BaseConnector, ColumnInfo, TableInfo


class CSVConnector(BaseConnector):
    def __init__(self, file_path: str | Path, table_name: str | None = None):
        self.file_path = Path(file_path)
        self.table_name = table_name or self.file_path.stem
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV not found: {self.file_path}")
        self._conn = duckdb.connect(":memory:")
        path = str(self.file_path).replace("\\", "/")
        self._conn.execute(
            f"CREATE OR REPLACE VIEW {self._quote(self.table_name)} AS "
            f"SELECT * FROM read_csv_auto('{path}')"
        )

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
        count = self.execute_query(f"SELECT COUNT(*) AS cnt FROM {self._quote(table)}")
        row_count = int(count.iloc[0]["cnt"])
        return TableInfo(
            name=table,
            columns=columns,
            row_count=row_count,
            sample_rows=df.head(5).to_dict(orient="records"),
        )

    def execute_query(self, sql: str) -> pd.DataFrame:
        if not self._conn:
            self.connect()
        return self._conn.execute(sql).fetchdf()

    def read_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        sql = f"SELECT * FROM {self._quote(table)}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.execute_query(sql)

    @staticmethod
    def _quote(name: str) -> str:
        return f'"{name}"'
