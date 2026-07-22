"""Generate sample sales data for demo."""
import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)
dates = pd.date_range("2024-07-01", "2024-10-31", freq="D")
regions = ["华北", "华东", "华南", "华西"]
categories = ["手机", "电脑", "家电", "穿戴"]
channels = ["线上", "线下", "分销"]
user_types = ["新客", "老客", "VIP"]

rows = []
for d in dates:
    for _ in range(int(np.random.randint(8, 15))):
        gmv = float(np.random.uniform(5000, 50000))
        cost = gmv * float(np.random.uniform(0.55, 0.85))
        rows.append(
            {
                "order_date": d.strftime("%Y-%m-%d"),
                "quarter": f"Q{(d.month - 1) // 3 + 1}",
                "region": str(np.random.choice(regions)),
                "category": str(np.random.choice(categories)),
                "channel": str(np.random.choice(channels)),
                "user_type": str(np.random.choice(user_types)),
                "gmv": round(gmv, 2),
                "cost": round(cost, 2),
                "quantity": int(np.random.randint(1, 20)),
            }
        )

df = pd.DataFrame(rows)
df["gross_margin"] = ((df["gmv"] - df["cost"]) / df["gmv"]).round(4)

oct_mask = (
    (pd.to_datetime(df["order_date"]) >= "2024-10-01")
    & (df["channel"] == "线上")
    & (df["region"] == "华北")
)
df.loc[oct_mask, "gmv"] = (df.loc[oct_mask, "gmv"] * 0.7).round(2)

out = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out, index=False)
print(f"Generated {len(df)} rows -> {out}")
