"""Create demo SQLite database from sample_sales.csv."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "sample_sales.csv"
DB = ROOT / "data" / "demo.db"


def main() -> None:
    if not CSV.exists():
        raise FileNotFoundError(f"Run gen_sample.py first or ensure {CSV} exists")
    df = pd.read_csv(CSV)
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as conn:
        df.to_sql("sales", conn, if_exists="replace", index=False)
    print(f"Created {DB} with table 'sales' ({len(df)} rows)")


if __name__ == "__main__":
    main()
