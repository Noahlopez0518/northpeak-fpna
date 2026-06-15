"""
dashboard.py — Component 5 (data): build a Power BI-ready dataset.

Power BI likes a single tidy/long fact table: one row per (date, series,
metric, value). That shape lets a single table drive every visual via slicers
— KPI cards, the ARR trend, the scenario fan — without reshaping in DAX.

This script assembles that table from the SAME in-memory builders the other
components use (not by re-reading their CSVs), so the dashboard can never drift
out of sync with the analysis. It also emits a small bridge table for the
variance waterfall visual.

OUTPUTS:
    outputs/dashboard_data.csv     (tidy/long: date, series, metric, value, unit)
    outputs/dashboard_bridge.csv   (operating-income waterfall steps)

Run standalone:  python src/dashboard.py
"""
from __future__ import annotations

import sys

import pandas as pd

import forecast
import scenarios as scen_mod
import utils
import variance as var_mod

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Every metric we expose, mapped to a unit so Power BI can format cards/axes.
UNIT = {
    "arr": "currency", "mrr": "currency", "revenue": "currency",
    "cogs": "currency", "gross_profit": "currency", "sales_marketing": "currency",
    "research_development": "currency", "general_admin": "currency",
    "total_opex": "currency", "operating_income": "currency",
    "expansion_mrr": "currency", "new_mrr": "currency", "churned_mrr": "currency",
    "arpu": "currency",
    "operating_margin": "percent", "logo_churn_rate": "percent",
    "net_revenue_retention": "percent",
    "new_customers": "count", "churned_customers": "count",
    "ending_customers": "count",
}


def _melt(df: pd.DataFrame, series: str, metrics: list[str]) -> pd.DataFrame:
    """Melt a wide month-indexed frame into long [date, series, metric, value, unit]."""
    keep = ["month"] + [m for m in metrics if m in df.columns]
    long = df[keep].melt(id_vars="month", var_name="metric", value_name="value")
    long.insert(1, "series", series)
    long = long.rename(columns={"month": "date"})
    long["unit"] = long["metric"].map(UNIT)
    return long


def build_dashboard_data(drivers, actuals, budget) -> pd.DataFrame:
    parts = []

    # --- Actual (24 months of history) ---
    act = drivers.merge(actuals, on="month", how="inner")
    act = act.rename(columns={"ending_mrr": "mrr"})
    act["revenue"] = act["mrr"]  # P&L revenue == ending MRR
    parts.append(_melt(act, "Actual", [
        "arr", "mrr", "revenue", "cogs", "gross_profit", "sales_marketing",
        "research_development", "general_admin", "total_opex", "operating_income",
        "operating_margin", "new_customers", "churned_customers",
        "ending_customers", "logo_churn_rate", "net_revenue_retention",
        # MRR movement (the leaky-bucket story): new + expansion - churned each month
        "new_mrr", "expansion_mrr", "churned_mrr",
    ]))

    # --- Budget (FY2025 plan) ---
    b = budget.rename(columns={c: c.replace("budget_", "") for c in budget.columns
                               if c != "month"}).copy()
    b["gross_profit"] = b["revenue"] - b["cogs"]
    b["operating_margin"] = b["operating_income"] / b["revenue"]
    b["mrr"] = b["revenue"]
    b["arr"] = b["revenue"] * 12
    parts.append(_melt(b, "Budget", [
        "arr", "mrr", "revenue", "cogs", "gross_profit", "total_opex",
        "operating_income", "operating_margin",
    ]))

    # --- Forecast (Component 2 base driver forecast, FY2026) ---
    fc = forecast.forecast_drivers(drivers, forecast.FORECAST_MONTHS)
    fc = fc.rename(columns={"ending_mrr": "mrr"})
    fc["revenue"] = fc["mrr"]
    parts.append(_melt(fc, "Forecast", [
        "arr", "mrr", "revenue", "new_customers", "churned_customers",
        "ending_customers", "logo_churn_rate", "arpu", "expansion_mrr",
        "net_revenue_retention",
    ]))

    # --- Scenarios (FY2026 Base / Upside / Downside) ---
    scen = scen_mod.build_scenarios(drivers)
    scen = scen.rename(columns={"ending_mrr": "mrr"})
    for name in ["Base", "Upside", "Downside"]:
        s = scen[scen["scenario"] == name]
        parts.append(_melt(s, f"Scenario: {name}", [
            "arr", "mrr", "revenue", "cogs", "total_opex", "operating_income",
            "operating_margin", "new_customers", "churned_customers",
            "ending_customers",
        ]))

    out = pd.concat(parts, ignore_index=True)
    out = out.dropna(subset=["value"])
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out = out.sort_values(["series", "metric", "date"]).reset_index(drop=True)
    return out[["date", "series", "metric", "value", "unit"]]


def build_bridge_table(actuals, budget) -> pd.DataFrame:
    _, _, merged = var_mod.build_variance(actuals, budget)
    bridge = var_mod.build_bridge(merged)
    bridge = bridge.reset_index(drop=True)
    bridge.insert(0, "step_order", range(1, len(bridge) + 1))
    return bridge.rename(columns={"Item": "label", "Amount": "amount", "Kind": "kind"})


def main() -> None:
    utils.ensure_dirs()
    drivers = utils.load_drivers()
    actuals = utils.load_actuals()
    budget = utils.load_budget()

    data = build_dashboard_data(drivers, actuals, budget)
    bridge = build_bridge_table(actuals, budget)

    data.to_csv(utils.OUTPUTS / "dashboard_data.csv", index=False)
    bridge.to_csv(utils.OUTPUTS / "dashboard_bridge.csv", index=False)

    print("=" * 64)
    print("COMPONENT 5 (data) — POWER BI EXPORT")
    print("=" * 64)
    print(f"dashboard_data.csv : {len(data):,} rows (tidy/long)")
    print(f"  series : {', '.join(sorted(data['series'].unique()))}")
    print(f"  metrics: {data['metric'].nunique()} distinct")
    print(f"  dates  : {data['date'].min()} -> {data['date'].max()}")
    print(f"dashboard_bridge.csv : {len(bridge)} waterfall steps")
    print("=" * 64)


if __name__ == "__main__":
    main()
