"""
utils.py — shared helpers for the NorthPeak FP&A project.

Data loading, path management, accuracy metrics, and a consistent chart style
so every figure in the project looks like it came from the same deck.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths — resolve everything relative to the repo root so each src/*.py script
# runs standalone from any working directory.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"


def ensure_dirs() -> None:
    """Make sure output directories exist before we write to them."""
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data loaders. `month` is the time index throughout the project.
# ---------------------------------------------------------------------------
def load_drivers() -> pd.DataFrame:
    """24 months of subscription drivers (the operational revenue engine)."""
    df = pd.read_csv(RAW / "subscription_drivers.csv", parse_dates=["month"])
    return df.sort_values("month").reset_index(drop=True)


def load_actuals() -> pd.DataFrame:
    """24 months of P&L actuals."""
    df = pd.read_csv(RAW / "actuals_pl.csv", parse_dates=["month"])
    return df.sort_values("month").reset_index(drop=True)


def load_budget() -> pd.DataFrame:
    """12 months of the FY2025 plan."""
    df = pd.read_csv(RAW / "budget_fy2025.csv", parse_dates=["month"])
    return df.sort_values("month").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Accuracy metrics. MAPE is the FP&A standard for forecast accuracy because it
# is unit-free and intuitive ("we were off by X%"). We add sMAPE and bias so a
# reviewer can see whether the model systematically over- or under-shoots.
# ---------------------------------------------------------------------------
def mape(actual, predicted) -> float:
    """Mean Absolute Percentage Error (%). Lower is better."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = actual != 0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def smape(actual, predicted) -> float:
    """Symmetric MAPE (%) — bounded, robust when actuals are small."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denom = (np.abs(actual) + np.abs(predicted)) / 2
    mask = denom != 0
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denom[mask]) * 100)


def bias_pct(actual, predicted) -> float:
    """Mean forecast bias (%). Positive = forecast runs high vs. actual."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = actual != 0
    return float(np.mean((predicted[mask] - actual[mask]) / actual[mask]) * 100)


# ---------------------------------------------------------------------------
# Shared chart style. One palette across the whole project keeps the figures
# looking like a coherent set on LinkedIn / in the README.
# ---------------------------------------------------------------------------
COLORS = {
    "actual": "#1b3a5b",      # deep navy — historical actuals
    "forecast": "#e07b39",    # warm orange — forecast
    "baseline": "#9aa7b1",    # muted grey — naive baseline
    "budget": "#3f8f6b",      # green — plan/budget
    "band": "#f0c9a8",        # light orange — forecast uncertainty band
    "favorable": "#3f8f6b",
    "unfavorable": "#c0432f",
    "grid": "#dfe4e8",
}


def apply_style() -> None:
    """Apply a clean, presentation-quality matplotlib style."""
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.figsize": (11, 6),
        "figure.dpi": 120,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.edgecolor": "#9aa7b1",
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.8,
        "legend.frameon": False,
    })


def fmt_money(x, _pos=None) -> str:
    """Axis formatter: 10266281 -> '$10.3M', 855523 -> '$856K'."""
    if abs(x) >= 1e6:
        return f"${x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"
