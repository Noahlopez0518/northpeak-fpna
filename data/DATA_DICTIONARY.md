# NorthPeak Analytics - Data Dictionary

**Project:** SaaS FP&A & Forecasting Model
**Company (fictional):** NorthPeak Analytics, a B2B subscription software business
**Period:** FY2024-FY2025 (24 months of actuals; FY2025 also has a budget)
**Note:** All data is synthetically generated to model a realistic ~$10M ARR SaaS company. No real or proprietary data is used.

---

## The Business Story

NorthPeak entered FY2024 with ~220 customers and ~$3.2M ARR. The business grows through three revenue levers: **new customer acquisition**, **expansion** from the existing base (upsell/cross-sell), offset by **churn**. In December 2024, leadership set an optimistic FY2025 budget assuming 3.5% month-over-month revenue growth and tighter cost discipline. The actuals tell us how reality compared to that plan - which is the heart of the variance analysis.

---

## Tab 1 - `Subscription_Drivers`
The operational engine. Every dollar of revenue traces back to these customer-level drivers.

| Field | Definition |
|---|---|
| `month` | Calendar month (month-start) |
| `new_customers` | New logos added that month |
| `churned_customers` | Logos lost that month |
| `ending_customers` | Active customers at month end |
| `arpu` | Average revenue per account (monthly) |
| `new_mrr` | MRR added from new customers |
| `churned_mrr` | MRR lost to churn |
| `expansion_mrr` | Net MRR gained from existing customers (upsell) |
| `ending_mrr` | Monthly recurring revenue at month end |
| `arr` | Annual recurring revenue (ending_mrr × 12) |
| `logo_churn_rate` | churned_customers ÷ prior-month customers |
| `net_revenue_retention` | Revenue retained + expanded from existing base (NRR) |

## Tab 2 - `Actuals_PL`
Monthly profit & loss, driven off `ending_mrr`.

| Field | Definition |
|---|---|
| `revenue` | Recognized monthly revenue (= ending_mrr) |
| `cogs` | Cost of goods sold (hosting, support) ~22% of revenue |
| `gross_profit` | revenue - cogs |
| `sales_marketing` | S&M operating expense |
| `research_development` | R&D / engineering operating expense |
| `general_admin` | G&A operating expense |
| `total_opex` | Sum of the three OpEx lines |
| `operating_income` | gross_profit - total_opex |
| `operating_margin` | operating_income ÷ revenue |

## Tab 3 - `Budget_FY2025`
The plan set in Dec 2024. Compared against FY2025 actuals for variance analysis. Budget assumes smoother growth and tighter cost ratios than reality delivered (`budget_*` prefixed columns mirror the actuals structure).

---

## Key SaaS Metrics Reference
- **MRR / ARR** - recurring revenue, the core SaaS health metric
- **NRR** - >100% means the existing base grows even before new sales (best-in-class is 110%+)
- **Logo churn** - % of customers lost; lower is better
- **Rule of 40** - growth rate + profit margin should exceed 40%
