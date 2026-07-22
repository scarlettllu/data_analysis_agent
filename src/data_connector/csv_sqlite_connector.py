"""Load uploaded CSV into in-memory SQLite — NL→SQL execution target."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from .base import BaseConnector, ColumnInfo, TableInfo


class CsvSQLiteConnector(BaseConnector):
    """CSV → pandas → SQLite (:memory:). Matches MVP: SQLite execution after upload."""

    def __init__(self, file_path: str | Path, table_name: str | None = None):
        self.file_path = Path(file_path)
        self.table_name = table_name or self._sanitize_table_name(self.file_path.stem)
        self._engine = None
        self.sqlite_mode = ":memory:"

    @property
    def execution_backend(self) -> str:
        return f"SQLite ({self.sqlite_mode})"

    def connect(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV not found: {self.file_path}")
        df = pd.read_csv(self.file_path)
        self._engine = create_engine("sqlite:///:memory:")
        df.to_sql(self.table_name, self._engine, index=False, if_exists="replace")

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def list_tables(self) -> list[str]:
        if not self._engine:
            self.connect()
        return inspect(self._engine).get_table_names()

    def get_table_info(self, table: str) -> TableInfo:
        if not self._engine:
            self.connect()
        insp = inspect(self._engine)
        cols_meta = insp.get_columns(table)
        df_sample = pd.read_sql(f'SELECT * FROM "{table}" LIMIT 100', self._engine)
        count_df = pd.read_sql(f'SELECT COUNT(*) AS cnt FROM "{table}"', self._engine)
        columns = []
        for meta in cols_meta:
            col_name = meta["name"]
            sample = df_sample[col_name].dropna().head(5).tolist() if col_name in df_sample else []
            columns.append(
                ColumnInfo(
                    name=col_name,
                    dtype=str(meta.get("type", "unknown")),
                    nullable=meta.get("nullable", True),
                    sample_values=sample,
                )
            )
        return TableInfo(
            name=table,
            columns=columns,
            row_count=int(count_df.iloc[0]["cnt"]),
            sample_rows=df_sample.head(5).to_dict(orient="records"),
        )

    def execute_query(self, sql: str) -> pd.DataFrame:
        if not self._engine:
            self.connect()
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def read_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        sql = f'SELECT * FROM "{table}"'
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.execute_query(sql)

    @staticmethod
    def _sanitize_table_name(name: str) -> str:
        safe = re.sub(r"[^\w]", "_", name)
        return safe or "uploaded_data"
