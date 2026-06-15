"""
scenarios.py - Component 4: Scenario analysis (Base / Upside / Downside) for FY2026.

WHY THIS MATTERS:
    A single forecast is a guess; a scenario set is a decision tool. The board
    doesn't want one number - they want the range, and the *levers* that move
    NorthPeak between a great year and a painful one. This module flexes the
    same driver-based engine from Component 2 with a small, clearly-labeled set
    of assumptions, so anyone can see "if sales lands 20% more logos and we hold
    churn at 1.3%, here's the ARR and operating income."

THE FOUR LEVERS WE FLEX (the things leadership can actually influence):
    1. New-customer pace   - go-to-market effectiveness (multiplier on base)
    2. Logo churn rate      - retention / product stickiness (absolute monthly %)
    3. ARPU growth premium  - pricing & packaging (extra monthly drift)
    4. Expansion pace       - upsell into the base (multiplier on base)
  Plus two margin levers:
    5. COGS % of revenue    - hosting/support efficiency
    6. OpEx % of revenue    - hiring & spend discipline (operating leverage)

Base case reproduces the Component 2 forecast; Upside/Downside flex from there.

OUTPUTS:
    outputs/scenarios.csv                 (tidy/long: one row per scenario-month)
    outputs/figures/scenario_arr.png      (ARR fan + FY2026 operating income)

Run standalone:  python src/scenarios.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import forecast  # reuse the Component 2 driver engine for the base levers
import utils

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FORECAST_MONTHS = 12  # FY2026

# ---------------------------------------------------------------------------
# SCENARIO ASSUMPTIONS - toggle these. Everything downstream is derived.
#
#   new_customer_pace : multiplier on the base-forecast new-logo count
#   logo_churn_rate   : absolute monthly logo churn (overrides base ~1.74%)
#   arpu_growth_prem  : EXTRA monthly ARPU growth on top of the base drift
#   expansion_pace    : multiplier on base expansion MRR (upsell strength)
#   cogs_pct          : COGS as a % of revenue (gross-margin lever)
#   opex_pct          : total OpEx as a % of revenue (operating-leverage lever)
#
# Reference points: FY2025 actuals ran COGS ~22% and OpEx ~79% of revenue
# (which is why FY2025 posted an operating loss). Base assumes modest operating
# leverage as the company scales; Upside assumes discipline + leverage; Downside
# assumes costs stay heavy.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "Downside": dict(new_customer_pace=0.75, logo_churn_rate=0.024,
                     arpu_growth_prem=-0.002, expansion_pace=0.70,
                     cogs_pct=0.24, opex_pct=0.80),
    "Base":     dict(new_customer_pace=1.00, logo_churn_rate=0.0174,
                     arpu_growth_prem=0.000, expansion_pace=1.00,
                     cogs_pct=0.222, opex_pct=0.74),
    "Upside":   dict(new_customer_pace=1.20, logo_churn_rate=0.013,
                     arpu_growth_prem=0.002, expansion_pace=1.30,
                     cogs_pct=0.21, opex_pct=0.66),
}

SCENARIO_COLORS = {
    "Base": utils.COLORS["actual"],
    "Upside": utils.COLORS["favorable"],
    "Downside": utils.COLORS["unfavorable"],
}


def run_scenario(name: str, params: dict, base_levers: pd.DataFrame,
                 seed_customers: float, seed_mrr: float) -> pd.DataFrame:
    """
    Apply a scenario's assumptions to the base driver levers, then roll the
    SaaS revenue walk forward and layer on a ratio-based P&L. Returns a tidy
    monthly frame for this scenario.
    """
    months = base_levers["month"].values
    n = len(base_levers)

    prev_customers = float(seed_customers)
    prev_mrr = float(seed_mrr)
    rows = []
    for t in range(n):
        # --- flex the levers ---
        new_cust = float(round(base_levers["new_customers"].iloc[t] * params["new_customer_pace"]))
        churn_rate = params["logo_churn_rate"]
        churned = float(round(churn_rate * prev_customers))
        # ARPU: base forecast path compounded by the scenario's extra drift.
        arpu_t = float(base_levers["arpu"].iloc[t]) * (1 + params["arpu_growth_prem"]) ** (t + 1)
        expansion = float(base_levers["expansion_mrr"].iloc[t]) * params["expansion_pace"]

        # --- revenue walk (identical mechanics to Component 2) ---
        new_mrr = new_cust * arpu_t
        churned_mrr = churned * arpu_t
        ending_mrr = prev_mrr + new_mrr - churned_mrr + expansion
        ending_customers = prev_customers + new_cust - churned

        # --- ratio-based P&L: margin is the scenario's cost-discipline story ---
        revenue = ending_mrr
        cogs = params["cogs_pct"] * revenue
        total_opex = params["opex_pct"] * revenue
        operating_income = revenue - cogs - total_opex

        rows.append({
            "scenario": name,
            "month": months[t],
            "new_customers": new_cust,
            "churned_customers": churned,
            "ending_customers": ending_customers,
            "ending_mrr": ending_mrr,
            "arr": ending_mrr * 12.0,
            "revenue": revenue,
            "cogs": cogs,
            "total_opex": total_opex,
            "operating_income": operating_income,
            "operating_margin": operating_income / revenue if revenue else np.nan,
        })
        prev_customers, prev_mrr = ending_customers, ending_mrr

    return pd.DataFrame(rows)


def build_scenarios(drivers: pd.DataFrame) -> pd.DataFrame:
    """Run all three cases off a shared base set of driver levers."""
    base_levers = forecast.forecast_drivers(drivers, FORECAST_MONTHS)
    seed_customers = float(drivers["ending_customers"].iloc[-1])
    seed_mrr = float(drivers["ending_mrr"].iloc[-1])

    frames = [run_scenario(name, params, base_levers, seed_customers, seed_mrr)
              for name, params in SCENARIOS.items()]
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------
def plot_scenarios(drivers: pd.DataFrame, scen: pd.DataFrame, path):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    utils.apply_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.2),
                                   gridspec_kw={"width_ratios": [1.7, 1]})

    # --- Left: ARR fan chart ---
    hist = drivers.set_index("month")["arr"].iloc[-6:]  # recent actuals for context
    ax1.plot(hist.index, hist.values, color="#444", lw=2.2, label="Actual ARR")

    pivot = scen.pivot(index="month", columns="scenario", values="arr")
    pivot.index = pd.to_datetime(pivot.index)
    # Shade the Downside-Upside range as the outcome cone.
    ax1.fill_between(pivot.index, pivot["Downside"], pivot["Upside"],
                     color=utils.COLORS["band"], alpha=0.45, zorder=1,
                     label="Outcome range")
    for name in ["Upside", "Base", "Downside"]:
        # bridge from last actual into FY2026 so lines start at the seam
        x = [hist.index[-1]] + list(pivot.index)
        y = [hist.values[-1]] + list(pivot[name].values)
        ax1.plot(x, y, color=SCENARIO_COLORS[name], lw=2.4,
                 marker="o", ms=3, label=name, zorder=3)
        ax1.annotate(utils.fmt_money(pivot[name].iloc[-1]),
                     xy=(pivot.index[-1], pivot[name].iloc[-1]),
                     xytext=(8, 0), textcoords="offset points", va="center",
                     fontsize=9, fontweight="bold", color=SCENARIO_COLORS[name])
    ax1.set_title("FY2026 ARR - Scenario Fan")
    ax1.set_ylabel("Annual Recurring Revenue")
    ax1.yaxis.set_major_formatter(FuncFormatter(utils.fmt_money))
    ax1.legend(loc="upper left", fontsize=9)
    ax1.margins(x=0.12)

    # --- Right: full-year FY2026 operating income by scenario ---
    oi = (scen.groupby("scenario")["operating_income"].sum()
          .reindex(["Downside", "Base", "Upside"]))
    colors = [SCENARIO_COLORS[s] for s in oi.index]
    bars = ax2.bar(oi.index, oi.values, color=colors, width=0.6, zorder=3)
    ax2.axhline(0, color="#444", lw=0.8)
    ax2.yaxis.set_major_formatter(FuncFormatter(utils.fmt_money))
    ax2.set_title("FY2026 Operating Income")
    for b, v in zip(bars, oi.values):
        ax2.text(b.get_x() + b.get_width() / 2, v + np.sign(v) * 0.02 * max(abs(oi)),
                 utils.fmt_money(v), ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=10, fontweight="bold")
    ax2.margins(y=0.18)

    fig.suptitle("NorthPeak FY2026 Scenario Analysis", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    utils.ensure_dirs()
    drivers = utils.load_drivers()
    scen = build_scenarios(drivers)

    scen.to_csv(utils.OUTPUTS / "scenarios.csv", index=False)
    plot_scenarios(drivers, scen, utils.FIGURES / "scenario_arr.png")

    start_arr = float(drivers["arr"].iloc[-1])
    print("=" * 70)
    print("COMPONENT 4 - FY2026 SCENARIO ANALYSIS")
    print("=" * 70)
    print(f"Starting point (Dec-2025 actual ARR): {utils.fmt_money(start_arr)}\n")
    print(f"{'Scenario':<10}{'Exit ARR':>12}{'ARR Growth':>12}"
          f"{'FY26 Op Inc':>14}{'Op Margin':>11}")
    print("-" * 59)
    for name in ["Upside", "Base", "Downside"]:
        s = scen[scen["scenario"] == name]
        exit_arr = float(s["arr"].iloc[-1])
        fy_oi = float(s["operating_income"].sum())
        fy_rev = float(s["revenue"].sum())
        margin = fy_oi / fy_rev
        print(f"{name:<10}{utils.fmt_money(exit_arr):>12}"
              f"{(exit_arr/start_arr - 1):>11.1%}"
              f"{utils.fmt_money(fy_oi):>14}{margin:>11.1%}")
    print("-" * 59)
    spread_lo = float(scen[scen.scenario == "Downside"]["arr"].iloc[-1])
    spread_hi = float(scen[scen.scenario == "Upside"]["arr"].iloc[-1])
    print(f"\nFY2026 exit-ARR range: {utils.fmt_money(spread_lo)} - "
          f"{utils.fmt_money(spread_hi)} "
          f"(spread {utils.fmt_money(spread_hi - spread_lo)})")
    print(f"\nWrote: outputs/scenarios.csv")
    print(f"Wrote: outputs/figures/scenario_arr.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
