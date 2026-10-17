"""
generate_sample_data.py
Creates data/sample_business_data.xlsx with realistic time-series data
and injected anomalies for testing.

Run:  python generate_sample_data.py
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

random.seed(42)

# ── Date range ─────────────────────────────────────────────────────────────────
dates = pd.date_range("2022-01-01", periods=36, freq="MS")   # 3 years monthly

# ── Base patterns + injected anomalies ────────────────────────────────────────
base_revenue = [
    95_000 + i * 2_000 + random.randint(-3_000, 3_000)
    for i in range(36)
]
# Inject: sudden drop at month 20 (Aug 2023)
base_revenue[19] = int(base_revenue[18] * 0.38)   # -62%
# Inject: spike at month 30 (Jun 2024)
base_revenue[29] = int(base_revenue[28] * 1.85)   # +85%

base_orders = [
    480 + i * 6 + random.randint(-20, 20)
    for i in range(36)
]
# Drop mirrors revenue drop
base_orders[19] = int(base_orders[18] * 0.42)

base_expenses = [
    58_000 + i * 800 + random.randint(-1_000, 1_000)
    for i in range(36)
]
# Gradual unfavourable trend: expenses accelerate from month 24
for i in range(24, 36):
    base_expenses[i] = int(base_expenses[i] * 1.04)

base_visitors = [
    9_500 + i * 150 + random.randint(-500, 500)
    for i in range(36)
]
# Inject: visitor spike at month 25 (Jan 2024)
base_visitors[24] = int(base_visitors[23] * 3.2)   # +220%

base_conversion = [
    round(2.5 + random.uniform(-0.3, 0.3), 2)
    for _ in range(36)
]
# Conversion drops after visitor spike (dilution)
base_conversion[24] = round(0.9 + random.uniform(-0.1, 0.1), 2)
base_conversion[25] = round(1.1 + random.uniform(-0.1, 0.1), 2)

base_inventory = [
    1_200 + random.randint(-50, 50)
    for _ in range(36)
]
# Inventory runs low around month 19–20
base_inventory[18] = 320
base_inventory[19] = 95   # near stockout

df = pd.DataFrame({
    "date": dates,
    "revenue_usd": base_revenue,
    "orders": base_orders,
    "expenses_usd": base_expenses,
    "website_visitors": base_visitors,
    "conversion_rate_pct": base_conversion,
    "inventory_units": base_inventory,
})

out = Path("data") / "sample_business_data.xlsx"
out.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(out, index=False, sheet_name="Monthly_KPIs")
print(f"Sample dataset written to: {out}")
print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
print("  Injected anomalies:")
print(f"    - Revenue drop at {dates[19].date()} (index 19): {base_revenue[19]:,}")
print(f"    - Revenue spike at {dates[29].date()} (index 29): {base_revenue[29]:,}")
print(f"    - Visitor spike at {dates[24].date()} (index 24): {base_visitors[24]:,}")
print(f"    - Inventory near-zero at {dates[19].date()}: {base_inventory[19]} units")
print(f"    - Gradual expense inflation from {dates[24].date()}")
