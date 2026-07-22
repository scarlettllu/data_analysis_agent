"""Generate human-readable schema summaries from connectors."""
from __future__ import annotations

from typing import Any

from src.data_connector.base import BaseConnector, TableInfo


class SchemaReader:
    def __init__(self, connector: BaseConnector):
        self.connector = connector

    def get_schema_summary(self) -> dict[str, Any]:
        schemas = self.connector.get_all_schemas()
        return {
            "tables": [self._table_to_dict(t, info) for t, info in schemas.items()],
            "table_count": len(schemas),
        }

    def get_schema_text(self) -> str:
        """Compact text for LLM context."""
        lines = []
        for table, info in self.connector.get_all_schemas().items():
            lines.append(f"表: {table} ({info.row_count} 行)")
            for col in info.columns:
                samples = ", ".join(str(v) for v in col.sample_values[:3])
                lines.append(f"  - {col.name} ({col.dtype}) 样例: [{samples}]")
        return "\n".join(lines)

    @staticmethod
    def _table_to_dict(name: str, info: TableInfo) -> dict[str, Any]:
        return {
            "name": name,
            "row_count": info.row_count,
            "columns": [
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "nullable": c.nullable,
                    "sample_values": c.sample_values[:5],
                }
                for c in info.columns
            ],
            "sample_rows": info.sample_rows[:3],
        }
