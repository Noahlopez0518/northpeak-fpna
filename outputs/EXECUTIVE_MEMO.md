# Executive Memo - NorthPeak Analytics FY2025 Review & FY2026 Outlook

**To:** Chief Financial Officer
**From:** FP&A
**Re:** FY2025 budget-vs-actual results, FY2026 driver-based forecast, and scenario planning
**Bottom line:** We grew faster than plan but spent the upside and more - FY2025 finished at a small operating loss. FY2026 is a strong growth year in every scenario; whether it is *profitable* comes down to cost discipline, not revenue.

---

## 1. What the numbers say

NorthPeak exited FY2025 at **$10.3M ARR** (625 customers, ARPU ~$1,213/mo), up **+76% year-over-year** from $5.8M. Growth is real, but it is **acquisition-driven**: net revenue retention is only **~93% on an annualized basis** (≈99% per month), meaning the existing base *shrinks* slightly on its own. In FY2025, expansion added $79K of MRR while churn removed $130K - so **every dollar of net growth came from new logos**, not the installed base. Monthly logo churn runs **~1.7% (~19% annualized)**. The engine works, but the bucket leaks.

But profitability went the wrong way. We planned a **+5.0% operating margin** for FY2025 and delivered **-1.6%** - a **$499K** swing that turned a budgeted +$368K operating profit into a **-$132K loss**.

## 2. What drove the budget variance

Revenue was *not* the problem - we beat it.

| Line | Budget | Actual | Variance | |
|---|--:|--:|--:|:--|
| Revenue | $7.36M | $8.24M | **+$888K (+12.1%)** | 🟢 Favorable |
| COGS | $1.47M | $1.83M | -$356K (+24.2%) | 🔴 Unfavorable |
| Sales & Marketing | $2.79M | $3.28M | -$485K (+17.3%) | 🔴 Unfavorable |
| Research & Development | $1.77M | $2.13M | -$362K (+20.5%) | 🔴 Unfavorable |
| General & Admin | $0.96M | $1.14M | -$185K (+19.3%) | 🔴 Unfavorable |
| **Operating Income** | **+$368K** | **-$132K** | **-$499K** | 🔴 Unfavorable |

**The story in one line:** the $888K revenue beat was more than consumed by ~$1.39M of cost overruns. Every cost line ran 17-24% over plan. Some of that is healthy (COGS scales with revenue, and we sold more), but **OpEx growth outran revenue growth** - total OpEx rose to **79% of revenue vs. the 75% we budgeted**. We bought growth at the expense of the margin we promised the board.

## 3. FY2026 outlook (driver-based forecast)

We forecast revenue the way the business actually works - new customers × ARPU, less churn, plus expansion - not a flat growth rate. The model is **backtested**: held out the last 6 months, forecast them from history only, and landed a **3.9% ARR error (MAPE)**, beating a naive flat-growth baseline (5.6%).

**Base case: ARR reaches ~$15.1M by Dec-2026 (+47%)**, decelerating sensibly from FY2025's +76%. Customer base grows from 625 to ~860. At current cost ratios with modest operating leverage, that delivers a **+$488K operating profit (3.8% margin)** - i.e., we cross back into the black, but barely.

## 4. Scenarios - the range leadership should plan against

The same engine, flexing the six levers leadership controls (sales pace, churn, pricing, expansion, COGS %, OpEx %):

| Case | Exit ARR | FY2026 Operating Income | Margin |
|---|--:|--:|--:|
| **Upside** (churn ↓1.3%, sales +20%, disciplined OpEx) | **$17.2M** | **+$1.8M** | 13.0% |
| **Base** | $15.1M | +$0.5M | 3.8% |
| **Downside** (churn ↑2.4%, sales -25%, OpEx stays heavy) | **$12.7M** | **-$0.5M** | -4.0% |

The **ARR spread is $4.5M** and the **operating-income spread is ~$2.3M** - and the single biggest swing factor between profit and loss is **OpEx as a share of revenue**, not the top line. All three cases still grow ARR double digits.

## 5. What leadership should do

1. **Hold the line on OpEx, not on growth.** Every scenario grows ARR; only the disciplined ones make money. Set an explicit FY2026 OpEx ceiling at **~74% of revenue** (Base) with a stretch to 70%, and gate incremental S&M/R&D hiring on hitting it. Closing the 79%→74% gap is the difference between a loss and a profit.
2. **Fix the leaky bucket - retention is the cheapest growth.** At ~93% annualized NRR the installed base loses value every month, so today we fund *all* growth through new-logo CAC. Closing the gap to 100%+ (the Upside assumption) compounds with near-zero acquisition cost. Fund the upsell/expansion motion before net-new S&M headcount.
3. **Re-baseline the budget to reality.** The FY2025 plan was ~12% light on revenue and ~5 pts optimistic on cost ratios. Build FY2026 off the backtested driver model, not a flat 3.5%/month, so we're managing to a number we can actually hit.
4. **Watch the leading indicators monthly.** New-logo pace, logo churn, and OpEx ratio are the three dials that move us across the scenario range - put them on the monthly dashboard and steer.

---
*Forecast accuracy validated by 6-month holdout backtest (3.9% ARR MAPE). All figures reconciled by `src/validate.py` (46/46 checks). Data is synthetic, generated to model a realistic ~$10M ARR B2B SaaS company.*
