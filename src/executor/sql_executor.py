"""SQL execution with error explanation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.data_connector.base import BaseConnector


@dataclass
class ExecutionResult:
    success: bool
    data: pd.DataFrame | None = None
    sql: str = ""
    error: str = ""
    error_hint: str = ""
    row_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SQLExecutor:
    def __init__(self, connector: BaseConnector):
        self.connector = connector

    def execute(self, sql: str) -> ExecutionResult:
        try:
            df = self.connector.execute_query(sql)
            return ExecutionResult(
                success=True,
                data=df,
                sql=sql,
                row_count=len(df),
            )
        except Exception as e:
            hint = self._explain_error(str(e), sql)
            return ExecutionResult(success=False, sql=sql, error=str(e), error_hint=hint)

    def _explain_error(self, error: str, sql: str) -> str:
        err_lower = error.lower()
        hints = []
        if "no such column" in err_lower or "column" in err_lower and "not found" in err_lower:
            tables = self.connector.list_tables()
            if tables:
                info = self.connector.get_table_info(tables[0])
                cols = [c.name for c in info.columns]
                hints.append(f"可用字段: {', '.join(cols)}")
        if "no such table" in err_lower:
            hints.append(f"可用表: {', '.join(self.connector.list_tables())}")
        if "syntax error" in err_lower:
            hints.append("请检查 SQL 语法，SQLite 使用双引号引用表名/字段名。")
        if not hints:
            hints.append("建议检查表名、字段名和数据类型是否匹配 schema。")
        return "; ".join(hints)
