"""MySQL / PostgreSQL connector stubs — extend for production."""
from __future__ import annotations

from abc import abstractmethod

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from .base import BaseConnector, ColumnInfo, TableInfo


class SQLAlchemyConnector(BaseConnector):
    """Shared logic for SQLAlchemy-backed databases."""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self._engine = None

    def connect(self) -> None:
        self._engine = create_engine(self.connection_url)

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
        df_sample = pd.read_sql(f"SELECT * FROM {table} LIMIT 100", self._engine)
        count_df = pd.read_sql(f"SELECT COUNT(*) AS cnt FROM {table}", self._engine)
        columns = [
            ColumnInfo(
                name=m["name"],
                dtype=str(m.get("type", "unknown")),
                nullable=m.get("nullable", True),
                sample_values=df_sample[m["name"]].dropna().head(5).tolist()
                if m["name"] in df_sample
                else [],
            )
            for m in cols_meta
        ]
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
        sql = f"SELECT * FROM {table}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.execute_query(sql)


class MySQLConnector(SQLAlchemyConnector):
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        super().__init__(url)


class PostgreSQLConnector(SQLAlchemyConnector):
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
        super().__init__(url)
