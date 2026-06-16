# NorthPeak FP&A - Power BI Dashboard Build Guide

## Data sources

| File | Shape | Powers |
|---|---|---|
| `outputs/dashboard_data.csv` | tidy/long: `date, series, metric, value, unit` (958 rows) | KPI cards, ARR trend, budget-vs-actual, scenario fan |
| `outputs/dashboard_bridge.csv` | `step_order, label, amount, kind` (7 rows) | Operating-income variance waterfall |

**Why long format:** every visual is driven by *filtering* one table (`series` +
`metric` slicers) instead of reshaping in DAX. `series` ∈ {`Actual`, `Budget`,
`Forecast`, `Scenario: Base`, `Scenario: Upside`, `Scenario: Downside`}.
`metric` ∈ 18 measures (`arr`, `mrr`, `revenue`, `operating_income`,
`operating_margin`, `logo_churn_rate`, `net_revenue_retention`, customer counts,
etc.). `unit` ∈ {`currency`, `percent`, `count`} for conditional formatting.

## Load & model

1. **Get Data → Text/CSV** → load both files. In Power Query set `date` to Date,
   `value` to Decimal Number.
2. Add a **Date dimension** table (`Calendar = CALENDAR(DATE(2024,1,1), DATE(2026,12,31))`),
   mark as date table, relate `dashboard_data[date]` → `Calendar[Date]` (many-to-one).
3. Base measure:
   ```DAX
   Value = SUM(dashboard_data[value])
   ```
   Everything else is this measure filtered by `series`/`metric` via slicers or
   explicit `CALCULATE`.

## Page 1 - Executive Summary

**Four KPI cards** (top row). Each is `Value` filtered to the latest actual month
(Dec-2025) unless noted:

| Card | Filter | Reads |
|---|---|---|
| **Ending ARR** | series=Actual, metric=arr, last month | **$10.3M** |
| **Net Revenue Retention (annual)** | `Annual NRR (FY2025)` measure - FY2025 monthly factors compounded (`EXP(SUMX(LN(value)))`) | **92.7%** |
| **Logo Churn (monthly)** | series=Actual, metric=logo_churn_rate, last month | **1.7%** |
| **FY2025 Operating Margin** | series=Actual, FY2025 **total** operating_income ÷ total revenue | **-1.6%** |

Format cards by `unit`: currency → `$#,0.0,,"M"`; percent → `0.0%`.

**ARR Trend (line chart).** Axis = `Calendar[Date]`. Lines = `Value` for
metric=arr, split by `series` filtered to {Actual, Forecast}. Actual navy solid,
Forecast orange dashed. This is the headline: $3.2M → $10.3M actual, extending to
**$15.1M** by Dec-2026.

**Budget vs. Actual (clustered column), FY2025.** Axis = month. Two columns per
month: `Value` metric=revenue for series=Budget vs. series=Actual. Add a line for
metric=operating_income. Tells the "beat revenue, missed profit" story at a glance.

## Page 2 - Variance Analysis (FY2025 Budget vs. Actual)

**Operating-income waterfall** from `dashboard_bridge.csv`. Use a Waterfall visual:
Category = `label` (sorted by `step_order`), Y = `amount`, and set
`Budget Operating Income` / `Actual Operating Income` as totals (`kind = anchor`).
Color deltas green when positive, red when negative.

Reads: **$368K plan → +$888K revenue → -$356K COGS → -$485K S&M → -$362K R&D →
-$185K G&A → -$132K actual.**

**Variance table** (matrix). Rebuild from `outputs/variance_analysis.xlsx`
(`Summary` sheet) or compute in DAX: Budget, Actual, Variance $, Variance %, F/U.
Conditional-format Variance % red/green by the F/U column.

## Page 3 - FY2026 Scenarios

**Scenario fan (line chart).** metric=arr, series = the three `Scenario: *` plus a
tail of Actual for context. Use a light shaded band between Upside and Downside.

| Scenario | Exit ARR | FY26 Op Income | Op Margin |
|---|--:|--:|--:|
| Upside | $17.2M | +$1.8M | 13.0% |
| Base | $15.1M | +$0.5M | 3.8% |
| Downside | $12.7M | -$0.5M | -4.0% |

**Scenario OI (clustered column).** metric=operating_income summed over FY2026 by
`series`. One green/navy/red column each - the profitability spread.

**Assumptions card / slicer panel.** List the six toggled drivers (new-customer
pace, churn rate, ARPU growth, expansion pace, COGS %, OpEx %) as a text box so
viewers see what separates the cases. (Values live at the top of `src/scenarios.py`.)

## Styling

- Palette: navy `#1B3A5B` (actual), orange `#E07B39` (forecast), green `#3F8F6B`
  (favorable/upside), red `#C0432F` (unfavorable/downside), grey `#9AA7B1`.
- Currency `$#,0.0,,"M"` for ARR; `$#,0"K"` for monthly lines; `0.0%` for rates.
- One slicer for `metric`, one for `series`, synced across pages.

## Refresh

Re-run the pipeline, then **Refresh** in Power BI - the long schema means new
months flow into every visual with no rework:
```
python src/forecast.py && python src/variance.py && python src/scenarios.py && python src/dashboard.py
```
