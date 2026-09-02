# RESULTS

**Deliverable:** `FINESSE_CITADEL_SUBMISSION.xlsx` — 10 sheets, 7,329 live Excel formulas, 0 broken references.

## Frozen strategy

`COMP_allweather` — quarterly · inverse-vol weighted, capped 20% / floored 5% · 10 names · drop the most volatile 20% of the eligible universe before scoring.

Score = equal-weighted sum of four winsorised cross-sectional z-scores: risk-adjusted 12m momentum (skip 1m) + fraction of up months (12m) + trailing-1y max drawdown + 6m path efficiency.

Frozen at **2026-09-02T17:27:58Z** (`FROZEN.json`, with SHA-256 of every strategy source file). That timestamp is also the stress-window unseal.

## Headline — 1 Jan 2021 to 31 Dec 2025, point-in-time universe

| Metric | Strategy | Nifty 500 TRI | EW PIT universe |
|---|---:|---:|---:|
| Final value of ₹1cr | **₹3,73,92,323** | ₹2,16,47,190 | ₹2,81,83,692 |
| **TOTAL NET PNL (primary rank)** | **₹2,73,92,323** | ₹1,16,47,190 | ₹1,81,83,692 |
| Absolute return | 273.92% | 116.47% | 181.84% |
| **Annualised return (CAGR)** | **30.23%** | 16.71% | 22.83% |
| **Maximum drawdown** | **−27.16%** | −18.44% | −22.59% |
| **Sharpe (competition defn: ann. return ÷ SD of daily returns, rf=0)** | **26.28** | 18.45 | — |
| **Sharpe (standard, denominator annualised)** | **1.66** | 1.16 | — |
| Annualised volatility | 18.26% | 14.38% | — |
| **Gain-to-loss ratio** | **1.78** | — | — |
| **Accuracy (% profitable trades)** | **61.54%** | — | — |
| Beta / annualised alpha / IR | 0.97 / +12.34% / 1.00 | — | — |

**Trade statistics:** 130 completed round trips · 320 legs · 256.5% annual one-way turnover · **₹6,16,428 total transaction cost** (0.1% on every leg, charged inside the NAV path) · max drawdown peak 27-Sep-2024 → trough 07-Apr-2025.

**Constraints proven in code and on sheet 2:** max concurrent holdings **10** · max |Σw − 1| = 2.2e-16 · max single weight **15.5%** (20% cap never binds) · PIT universe only · 0.1% per leg on both sides.

## Stress test — 1 Jan to 30 Jun 2026 (sealed until freeze)

| | Frozen strategy | Nifty 500 TRI | EW PIT universe |
|---|---:|---:|---:|
| Period return | **−0.22%** | −4.05% | +1.68% |
| Net PNL on ₹1cr | −₹31,562 | −₹4,04,900 | — |
| Max drawdown | −15.51% | −14.59% | — |
| Trades / accuracy / gain-to-loss | 17 / 52.9% / 0.87 | — | — |

The window inverted the backtest regime (Nifty 50 −8 to −10%, Nifty IT −27.8%, smallcaps up). The book was flat, beating the index by 3.8pp but **trailing its own equal-weighted universe by 1.9pp**. We claim **regime survival, not regime skill** — 6 months and 17 round trips prove robustness, not edge.

Continuous path 1 Jan 2021 → 30 Jun 2026: **₹3,72,39,510**, CAGR 27.07%.

## Calendar years — including the bad one

| Year | Strategy | Nifty 500 TRI | EW PIT universe | Strategy max DD |
|---|---:|---:|---:|---:|
| 2021 | +66.15% | n/a | +46.89% | −9.16% |
| 2022 | +5.97% | +2.80% | +3.06% | −20.98% |
| 2023 | +56.56% | +26.62% | +41.93% | −7.44% |
| 2024 | +47.63% | +16.51% | +23.72% | −12.97% |
| **2025** | **−8.89%** | **+7.95%** | +2.32% | −21.89% |
| 2026 H1 (sealed) | −0.22% | −3.13% | +1.68% | −15.51% |

## Why this and not the ₹427L strategy

The best in-sample number we found was ₹427L (`mom_12m`, semi-annual). It is the **maximum of its own rebalance-phase distribution** — shift the identical calendar 3 months and it prints ₹223L. Our frozen strategy's spread across the same six phases is ₹81L (std ₹30L) versus ₹67–84L std for every momentum rival, and its *worst* phase beats their worst. We ranked on phase stability and accepted a ~₹43L lower expected headline. See `TRIALS_REGISTER.md` and workbook sheet 10.

## Deliberately not run

- **ML / hybrid families — coded, never executed.** ~60 monthly cross-sections is not a training set, and any result would need deflating against a 119-trial search which there was no time to do honestly. Reporting an undeflated ML number would be a weaker answer to a quant jury than not running it. This is a considered decision, not an omission.
- **Standalone fundamental strategies.** Our fundamentals are restated, not point-in-time, and honest only back to July 2022. Cannot be built for a 2021-start window without look-ahead.
- **The fundamental quality-screen overlay** (positive ROE, below-median D/E, applied from Jul-2022 with the pre-2022 gap disclosed) was scoped and **not run** — it needed a new lagged panel wired into the feature set, and phase robustness was worth more per available minute. **Untested, disclosed as such.**

## Known limitations

Only the mandated 0.1%/side is modelled — no STT, stamp duty, GST or slippage; at 256% turnover a realistic statutory add-on would cost ~4pp of CAGR. Fractional shares assumed. Nifty 500 TRI approximated from the price index plus a constant dividend accrual. PIT membership is *reconstructed* (NSE does not publish free historical constituent files), so it is directionally right rather than exact. Accuracy of 61.5% carries a ±8.4pp 95% interval on 130 trades. **40.9% of PNL came from 5 trades.**

Full detail: `DEFENCE.md`, `TRIALS_REGISTER.md`, `ASSUMPTIONS.md`, workbook sheets 7 / 9 / 10.
