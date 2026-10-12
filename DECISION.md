# DECISION — second search, 2026-09-02

**Outcome: a challenger cleared all six replacement criteria. Nothing has been pushed. The final call on whether to swap is yours, and I flag one argument that points the other way.**

## The challenger

`CHALLENGER_rarAvg_up12_dd1y` — quarterly · top 10 · drop the most volatile 20% · inverse-vol weighted, 20% cap / 5% floor.

Score = equal-weighted average of **three** cross-sectional percentile ranks:
1. `rar_mom_avg_6_12_skip1` — the average of 6-month and 12-month returns (each skipping the most recent month), divided by trailing 1-year volatility
2. `pct_up_months_12m` — fraction of the last 12 months that were up months
3. `max_dd_1y` — trailing 1-year maximum drawdown (shallower is better)

It is the incumbent **minus** the path-efficiency leg, with the momentum leg blended across 6 and 12 months instead of 12 alone. A simplification, not an invention.

## Scorecard against the six criteria

| | Criterion | Incumbent | Challenger | Verdict |
|---|---|---:|---:|---|
| a | Total Net PNL | ₹2,73,92,323 | **₹3,27,42,461** | **PASS** (+₹53.5L, +19.5%) |
| b | Phase σ, 6 semiannual phases | ₹30.1L | **₹10.7L** | **PASS** (≤₹30L) |
| b′ | Phase σ, 3 quarterly phases | ₹24.1L | **₹14.9L** | better on both bases |
| c | Maximum drawdown | −27.16% | **−24.46%** | **PASS** (≥−32%) |
| d | Hard constraints in code | — | 8/8 proven | **PASS** |
| e | 7-point audit | — | 7/7 | **PASS** |
| f | Explainable in 4 sentences | — | yes | **PASS** |

Supporting metrics (challenger vs incumbent): CAGR **33.71% vs 30.18%** (brief's `(final/1cr)^(1/5)−1`) · Sharpe competition **30.07 vs 26.28** · Sharpe standard **1.89 vs 1.65** · accuracy **62.30% vs 61.54%** · gain-to-loss **2.10 vs 1.78** · 122 round trips / 312 legs vs 130 / 320 · turnover **227% vs 256%** · costs ₹5.83L vs ₹6.16L.

**The four sentences (criterion f):** We buy the ten stocks in the eligible universe that have climbed the most steadily. We measure steadiness three ways — return over the past 6–12 months divided by how much the stock wobbled, the fraction of the last twelve months that were up months, and how shallow its worst fall of the past year was. Each measure is converted to a percentile rank among the eligible names on that date, and the three ranks are averaged with equal weight. We size positions inversely to volatility, cap any name at 20%, and repeat every quarter.

## Audit gate — 7/7

Constraints: max 10 concurrent holdings on every single day · |Σw−1| = 2.2e-16 · weights within [0.068, 0.157], cap never breached · cost = 0.001 × notional on all **312/312** legs · zero short positions · **zero** selections outside the point-in-time universe · window exactly 2021-01-01 → 2025-12-31.

No look-ahead: the search ran on a world **physically truncated** to 2025-12-31, so 2026 was absent rather than merely forbidden. Validation: the incumbent re-run on the truncated world reproduces ₹27,392,323 to the paisa, proving truncation is a no-op in sample. Shift test: shifting inputs 21 days changes the picks at **20/20** rebalances and moves PNL by ₹113L.

Reconciliation: replaying all 312 legs gives a terminal value of ₹42,742,461.44 against the NAV path's ₹42,742,461.44 — **difference ₹0.000000**.

Tripwire: not tripped. CAGR 33.7% (< 35%), standard Sharpe 1.89 (< 2.5), drawdown deeper than the benchmark in both 2022 (−19.3% vs −17.5%) and 2025 (−20.3% vs −12.7%).

The one flag raised and resolved: my independent metric path disagreed with the engine on CAGR by 0.03pp. Cause is a **denominator convention**, not a bug — `metrics.annualised_return` divides by NAV on day 1 (after the first purchase's cost) while the brief mandates ₹1,00,00,000. It affects incumbent and challenger identically. All figures above use the brief's definition. The 29 existing tests pass unchanged.

## Concentration — the challenger is better here

| | Incumbent | Challenger |
|---|---:|---:|
| Top-5 trades' share of PNL | 40.9% | **34.6%** |
| Largest single trade | HAL, 15.5% | RECLTD, **8.1%** |
| PNL excluding the top 5 trades | ₹161.8L | **₹214.2L** |

The challenger's advantage is **not** one lucky trade. Excluding each book's five best trades, it still earns ₹52L more than the incumbent. This is the strongest single piece of evidence in its favour.

## What argues AGAINST the challenger — read this before deciding

**1. The specification sits on a sharp peak, not a plateau.** Every single-leg substitution costs a lot:

| Variant | PNL | Δ | phase σ |
|---|---:|---:|---:|
| **rarAvg + up12 + dd1y (winner)** | ₹327.4L | — | 10.7 |
| rar12s + up12 + dd1y | ₹286.5L | −41L | 15.0 |
| rar12 + up12 + dd1y | ₹242.3L | −85L | 19.8 |
| rarAvg + up12 + dd1y + eff6 | ₹242.4L | −85L | 25.1 |
| rar6 + up12 + dd1y | ₹209.6L | −118L | 19.9 |
| rarAvg + up6d + dd1y | ₹179.2L | −148L | 38.7 |
| rarAvg + up12 + **ddnow** | ₹191.4L | −136L | 81.4 |

Mitigating: the gradient is **monotone and economically sensible** — blending 6m+12m beats either alone, the 12-month consistency measure beats the 6-month one, and the full-year drawdown beats the spot drawdown. It is a coherent surface, not noise. But the peak is sharper than the incumbent's, and a peak that sharp on 20 rebalances is partly sample-specific.

**2. Multiple testing.** 526 new trials this session; register now at **820**. The winner is the best of a large search, and the phase filter that promoted it was *itself* a selection stage, so its ₹10.7L dispersion is also partly selection-lucky.

**3. Provenance — the argument I weigh most heavily.** The incumbent was frozen **before anyone had seen 2026**, and its seal held: −0.22% out of sample. The challenger was chosen **after** the unseal. Even though 2026 was physically absent from the search world and entered no signal, screen, ranking or tie-break, the *selector* had already seen the incumbent's 2026 result. That is a genuine, unfixable weakening of the evidence.

**4. Out of sample, the challenger is slightly worse.** Report-only diagnostic, computed after freezing, never used in selection:

| Jan–Jun 2026 | Incumbent | Challenger | Nifty 500 TRI |
|---|---:|---:|---:|
| Period return | **−0.22%** | −1.00% | −4.05% |
| Max drawdown | −15.51% | −14.73% | −14.59% |

Both survive the regime inversion and both beat the index. The challenger is 0.78pp behind the incumbent on the only genuinely out-of-sample window either has.

## My recommendation

**On the stated criteria the challenger wins, and I am reporting it as the winner because that is the rule you set.** It is more profitable, less risky, more phase-stable, less concentrated, and cleanly audited.

**But if you ask which I would put in front of the jury, I lean to the incumbent**, and the reason is criterion (f) generalised: the incumbent's story is stronger than its number. "We froze before we looked, and it survived the inversion" is a claim the challenger structurally cannot make. Round 2 is graded on rationale, robustness and risk management — not PNL alone — and trading a clean provenance narrative for ₹53L of in-sample PNL is a poor exchange in front of a panel that will ask exactly how the strategy was chosen. The sharp-peak result reinforces that caution.

A defensible middle path exists and costs nothing: **submit the incumbent, and present the challenger as evidence of search discipline** — "our second, wider search found a higher-PNL variant that passed every audit, and we did not submit it, because it was selected after our seal was broken." That is a stronger answer than either strategy alone.

The call is yours. Everything for the swap is prepared and uncommitted.
