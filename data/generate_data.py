"""
NorthPeak Analytics — Synthetic SaaS FP&A Dataset Generator
Generates realistic subscription-business data for an FP&A project:
  - Monthly customer/subscription activity (new, churn, expansion)
  - Actuals: revenue + OpEx by category (24 months)
  - Budget: the plan set at start of FY2025 (12 months)
Story: NorthPeak is a B2B SaaS company. FY2024 was actuals-only history;
FY2025 has both a Budget (the plan) and Actuals (what happened) so we can
do budget-vs-actuals variance analysis.
"""
import numpy as np
import pandas as pd

np.random.seed(42)  # reproducible

# ----------------------------------------------------------------------
# 1. TIMELINE
# ----------------------------------------------------------------------
months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")  # 24 months
fy2025 = pd.date_range("2025-01-01", "2025-12-01", freq="MS")   # budget period

# ----------------------------------------------------------------------
# 2. CUSTOMER / SUBSCRIPTION DRIVERS (this is the "engine" of the model)
# ----------------------------------------------------------------------
# Starting state Jan 2024
start_customers = 220
arpu = 1150           # avg revenue per account / month (starting)
monthly_churn = 0.018 # logo churn ~1.8%/mo
expansion_rate = 0.010  # net dollar expansion from existing base

rows = []
customers = start_customers
cum_mrr = customers * arpu

for i, m in enumerate(months):
    # New customer adds: growing sales motion, with seasonality + noise
    base_new = 14 + i * 0.9                       # acquisition ramps over time
    seasonal = 4 * np.sin((i % 12) / 12 * 2*np.pi)  # Q4 push, summer dip
    new_custs = max(0, int(round(base_new + seasonal + np.random.normal(0, 3))))

    churn_custs = int(round(customers * (monthly_churn + np.random.normal(0, 0.003))))
    churn_custs = max(0, churn_custs)

    customers = customers + new_custs - churn_custs

    # ARPU drifts up slightly (price increases + tier upgrades)
    arpu_m = arpu * (1 + 0.0025) ** i * (1 + np.random.normal(0, 0.01))

    new_mrr = new_custs * arpu_m
    churned_mrr = churn_custs * arpu_m
    expansion_mrr = cum_mrr * (expansion_rate + np.random.normal(0, 0.002))
    cum_mrr = cum_mrr + new_mrr - churned_mrr + expansion_mrr

    rows.append({
        "month": m,
        "new_customers": new_custs,
        "churned_customers": churn_custs,
        "ending_customers": customers,
        "arpu": round(arpu_m, 2),
        "new_mrr": round(new_mrr, 2),
        "churned_mrr": round(churned_mrr, 2),
        "expansion_mrr": round(expansion_mrr, 2),
        "ending_mrr": round(cum_mrr, 2),
        "arr": round(cum_mrr * 12, 2),
    })

subs = pd.DataFrame(rows)
subs["logo_churn_rate"] = (subs["churned_customers"] /
                           subs["ending_customers"].shift(1)).round(4)
subs["net_revenue_retention"] = (
    (subs["ending_mrr"] - subs["new_mrr"]) /
    subs["ending_mrr"].shift(1)).round(4)

# ----------------------------------------------------------------------
# 3. ACTUALS P&L (revenue + OpEx) — driven off the subscription engine
# ----------------------------------------------------------------------
pl = subs[["month", "ending_mrr"]].copy()
pl["revenue"] = pl["ending_mrr"]

# COGS (hosting, support) ~ 22% of revenue
pl["cogs"] = (pl["revenue"] * (0.22 + np.random.normal(0, 0.01, len(pl)))).round(2)
pl["gross_profit"] = pl["revenue"] - pl["cogs"]

# OpEx categories scale with stage of business + noise
n = len(pl)
pl["sales_marketing"] = (pl["revenue"] * (0.40 + np.random.normal(0, 0.02, n))).round(2)
pl["research_development"] = (pl["revenue"] * (0.25 + np.random.normal(0, 0.015, n))).round(2)
pl["general_admin"] = (pl["revenue"] * (0.14 + np.random.normal(0, 0.01, n))).round(2)
pl["total_opex"] = pl[["sales_marketing", "research_development", "general_admin"]].sum(axis=1)
pl["operating_income"] = pl["gross_profit"] - pl["total_opex"]
pl["operating_margin"] = (pl["operating_income"] / pl["revenue"]).round(4)
pl = pl.drop(columns=["ending_mrr"])

# ----------------------------------------------------------------------
# 4. BUDGET (FY2025 plan) — set in Dec 2024, slightly optimistic vs reality
# ----------------------------------------------------------------------
# Budget assumed smoother, more aggressive revenue, tighter cost control
dec24_rev = pl.loc[pl["month"] == "2024-12-01", "revenue"].values[0]
budget_rows = []
plan_rev = dec24_rev
for i, m in enumerate(fy2025):
    plan_rev = plan_rev * (1 + 0.035)  # plan: 3.5% MoM growth (optimistic)
    budget_rows.append({
        "month": m,
        "budget_revenue": round(plan_rev, 2),
        "budget_cogs": round(plan_rev * 0.20, 2),          # plan tighter COGS
        "budget_sales_marketing": round(plan_rev * 0.38, 2),
        "budget_research_development": round(plan_rev * 0.24, 2),
        "budget_general_admin": round(plan_rev * 0.13, 2),
    })
budget = pd.DataFrame(budget_rows)
budget["budget_total_opex"] = budget[["budget_sales_marketing",
    "budget_research_development", "budget_general_admin"]].sum(axis=1)
budget["budget_operating_income"] = (budget["budget_revenue"]
    - budget["budget_cogs"] - budget["budget_total_opex"]).round(2)

# ----------------------------------------------------------------------
# 5. WRITE TO EXCEL (multi-tab workbook)
# ----------------------------------------------------------------------
with pd.ExcelWriter("/home/claude/northpeak_data.xlsx", engine="openpyxl") as xl:
    subs.to_excel(xl, sheet_name="Subscription_Drivers", index=False)
    pl.to_excel(xl, sheet_name="Actuals_PL", index=False)
    budget.to_excel(xl, sheet_name="Budget_FY2025", index=False)

# Also CSVs for GitHub / portability
subs.to_csv("/home/claude/subscription_drivers.csv", index=False)
pl.to_csv("/home/claude/actuals_pl.csv", index=False)
budget.to_csv("/home/claude/budget_fy2025.csv", index=False)

print("Generated NorthPeak dataset")
print(f"  Subscription drivers: {len(subs)} months")
print(f"  Actuals P&L:          {len(pl)} months")
print(f"  Budget FY2025:        {len(budget)} months")
print(f"\nDec 2025 ending ARR:  ${subs['arr'].iloc[-1]:,.0f}")
print(f"Dec 2025 customers:   {subs['ending_customers'].iloc[-1]:,}")
print(f"Avg logo churn:       {subs['logo_churn_rate'].mean():.2%}")
