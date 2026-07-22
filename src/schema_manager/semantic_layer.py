"""Business semantic layer — map natural language terms to physical columns."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import DEFAULT_SYNONYMS
from src.data_connector.base import BaseConnector


@dataclass
class FieldMapping:
    business_term: str
    physical_column: str
    table: str
    confidence: float = 1.0


@dataclass
class SemanticLayer:
    connector: BaseConnector
    synonyms: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_SYNONYMS))
    custom_descriptions: dict[str, str] = field(default_factory=dict)

    def resolve_term(self, term: str, table: str | None = None) -> list[FieldMapping]:
        """Resolve a business term to physical columns."""
        term_lower = term.lower().strip()
        mappings: list[FieldMapping] = []
        tables = [table] if table else self.connector.list_tables()

        for tbl in tables:
            info = self.connector.get_table_info(tbl)
            col_names = {c.name.lower(): c.name for c in info.columns}

            # Direct match
            if term_lower in col_names:
                mappings.append(FieldMapping(term, col_names[term_lower], tbl, 1.0))

            # Synonym match
            for biz_term, syns in self.synonyms.items():
                all_terms = [biz_term.lower()] + [s.lower() for s in syns]
                if term_lower in all_terms or term_lower == biz_term.lower():
                    for syn in all_terms:
                        if syn in col_names:
                            conf = 0.95 if syn == term_lower else 0.85
                            mappings.append(FieldMapping(biz_term, col_names[syn], tbl, conf))

            # Fuzzy: column contains term
            for lower, original in col_names.items():
                if term_lower in lower or lower in term_lower:
                    mappings.append(FieldMapping(term, original, tbl, 0.7))

        # Deduplicate by (table, column), keep highest confidence
        seen: dict[tuple[str, str], FieldMapping] = {}
        for m in mappings:
            key = (m.table, m.physical_column)
            if key not in seen or m.confidence > seen[key].confidence:
                seen[key] = m
        return sorted(seen.values(), key=lambda x: -x.confidence)

    def extract_terms_from_query(self, query: str) -> list[str]:
        """Extract known business terms from natural language query."""
        found = []
        for term in self.synonyms:
            if term.lower() in query.lower():
                found.append(term)
        # Also extract quoted or capitalized tokens
        for m in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z_]+", query):
            if len(m) >= 2:
                found.append(m)
        return list(dict.fromkeys(found))

    def build_context_block(self) -> str:
        """Semantic context for agent prompts."""
        lines = ["## 业务语义映射"]
        for tbl in self.connector.list_tables():
            info = self.connector.get_table_info(tbl)
            lines.append(f"\n### {tbl}")
            for col in info.columns:
                desc = self.custom_descriptions.get(f"{tbl}.{col.name}", "")
                mapped_terms = []
                for biz, syns in self.synonyms.items():
                    if col.name.lower() in [s.lower() for s in syns] or col.name.lower() == biz.lower():
                        mapped_terms.append(biz)
                alias = f" (别名: {', '.join(mapped_terms)})" if mapped_terms else ""
                desc_part = f" — {desc}" if desc else ""
                lines.append(f"- {col.name}{alias}{desc_part}")
        return "\n".join(lines)
