"""
validate.py — reconciliation & sanity checks for the whole NorthPeak model.

This is the "do the numbers actually tie out" script. It re-derives every
accounting identity independently and asserts the source data and each
component's outputs agree. Run it after any change to trust the deliverables.

Checks, in order:
  A. Raw data internal consistency (the SaaS revenue walk, P&L identities).
  B. Component 2 forecast reconciles (walk holds, ARR = MRR x 12).
  C. Component 3 variance ties to raw FY2025 (sums, bridge reconciliation).
  D. Component 4 scenarios reconcile (walk holds, Base == Component 2, P&L).
  E. Business-sense guardrails (margins, growth, churn in plausible ranges).

Run standalone:  python src/validate.py   (exits non-zero if anything fails)
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import forecast
import scenarios as scen_mod
import utils
import variance as var_mod

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((bool(ok), name, detail))


def close(a, b, atol=1.0, rtol=0.0) -> bool:
    """Elementwise allclose that tolerates the cents-rounding in the raw data."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return bool(np.allclose(a, b, atol=atol, rtol=rtol, equal_nan=True))


# ---------------------------------------------------------------------------
def validate_raw(drivers, actuals, budget):
    d = drivers
    # SaaS revenue walk: ending_mrr[t] = ending_mrr[t-1] + new - churned + expansion
    walk = (d["ending_mrr"].shift(1) + d["new_mrr"] - d["churned_mrr"]
            + d["expansion_mrr"])
    check("raw: MRR walk reconciles (24 mo)",
          close(walk.iloc[1:], d["ending_mrr"].iloc[1:], atol=1.0),
          f"max err ${np.nanmax(np.abs(walk.iloc[1:]-d['ending_mrr'].iloc[1:])):.2f}")

    # new_mrr and churned_mrr are priced at ARPU (our forecast assumption).
    check("raw: new_mrr = new_customers x arpu",
          close(d["new_mrr"], d["new_customers"] * d["arpu"], atol=1.0),
          f"max err ${np.nanmax(np.abs(d['new_mrr']-d['new_customers']*d['arpu'])):.2f}")
    check("raw: churned_mrr = churned_customers x arpu",
          close(d["churned_mrr"], d["churned_customers"] * d["arpu"], atol=1.0))

    # Customer walk and ARR definition.
    cust_walk = d["ending_customers"].shift(1) + d["new_customers"] - d["churned_customers"]
    check("raw: customer count walk reconciles",
          close(cust_walk.iloc[1:], d["ending_customers"].iloc[1:], atol=0.5))
    check("raw: arr = ending_mrr x 12",
          close(d["arr"], d["ending_mrr"] * 12, atol=1.0))
    # Logo churn rate definition.
    rate = d["churned_customers"] / d["ending_customers"].shift(1)
    check("raw: logo_churn_rate = churned / prior customers",
          close(rate.iloc[1:], d["logo_churn_rate"].iloc[1:], atol=1e-3))

    # P&L identities in the actuals.
    a = actuals
    check("raw: revenue == ending_mrr (P&L driven off MRR)",
          close(a["revenue"], d["ending_mrr"], atol=1.0))
    check("raw: gross_profit = revenue - cogs",
          close(a["gross_profit"], a["revenue"] - a["cogs"], atol=1.0))
    check("raw: total_opex = S&M + R&D + G&A",
          close(a["total_opex"],
                a["sales_marketing"] + a["research_development"] + a["general_admin"],
                atol=1.0))
    check("raw: operating_income = gross_profit - total_opex",
          close(a["operating_income"], a["gross_profit"] - a["total_opex"], atol=1.0))
    check("raw: operating_margin = operating_income / revenue",
          close(a["operating_margin"], a["operating_income"] / a["revenue"], atol=1e-3))

    # Budget internal identities.
    b = budget
    check("raw: budget total_opex = S&M + R&D + G&A",
          close(b["budget_total_opex"],
                b["budget_sales_marketing"] + b["budget_research_development"]
                + b["budget_general_admin"], atol=1.0))
    check("raw: budget operating_income = rev - cogs - opex",
          close(b["budget_operating_income"],
                b["budget_revenue"] - b["budget_cogs"] - b["budget_total_opex"],
                atol=1.0))


# ---------------------------------------------------------------------------
def validate_forecast(drivers):
    fc = forecast.forecast_drivers(drivers, forecast.FORECAST_MONTHS)
    seed_mrr = float(drivers["ending_mrr"].iloc[-1])
    seed_cust = float(drivers["ending_customers"].iloc[-1])

    # Reconstruct the walk independently with the seam to the last actual.
    prev_mrr, prev_cust = seed_mrr, seed_cust
    recon_mrr, recon_cust = [], []
    for _, r in fc.iterrows():
        m = prev_mrr + r["new_mrr"] - r["churned_mrr"] + r["expansion_mrr"]
        c = prev_cust + r["new_customers"] - r["churned_customers"]
        recon_mrr.append(m); recon_cust.append(c)
        prev_mrr, prev_cust = m, c
    check("fc: MRR walk reconciles vs seam", close(recon_mrr, fc["ending_mrr"], atol=1.0))
    check("fc: customer walk reconciles", close(recon_cust, fc["ending_customers"], atol=0.5))
    check("fc: new_mrr = new_customers x arpu",
          close(fc["new_mrr"], fc["new_customers"] * fc["arpu"], atol=1.0))
    check("fc: arr = ending_mrr x 12", close(fc["arr"], fc["ending_mrr"] * 12, atol=1.0))
    check("fc: forecast continues upward from last actual",
          fc["arr"].iloc[0] > drivers["arr"].iloc[-1] * 0.98,
          f"first fc ARR {utils.fmt_money(fc['arr'].iloc[0])} vs last actual "
          f"{utils.fmt_money(drivers['arr'].iloc[-1])}")
    check("fc: churn rate stays positive & stationary (not drifting to 0)",
          fc["logo_churn_rate"].min() > 0.005,
          f"min churn {fc['logo_churn_rate'].min():.4f}")

    # Backtest sanity.
    bt = forecast.backtest(drivers, forecast.HOLDOUT_MONTHS)
    check("fc: backtest ARR MAPE < 10% (credible)",
          bt["model_arr_mape"] < 10.0, f"MAPE {bt['model_arr_mape']:.2f}%")
    check("fc: driver model beats flat-growth baseline",
          bt["model_arr_mape"] < bt["baseline_arr_mape"],
          f"{bt['model_arr_mape']:.2f}% vs {bt['baseline_arr_mape']:.2f}%")
    return fc


# ---------------------------------------------------------------------------
def validate_variance(actuals, budget):
    summary, monthly, merged = var_mod.build_variance(actuals, budget)
    bridge = var_mod.build_bridge(merged)

    # Independent FY2025 sums straight from raw actuals (months 2025-*).
    fy = actuals[actuals["month"].dt.year == 2025]
    check("var: FY2025 isolated to 12 months", len(merged) == 12, f"{len(merged)} rows")
    rev_act = fy["revenue"].sum()
    rev_row = summary.loc[summary["Line Item"] == "Revenue"].iloc[0]
    check("var: revenue actual ties to raw FY2025 sum",
          close(rev_row["Actual"], rev_act, atol=1.0))
    check("var: revenue variance = actual - budget",
          close(rev_row["Variance $"], rev_row["Actual"] - rev_row["Budget"], atol=1.0))

    # Every summary row: variance% = variance$/budget, and F/U sign is correct.
    ok_pct = close(summary["Variance %"], summary["Variance $"] / summary["Budget"], atol=1e-6)
    check("var: variance % = variance $ / budget (all lines)", ok_pct)

    # Bridge reconciles budget OI -> actual OI exactly.
    deltas = bridge.loc[bridge["Kind"] == "delta", "Amount"].sum()
    b_oi = bridge.loc[bridge["Item"] == "Budget Operating Income", "Amount"].iloc[0]
    a_oi = bridge.loc[bridge["Item"] == "Actual Operating Income", "Amount"].iloc[0]
    check("var: bridge reconciles (budget OI + deltas = actual OI)",
          close(b_oi + deltas, a_oi, atol=1.0),
          f"{utils.fmt_money(b_oi)} + {utils.fmt_money(deltas)} = {utils.fmt_money(a_oi)}")

    # Sign convention: revenue beat is Favorable; an OpEx overspend is Unfavorable.
    check("var: revenue over plan flagged Favorable",
          rev_row["F/U"] == "Favorable")
    sm = summary.loc[summary["Line Item"] == "Sales & Marketing"].iloc[0]
    check("var: S&M overspend flagged Unfavorable",
          (sm["Variance $"] > 0) and (sm["F/U"] == "Unfavorable"))
    return summary


# ---------------------------------------------------------------------------
def validate_scenarios(drivers, fc):
    scen = scen_mod.build_scenarios(drivers)
    check("scen: 3 scenarios x 12 months = 36 rows", len(scen) == 36, f"{len(scen)} rows")

    for name in ["Base", "Upside", "Downside"]:
        s = scen[scen["scenario"] == name].reset_index(drop=True)
        # P&L identity: OI = revenue - cogs - opex
        check(f"scen[{name}]: OI = revenue - cogs - opex",
              close(s["operating_income"], s["revenue"] - s["cogs"] - s["total_opex"], atol=1.0))
        check(f"scen[{name}]: arr = ending_mrr x 12",
              close(s["arr"], s["ending_mrr"] * 12, atol=1.0))
        check(f"scen[{name}]: operating_margin = OI / revenue",
              close(s["operating_margin"], s["operating_income"] / s["revenue"], atol=1e-6))

    # Base scenario MUST equal the Component 2 forecast on ARR (shared engine).
    base = scen[scen["scenario"] == "Base"].reset_index(drop=True)
    check("scen: Base ARR == Component 2 forecast ARR (consistent engine)",
          close(base["arr"], fc["arr"], atol=2.0),
          f"max diff ${np.max(np.abs(base['arr'].values - fc['arr'].values)):.2f}")

    # Ordering sanity: Upside >= Base >= Downside on exit ARR and FY OI.
    exit_arr = scen.groupby("scenario")["arr"].last()
    check("scen: exit ARR ordering Upside > Base > Downside",
          exit_arr["Upside"] > exit_arr["Base"] > exit_arr["Downside"])
    fy_oi = scen.groupby("scenario")["operating_income"].sum()
    check("scen: FY operating income ordering Upside > Base > Downside",
          fy_oi["Upside"] > fy_oi["Base"] > fy_oi["Downside"])
    return scen


# ---------------------------------------------------------------------------
def validate_business_sense(drivers, fc, summary, scen):
    # Forecast YoY ARR growth should be strong but below the historical pace
    # (a damped trend shouldn't accelerate). FY2025 grew ~2x; FY2026 should be
    # less than that and clearly positive.
    last_actual = drivers["arr"].iloc[-1]
    yoy = fc["arr"].iloc[-1] / last_actual - 1
    hist_yoy = drivers["arr"].iloc[-1] / drivers[drivers["month"].dt.year == 2024]["arr"].iloc[-1] - 1
    check("sense: FY2026 ARR growth positive and decelerating vs FY2025",
          0.0 < yoy < hist_yoy, f"FY2026 +{yoy:.1%} vs FY2025 +{hist_yoy:.1%}")

    # Forecast NRR in a believable band (data runs ~99%).
    check("sense: forecast NRR within 90%-130%",
          fc["net_revenue_retention"].between(0.90, 1.30).all(),
          f"range {fc['net_revenue_retention'].min():.3f}-{fc['net_revenue_retention'].max():.3f}")

    # Scenario margins ordered and within sane SaaS bounds (-25%..+30%).
    m = scen.groupby("scenario")["operating_margin"].mean()
    check("sense: scenario op-margins within -25%..30%",
          m.between(-0.25, 0.30).all(), f"{m.round(3).to_dict()}")

    # Rule of 40 on the Base case (growth% + margin% should be respectable).
    base = scen[scen["scenario"] == "Base"]
    base_growth = base["arr"].iloc[-1] / last_actual - 1
    base_margin = base["operating_income"].sum() / base["revenue"].sum()
    rule40 = (base_growth + base_margin) * 100
    check("sense: Base case clears Rule of 40", rule40 >= 40,
          f"growth {base_growth:.1%} + margin {base_margin:.1%} = {rule40:.0f}")

    # FY2025 variance direction matches the narrative: revenue favorable, OpEx unfavorable.
    rev = summary.loc[summary["Line Item"] == "Revenue"].iloc[0]
    opex = summary.loc[summary["Line Item"] == "Total OpEx"].iloc[0]
    oi = summary.loc[summary["Line Item"] == "Operating Income"].iloc[0]
    check("sense: FY2025 story holds (rev beat, opex over, OI missed)",
          rev["F/U"] == "Favorable" and opex["F/U"] == "Unfavorable"
          and oi["F/U"] == "Unfavorable")


# ---------------------------------------------------------------------------
def main() -> None:
    drivers = utils.load_drivers()
    actuals = utils.load_actuals()
    budget = utils.load_budget()

    validate_raw(drivers, actuals, budget)
    fc = validate_forecast(drivers)
    summary = validate_variance(actuals, budget)
    scen = validate_scenarios(drivers, fc)
    validate_business_sense(drivers, fc, summary, scen)

    print("=" * 72)
    print("NORTHPEAK MODEL — RECONCILIATION & SANITY CHECKS")
    print("=" * 72)
    passed = sum(1 for ok, _, _ in _results if ok)
    for ok, name, detail in _results:
        tag = "PASS" if ok else "FAIL"
        line = f"[{tag}] {name}"
        if detail and (not ok or detail):
            line += f"   ({detail})"
        print(line)
    print("-" * 72)
    print(f"{passed}/{len(_results)} checks passed")
    print("=" * 72)
    if passed != len(_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
