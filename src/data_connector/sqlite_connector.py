"""SQLite database connector."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from .base import BaseConnector, ColumnInfo, TableInfo


class SQLiteConnector(BaseConnector):
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._engine = None

    def connect(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite DB not found: {self.db_path}")
        self._engine = create_engine(f"sqlite:///{self.db_path}")

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def list_tables(self) -> list[str]:
        if not self._engine:
            self.connect()
        insp = inspect(self._engine)
        return insp.get_table_names()

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
