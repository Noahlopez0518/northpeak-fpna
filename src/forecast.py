"""
forecast.py - Component 2: Driver-based revenue forecast for NorthPeak Analytics.

WHY DRIVER-BASED (and not a flat growth %):
    A SaaS revenue number is the *output* of an operating engine, not an input.
    Each month's recurring revenue walks forward as:

        ending_mrr[t] = ending_mrr[t-1]
                        + new_mrr[t]        (new_customers x arpu)
                        - churned_mrr[t]    (churned_customers x arpu)
                        + expansion_mrr[t]  (upsell from the existing base)

    So instead of fitting a line to ARR, we forecast the four levers a CFO can
    actually pull - new customer pace, logo churn, ARPU, and expansion - then
    roll them up. The forecast stays explainable: every dollar traces to a
    driver, and the scenario engine (Component 4) can flex those same levers.

WHAT THIS SCRIPT DOES:
    1. Forecasts each driver for FY2026 (12 months) with Holt's damped-trend
       exponential smoothing (statsmodels), with safe fallbacks.
    2. Rolls the drivers up into MRR / ARR via the SaaS revenue walk above.
    3. BACKTESTS the whole pipeline: holds out the last 6 months of actuals,
       forecasts them, and reports MAPE vs. a naive flat-growth baseline.
    4. Writes outputs/forecast_fy2026.csv and a forecast chart.

Run standalone:  python src/forecast.py
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

import utils

# Statsmodels is chatty about convergence / frequency on short series; the
# fallbacks below handle anything that genuinely fails, so quiet the noise.
warnings.filterwarnings("ignore")

# The four operating levers we forecast, plus the churn *rate* which we model
# directly (more stable than raw churned-customer counts, and it scales the
# churn to the size of the base automatically).
HOLDOUT_MONTHS = 6        # backtest window (brief asks for 3-6)
FORECAST_MONTHS = 12      # FY2026


# ---------------------------------------------------------------------------
# Driver-level forecasting
# ---------------------------------------------------------------------------
def _to_series(values: pd.Series) -> pd.Series:
    """Return a month-start indexed float series so statsmodels has a freq."""
    s = values.astype(float).copy()
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp(how="start")
    s = s.asfreq("MS")
    return s


def forecast_series(values: pd.Series, periods: int,
                    trend: str | None = "add", damped: bool = True,
                    floor: float | None = None) -> np.ndarray:
    """
    Forecast one driver `periods` months ahead.

    Default model is Holt's linear trend with damping - appropriate for short
    (24-point) monthly SaaS series that trend but shouldn't extrapolate to the
    moon. Falls back to a drift/mean forecast if the optimiser can't fit.
    """
    s = _to_series(values)
    fitted = None
    if len(s) >= 5:
        try:
            # statsmodels forbids damped_trend without a trend, so only damp
            # when we actually asked for a trend. trend=None gives simple
            # exponential smoothing -> a flat (level) forecast, which is what
            # we want for a stationary series like the logo churn rate.
            model = ExponentialSmoothing(
                s, trend=trend, damped_trend=(damped and trend is not None),
                seasonal=None, initialization_method="estimated",
            ).fit()
            fitted = np.asarray(model.forecast(periods), dtype=float)
        except Exception:
            fitted = None

    if fitted is None or not np.all(np.isfinite(fitted)):
        # Fallback: linear drift from the average recent month-over-month change.
        recent = s.values
        drift = np.mean(np.diff(recent[-6:])) if len(recent) >= 2 else 0.0
        fitted = recent[-1] + drift * np.arange(1, periods + 1)

    if floor is not None:
        fitted = np.maximum(fitted, floor)
    return fitted


def forecast_drivers(drivers: pd.DataFrame, periods: int) -> pd.DataFrame:
    """
    Forecast each operating lever, then roll them up into the full driver/MRR
    table via the SaaS revenue walk. `drivers` is the history we train on.
    """
    d = drivers.set_index("month")
    last_month = d.index.max()
    future_idx = pd.date_range(
        last_month + pd.offsets.MonthBegin(1), periods=periods, freq="MS"
    )

    # --- forecast the levers ------------------------------------------------
    # New customers: trending up -> damped Holt. Floor at 0 (can't be negative).
    new_customers = forecast_series(d["new_customers"], periods, trend="add",
                                    damped=True, floor=0.0)
    # Logo churn rate: roughly stationary (~1.7%) -> level-only smoothing (mean
    # reverting). Modeling the *rate* lets churn scale with the customer base.
    churn_rate = forecast_series(d["logo_churn_rate"].dropna(), periods,
                                 trend=None, floor=0.0)
    # ARPU: slow drift -> damped Holt.
    arpu = forecast_series(d["arpu"], periods, trend="add", damped=True,
                           floor=0.0)
    # Expansion MRR: noisy but growing with the base -> damped Holt.
    expansion_mrr = forecast_series(d["expansion_mrr"], periods, trend="add",
                                    damped=True, floor=0.0)

    # --- roll up the revenue walk, month by month ---------------------------
    prev_customers = float(d["ending_customers"].iloc[-1])
    prev_mrr = float(d["ending_mrr"].iloc[-1])

    rows = []
    for i in range(periods):
        nc = float(round(new_customers[i]))
        arpu_t = float(arpu[i])
        # Churned customers derived from the rate applied to the prior base.
        churned = float(round(churn_rate[i] * prev_customers))
        new_mrr = nc * arpu_t
        churned_mrr = churned * arpu_t
        exp_mrr = float(expansion_mrr[i])

        ending_mrr = prev_mrr + new_mrr - churned_mrr + exp_mrr
        ending_customers = prev_customers + nc - churned
        # NRR = how the existing base alone evolved this month (expansion net of
        # churn), before new logos. >100% is best-in-class.
        nrr = (prev_mrr + exp_mrr - churned_mrr) / prev_mrr if prev_mrr else np.nan

        rows.append({
            "month": future_idx[i],
            "new_customers": nc,
            "churned_customers": churned,
            "ending_customers": ending_customers,
            "logo_churn_rate": float(churn_rate[i]),
            "arpu": arpu_t,
            "new_mrr": new_mrr,
            "churned_mrr": churned_mrr,
            "expansion_mrr": exp_mrr,
            "ending_mrr": ending_mrr,
            "arr": ending_mrr * 12.0,
            "net_revenue_retention": nrr,
        })
        prev_customers, prev_mrr = ending_customers, ending_mrr

    return pd.DataFrame(rows)


def baseline_flat_growth(drivers: pd.DataFrame, periods: int) -> pd.DataFrame:
    """
    Naive strawman the brief warns against: project ARR with a single flat
    month-over-month growth rate (the average historical MRR growth). No
    drivers, no explainability - the credibility benchmark to beat.
    """
    d = drivers.set_index("month")
    mrr = d["ending_mrr"].astype(float)
    avg_growth = float(mrr.pct_change().dropna().mean())
    last_month = d.index.max()
    future_idx = pd.date_range(
        last_month + pd.offsets.MonthBegin(1), periods=periods, freq="MS"
    )
    last_mrr = float(mrr.iloc[-1])
    ending_mrr = last_mrr * (1 + avg_growth) ** np.arange(1, periods + 1)
    return pd.DataFrame({
        "month": future_idx,
        "ending_mrr": ending_mrr,
        "arr": ending_mrr * 12.0,
    })


# ---------------------------------------------------------------------------
# Backtest - the credibility step
# ---------------------------------------------------------------------------
def backtest(drivers: pd.DataFrame, holdout: int = HOLDOUT_MONTHS) -> dict:
    """
    Hold out the last `holdout` months, forecast them from history only, and
    score the driver model vs. the flat-growth baseline on the held-out actuals.
    Reports MAPE at the headline (ARR) level and per-driver.
    """
    train = drivers.iloc[:-holdout].copy()
    test = drivers.iloc[-holdout:].copy()

    fc = forecast_drivers(train, holdout)
    base = baseline_flat_growth(train, holdout)

    a_arr = test["arr"].values
    metrics = {
        "holdout": holdout,
        "train_end": train["month"].max(),
        "test_start": test["month"].min(),
        "test_end": test["month"].max(),
        # Headline: ARR accuracy, model vs. baseline.
        "model_arr_mape": utils.mape(a_arr, fc["arr"].values),
        "model_arr_bias": utils.bias_pct(a_arr, fc["arr"].values),
        "baseline_arr_mape": utils.mape(a_arr, base["arr"].values),
        # Per-driver accuracy (model only) - shows which lever is hardest.
        "driver_mape": {
            "new_customers": utils.mape(test["new_customers"], fc["new_customers"]),
            "churned_customers": utils.mape(test["churned_customers"], fc["churned_customers"]),
            "arpu": utils.mape(test["arpu"], fc["arpu"]),
            "expansion_mrr": utils.mape(test["expansion_mrr"], fc["expansion_mrr"]),
            "ending_mrr": utils.mape(test["ending_mrr"], fc["ending_mrr"]),
        },
        "test": test,
        "model_fc": fc,
        "baseline_fc": base,
    }
    return metrics


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def plot_forecast(drivers: pd.DataFrame, fc: pd.DataFrame, bt: dict) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    utils.apply_style()
    fig, ax = plt.subplots()

    hist = drivers.set_index("month")["arr"]
    ax.plot(hist.index, hist.values, color=utils.COLORS["actual"], lw=2.4,
            label="Actual ARR (FY2024-25)", zorder=3)

    # Bridge the last actual point into the forecast so the line is continuous.
    bridge_x = [hist.index[-1], fc["month"].iloc[0]]
    bridge_y = [hist.values[-1], fc["arr"].iloc[0]]
    ax.plot(bridge_x, bridge_y, color=utils.COLORS["forecast"], lw=2.4, ls="--")
    ax.plot(fc["month"], fc["arr"], color=utils.COLORS["forecast"], lw=2.4,
            ls="--", marker="o", ms=4, label="Driver forecast (FY2026)", zorder=3)

    # Shade the backtest window so a reviewer sees where we validated accuracy.
    test = bt["test"]
    ax.axvspan(test["month"].min(), test["month"].max(),
               color=utils.COLORS["band"], alpha=0.35, zorder=0,
               label=f"Backtest window ({bt['holdout']} mo)")

    ax.set_title("NorthPeak ARR - Actuals & Driver-Based FY2026 Forecast")
    ax.set_ylabel("Annual Recurring Revenue")
    ax.yaxis.set_major_formatter(FuncFormatter(utils.fmt_money))
    ax.set_xlabel("")
    end_arr = fc["arr"].iloc[-1]
    ax.annotate(f"FY2026 exit\n{utils.fmt_money(end_arr)} ARR",
                xy=(fc["month"].iloc[-1], end_arr),
                xytext=(-14, -34), textcoords="offset points",
                ha="right", va="top", fontsize=10, fontweight="bold",
                color=utils.COLORS["forecast"])
    ax.legend(loc="upper left")
    fig.text(0.99, 0.01,
             f"Backtest MAPE: {bt['model_arr_mape']:.1f}% (driver model) vs "
             f"{bt['baseline_arr_mape']:.1f}% (flat-growth baseline)",
             ha="right", va="bottom", fontsize=8, color="#666")
    fig.savefig(utils.FIGURES / "forecast_fy2026.png")
    plt.close(fig)


def plot_drivers(drivers: pd.DataFrame, fc: pd.DataFrame) -> None:
    """Small-multiple view of the forecasted levers - the 'how' behind the ARR."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    utils.apply_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    hist = drivers.set_index("month")
    specs = [
        ("new_customers", "New customers / mo", None),
        ("logo_churn_rate", "Logo churn rate", "pct"),
        ("arpu", "ARPU (monthly)", "money"),
        ("expansion_mrr", "Expansion MRR / mo", "money"),
    ]
    for ax, (col, title, fmt) in zip(axes.ravel(), specs):
        ax.plot(hist.index, hist[col], color=utils.COLORS["actual"], lw=2,
                label="Actual")
        ax.plot(fc["month"], fc[col], color=utils.COLORS["forecast"], lw=2,
                ls="--", marker="o", ms=3, label="Forecast")
        ax.set_title(title)
        if fmt == "money":
            ax.yaxis.set_major_formatter(FuncFormatter(utils.fmt_money))
        elif fmt == "pct":
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x*100:.1f}%"))
    axes[0, 0].legend(loc="upper left")
    fig.suptitle("FY2026 Forecast - Operating Drivers", fontsize=15,
                 fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(utils.FIGURES / "forecast_drivers.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    utils.ensure_dirs()
    drivers = utils.load_drivers()

    # 1) Backtest first - earn the right to forecast.
    bt = backtest(drivers, HOLDOUT_MONTHS)

    # 2) Full FY2026 forecast on all 24 months of history.
    fc = forecast_drivers(drivers, FORECAST_MONTHS)

    # 3) Persist outputs.
    out_cols = [
        "month", "new_customers", "churned_customers", "ending_customers",
        "logo_churn_rate", "arpu", "new_mrr", "churned_mrr", "expansion_mrr",
        "ending_mrr", "arr", "net_revenue_retention",
    ]
    fc_out = fc[out_cols].copy()
    fc_out.to_csv(utils.OUTPUTS / "forecast_fy2026.csv", index=False)

    plot_forecast(drivers, fc, bt)
    plot_drivers(drivers, fc)

    # 4) Console summary.
    start_arr = drivers["arr"].iloc[-1]
    end_arr = fc["arr"].iloc[-1]
    dm = bt["driver_mape"]
    print("=" * 68)
    print("COMPONENT 2 - DRIVER-BASED REVENUE FORECAST")
    print("=" * 68)
    print(f"History: {drivers['month'].min():%Y-%m} -> {drivers['month'].max():%Y-%m} "
          f"({len(drivers)} months)")
    print(f"Exit ARR (Dec-2025 actual):  {utils.fmt_money(start_arr)}")
    print(f"Forecast ARR (Dec-2026):     {utils.fmt_money(end_arr)}  "
          f"(+{(end_arr/start_arr - 1)*100:.1f}%)")
    print()
    print(f"BACKTEST - held out last {bt['holdout']} months "
          f"({bt['test_start']:%Y-%m} to {bt['test_end']:%Y-%m}):")
    print(f"  ARR MAPE  - driver model : {bt['model_arr_mape']:5.2f}%   "
          f"(bias {bt['model_arr_bias']:+.2f}%)")
    print(f"  ARR MAPE  - flat baseline: {bt['baseline_arr_mape']:5.2f}%")
    lift = bt["baseline_arr_mape"] - bt["model_arr_mape"]
    verdict = "beats" if lift > 0 else "trails"
    print(f"  -> driver model {verdict} baseline by {abs(lift):.2f} pts")
    print()
    print("  Per-driver MAPE:")
    for k in ["new_customers", "churned_customers", "arpu", "expansion_mrr", "ending_mrr"]:
        print(f"    {k:<20} {dm[k]:6.2f}%")
    print()
    print(f"Wrote: outputs/forecast_fy2026.csv")
    print(f"Wrote: outputs/figures/forecast_fy2026.png")
    print(f"Wrote: outputs/figures/forecast_drivers.png")
    print("=" * 68)


if __name__ == "__main__":
    main()
