"""Global configuration for the Data Analysis Agent."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Business synonym defaults (extend via schema_manager)
DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "销售额": ["revenue", "amount", "gmv", "sales", "sale_amount", "total_amount"],
    "毛利率": ["gross_margin", "margin_rate", "profit_margin", "margin"],
    "销量": ["quantity", "qty", "units", "sales_qty"],
    "日期": ["date", "order_date", "created_at", "dt", "day"],
    "地区": ["region", "area", "district", "zone"],
    "品类": ["category", "product_category", "cat"],
    "渠道": ["channel", "source", "platform"],
    "用户类型": ["user_type", "customer_type", "segment"],
    "GMV": ["gmv", "total_gmv", "gross_merchandise_value"],
    "成本": ["cost", "cogs", "unit_cost"],
    "利润": ["profit", "net_profit", "gross_profit"],
}
