# CLAUDE.md — NorthPeak FP&A Project Brief

This file is the build spec for Claude Code. Read it fully, then build the project component by component. Ask me before installing heavy deps or making structural choices that deviate from this brief.

---

## What we're building

An end-to-end **FP&A (Financial Planning & Analysis) project** for a fictional B2B SaaS company called **NorthPeak Analytics**. This is a portfolio piece for a Financial Data Analyst job search — it will be posted to GitHub, LinkedIn, and referenced on a resume.

**Audience:** finance hiring managers (FP&A / financial data analyst roles). The project must speak their language — ARR, MRR, churn, NRR, budget-vs-actuals, variance bridges, scenario planning — and connect numbers to a business narrative.

**Design principle that matters most:** revenue is **driver-based** (new customers × ARPU, minus churn, plus expansion), NOT a flat growth %. Keep it that way throughout.

---

## The data (already generated — do not regenerate unless asked)

Located in `data/raw/`:
- `northpeak_data.xlsx` — 3 tabs: `Subscription_Drivers`, `Actuals_PL`, `Budget_FY2025`
- `subscription_drivers.csv` — 24 months of customer/MRR drivers
- `actuals_pl.csv` — 24 months of P&L (revenue, COGS, OpEx, operating income)
- `budget_fy2025.csv` — 12 months FY2025 plan

`data/generate_data.py` is the reproducible generator. `data/DATA_DICTIONARY.md` defines every field and the business story. **Read DATA_DICTIONARY.md before writing any analysis code.**

Business shape: ~$3.2M → ~$10.3M ARR over 24 months, 625 ending customers, ~1.7% monthly logo churn. The FY2025 budget was set optimistically (3.5% MoM growth, tighter costs), so actuals will show real variances.

---

## Build these 4 components in order

### Component 2 — Driver-based revenue forecast
- Forecast the next 12 months (FY2026) from the drivers, not a flat line.
- Forecast each driver: new customers, churn rate, ARPU, expansion — then roll up to MRR/ARR.
- Use statsmodels (e.g. exponential smoothing / Holt-Winters) and/or scikit-learn. Compare a simple baseline vs. the chosen model.
- **Backtest:** hold out the last 3–6 months of actuals, forecast them, report MAPE / forecast accuracy. This is the credibility step — do not skip it.
- Output: `outputs/forecast_fy2026.csv` + a forecast chart in `outputs/figures/`.

### Component 3 — Budget vs. Actuals variance engine
- Join FY2025 budget to FY2025 actuals.
- Compute variance ($ and %) for revenue, COGS, each OpEx line, and operating income.
- Flag material variances (e.g. |variance| > 5% or a $ threshold) — favorable vs. unfavorable.
- Build a **variance waterfall / bridge** (plan → actual, showing what drove the gap).
- Output: `outputs/variance_analysis.xlsx` + bridge chart in `outputs/figures/`.

### Component 4 — Scenario analysis
- Three cases: Base / Upside / Downside, driven by toggleable assumptions (churn rate, new-customer pace, ARPU growth, hiring/OpEx).
- Show ARR and operating income under each case over FY2026.
- Make assumptions a clearly-labeled config dict at the top so they're easy to flex.
- Output: `outputs/scenarios.csv` + comparison chart.

### Component 5 — Executive deliverables
- **Power BI dashboard** (`.pbix`) — Claude Code can't build this directly, so instead produce a clean, well-shaped `outputs/dashboard_data.csv` (tidy/long format ready for Power BI) AND a `DASHBOARD_GUIDE.md` describing the exact visuals to build (KPI cards, ARR trend, variance bridge, scenario fan chart) so the human can assemble it fast.
- **Executive memo** — `outputs/EXECUTIVE_MEMO.md`: a 1-page narrative. "Here's what the numbers say, here's what's driving the budget variance, here's the FY2026 outlook, here's what leadership should do." This memo is the differentiator — write it like an analyst briefing the CFO.

---

## Repo structure to maintain
```
northpeak-fpna/
├── CLAUDE.md                # this file
├── README.md               # build last — see README requirements below
├── requirements.txt
├── data/
│   ├── raw/                 # source data (don't edit)
│   ├── generate_data.py
│   └── DATA_DICTIONARY.md
├── notebooks/              # exploration (optional)
├── src/
│   ├── forecast.py         # Component 2
│   ├── variance.py         # Component 3
│   ├── scenarios.py        # Component 4
│   └── utils.py
└── outputs/
    ├── figures/
    └── ... (csvs, xlsx, memo, guide)
```

## Conventions
- Python 3, pandas/numpy/statsmodels/scikit-learn/matplotlib/openpyxl.
- Pin versions in `requirements.txt`.
- Each `src/*.py` runs standalone (`python src/forecast.py`) and prints a short summary.
- Charts: clean, labeled, presentation-quality (these go on LinkedIn). Consistent color palette.
- Comment the finance logic, not just the code — explain *why* a metric matters.

## README requirements (build last)
- One-paragraph project pitch + the business story.
- Screenshots of the best 2–3 charts and the variance bridge.
- "What this demonstrates" section mapping skills → FP&A competencies.
- How to run it. Link to the executive memo.
- Note that data is synthetic.

## Out of scope / ask first
- Don't add a web framework or database unless I ask.
- Don't connect to live market/financial APIs — this is a self-contained model.
- Streamlit app is optional/stretch — only if I request it.
