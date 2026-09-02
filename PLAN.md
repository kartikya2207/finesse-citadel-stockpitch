# PLAN — Finesse × Citadel Portfolio Challenge, Round 2

**Status:** living document. Revised at each checkpoint (see Revision Log at bottom).
**Owner:** build agent. **Started:** 2026-09-02.

> **NOTE ON `RESEARCH_BRIEF.md`:** The file was not present anywhere on disk
> (`...\fineesexcitadel` was empty; a filesystem-wide search for `*RESEARCH_BRIEF*`
> returned nothing). I am therefore treating the detailed summary in the task prompt
> (Part 2) as the binding baseline spec. If the actual file surfaces, re-read and reconcile.

---

## 0. The objective function, stated precisely

We are NOT maximising backtest PNL. We are maximising:

```
E[prize] = P(top 6-8 on Round-2 Total Net PNL)
         x P(survive Jan-Jun 2026 stress test)
         x P(win the jury on rationale / robustness / risk / presentation)
```

Round 2 ranks on `Final Portfolio Value - 1,00,00,000`, blind to path. But the money is
decided at a jury-graded final with an out-of-sample stress test. So the design target is:
**a top-decile-plausible PNL that is defensible line-by-line and does not invert in
Jan-Jun 2026.** A hindsight-fitted smallcap basket showing 55% CAGR loses this competition
in the room, not in the spreadsheet.

Corollary rule for the final pick: *maximise expected Total Net PNL subject to
(a) surviving the stress window and (b) every line being defensible. Ties go to the more
explainable candidate.*

---

## 1. Hard constraints (binding, from the problem statement)

| # | Constraint | Implementation |
|---|---|---|
| C1 | Universe = Nifty 100 U Nifty Midcap 100 U Nifty Smallcap 100 | PIT reconstruction, sec. 3 |
| C2 | Corpus = INR 1,00,00,000 | `CAPITAL = 1e7` |
| C3 | Max 10 stocks | asserted every day: `n_positions <= 10` |
| C4 | Window 2021-01-01 .. 2025-12-31 | asserted |
| C5 | 0.1% per transaction | charged on every leg, live formula in Excel |
| C6 | Same core methodology across all 10 names | one scoring function, one weighting rule, no per-name overrides |
| C7 | Excel deliverable with stated sheets | `src/excel_export.py` |
| C8 | Stress test 2026-01-01 .. 2026-06-30 | SEALED (sec. 7) |

## 2. Metric definitions — THEIRS, not the textbook's

| Metric | Their formula | Note |
|---|---|---|
| **Total Net PNL** | `Final Value - 1e7` | PRIMARY RANK |
| Annualised Return | geometric: `(V_T/V_0)^(1/years) - 1` | also report calendar-year returns |
| Max Drawdown | max peak-to-trough on daily NAV | on total-return NAV |
| **Sharpe (theirs)** | `Annualised Return / SD(daily returns)`, rf=0 | **NOT an annualised denominator.** Report verbatim. |
| Sharpe (standard) | `mean(daily) * 252 / (SD(daily) * sqrt(252))` | reported alongside, clearly labelled |
| Gain-to-Loss | `avg profit of winning trades / avg loss of losing trades` | trade = round trip |
| Accuracy | `% of trades profitable` | caveat if n < 30 |
| Trade stats | total trades, per stock, turnover | both leg-count and round-trip count |

Their Sharpe is dimensionally inconsistent (annual numerator over a daily denominator) and
will read ~15.9x larger than the standard one. **We follow the rules and flag the conflict** —
both numbers in the workbook, each with its formula written in an adjacent label cell.

## 3. Point-in-time universe — the single biggest correctness risk

Using today's constituent lists for a 2021 backtest manufactures a large slice of terminal
PNL. Two distinct biases:

- **(a) Index-membership survivorship** — today's Nifty 100 contains stocks that *became*
  large. Picking from it in 2021 is picking winners with hindsight. THIS IS THE BIG ONE.
- **(b) Delisting / dead-stock survivorship** — names removed and now invisible to data
  vendors. Smaller in this universe (mostly mergers, where the acquirer survives) but real.

**Approach — reconstruct membership from NSE's own published rule, not from a scraped list.**
NSE index methodology is mechanical and public:
- Nifty 100 = top 100 of the eligible universe by average full market capitalisation.
- Nifty Midcap 150 = ranks 101-250; **Nifty Midcap 100** = top 100 of those = ranks ~101-200.
- Nifty Smallcap 250 = ranks 251-500; **Nifty Smallcap 100** = top 100 of those = ranks ~251-350.
- => our universe is approximately **mcap ranks 1-200 U 251-350**. (Ranks 201-250 are
  genuinely excluded by the rule — a real feature, not a bug.)
- Semi-annual review, cut-off 31 Jan / 31 Jul, effective end-March / end-September.

At each rebalance I rank the widest obtainable NSE cross-section by
`full_mcap = RAW close x shares_outstanding_as_of_that_date` (raw, not split-adjusted, since
share counts are as-reported) and apply the rank bands with the correct review lag.

**Validation gate:** the reconstruction is checked against actual published lists at every
date I can obtain one (current 2026-09 CSVs; Wayback snapshots 2023-08, 2024-01, 2024-07,
2026-08). Report overlap %. If overlap is poor the method is rejected and I fall back with
the bias quantified rather than hidden.

**Residual bias (b)** is handled by widening the master ticker list beyond today's Nifty
Total Market 750 using historical snapshots and known deletions, and by explicitly
quantifying what remains in the Assumptions Register.

## 4. Data plan

| Layer | Source | Use |
|---|---|---|
| Prices | yfinance `.NS` daily OHLCV + splits + dividends, from 2019-01-01 | returns (adj close), mcap (raw close) |
| Shares o/s | `yfinance.Ticker.get_shares_full()` | PIT market-cap ranking |
| Index lists | niftyindices.com constituent CSVs (11 indices, 754 unique symbols) | master list + validation |
| Historical lists | Wayback CDX snapshots of those CSVs | PIT validation anchors |
| Benchmark | `^CRSLDX` (Nifty 500), `^NSEI` (Nifty 50), + TRI adjustment | benchmark comparison |
| Fundamentals | yfinance financials, lagged to filing date | quality / value screens |

Integrity checks BEFORE any backtest: NSE trading-calendar reconciliation (a holiday is not
a zero-return day), zero-volume days, price jumps not explained by a recorded corporate
action, truncated history (no backfilling before listing), NaN propagation, paise-vs-rupee
and face-value errors, explicit suspended/delisted handling rule. All logged to an
exceptions file.

## 5. Strategy search — what gets built and benchmarked

Baseline (from the brief) is implemented first and honestly, then treated as a competitor,
not a conclusion.

**Baseline B0:** PIT universe -> screen (ROE>0, D/E below median, drop top-quintile vol)
-> rank by `avg(6m, 12m total return, skipping last 1m) / trailing 1y daily vol`
-> top 10 -> inverse-vol weights, cap 20%, floor 5% -> quarterly rebalance.

Families built and benchmarked head-to-head:
1. **Fundamental** — quality (ROE, ROCE, accruals, earnings stability, leverage), value
   (P/E, P/B, EV/EBITDA, dividend yield), growth, Piotroski-style composites.
2. **Quant / factor** — momentum at multiple lookbacks, risk-adjusted and residual momentum,
   low vol, low beta, size, multi-factor composites, trend / absolute-momentum overlay,
   volatility targeting. (Overlays checked against C3/C6 before use.)
3. **ML** — regularised linear, gradient boosting, random forest, small NN, clustering,
   HMM / changepoint regime overlay. Walk-forward only. Honest about ~300 names x ~60
   monthly observations overfitting trivially.
4. **Hybrids** — fundamental screen -> quant ranker; ML-learned factor combination;
   regime-conditional sleeve switching; signal ensembles.
5. **Permutations** — lookbacks, screens, n in {5,8,10}, cadence {B&H, annual, quarterly,
   monthly}, weighting {EW, inv-vol, score, risk-parity, capped variants}, universe sleeves,
   sector caps.

Every variant is logged to `TRIALS_REGISTER.md` with parameters and result. The honest trial
count feeds the deflated-Sharpe and PBO corrections. Reporting the best raw number without
that correction is the exact failure being guarded against.

## 6. Overfitting control (mandatory)

- Expanding-window walk-forward inside 2021-25. No single full-sample fit is ever the headline.
- Parameter-stability surfaces; pick plateau centres, never spikes.
- Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) with the real trial count, skew, kurtosis.
- Probability of Backtest Overfitting via combinatorially-symmetric cross-validation.
- Harvey-Liu multiple-testing hurdle t ~ 3.0.
- One-way sensitivity tables: universe source, cost per side, cadence, weighting, n names.

**TRIPWIRE (hard stop):** if CAGR > ~30%, OR standard Sharpe > ~2.5, OR drawdown shallower
than the benchmark in BOTH 2022 and 2025 -> stop and hunt for look-ahead / survivorship / a
cost or return sign error before believing the number.

## 7. Stress-window seal

Today is 2026-09-02, so Jan-Jun 2026 data physically exists and is downloadable. That makes
the seal a discipline problem, not a data problem.

Enforcement: raw data for 2026 is downloaded into the cache (acquisition is not peeking) but
`src/seal.py` makes the backtest engine **hard-refuse any date > 2025-12-31** unless
`FROZEN.json` exists on disk. `FROZEN.json` is written only when the in-sample design is
final; it records the frozen parameters, a SHA-256 of the strategy module, and a timestamp.
Unsealing is timestamped in `logs/seal.log`. Post-unseal parameter changes are forbidden and
would be visible in that log.

Known contamination, declared up front: the task prompt itself already states the Jan-Jun
2026 outcome (Nifty 50 -8..-10%, Smallcap 100 +6..12%, Nifty IT -27.8%, Defence +21%).
I cannot un-know it. Mitigation: no rule may reference a sector or a size sleeve chosen
*because* of that information; any such tilt must be justified by in-sample evidence alone;
and this contamination is disclosed in DEFENCE.md.

## 8. Engineering rules

- Unit tests before trusting the engine, including a fully hand-computed 3-stock / 5-day /
  1-rebalance case with PNL worked out by hand and asserted.
- Run-time invariants: weights sum to 1 or cash explicit; no unintended shorts; NAV
  continuity across rebalances; cost == 0.001 x traded notional per leg; no silent NaNs;
  integral share counts.
- Look-ahead test: shift inputs forward in time, assert results change.
- All seeds fixed; every run reproducible; data snapshot hash logged.
- Re-question earlier design decisions at least twice more during the build, including ones
  inherited from the brief and from the task prompt. Show the reasoning when something changes.
- Where the rules conflict with best practice: FOLLOW THE RULES, flag the conflict.

## 9. Deliverables

1. Reproducible pipeline: ingest -> PIT universe -> signals -> backtest -> metrics -> sealed
   stress test -> Excel.
2. `Finesse_Citadel_Round2_Submission.xlsx` per the required sheet structure.
3. `TRIALS_REGISTER.md` — every variant, parameters, result, kept/rejected + why.
4. `RESULTS.md` — head-to-head across all families on every required metric + stress test.
5. `DEFENCE.md` — one page for the jury round.
6. `ASSUMPTIONS.md` — tagged register.
7. `QUESTIONS_FOR_ORGANISERS.md` — ranked by build impact.

## 10. Build order

1. Scaffolding, config, seal.
2. Data ingestion + integrity report.
3. PIT universe + validation gate.
4. Backtest engine + unit tests (hand-computed case + look-ahead test).
5. Metrics module (their formulas + standard).
6. Baseline B0, audited.
7. Factor library + systematic sweep.
8. Fundamental family.
9. ML family, walk-forward.
10. Hybrids.
11. Overfitting statistics (DSR / PBO) on the honest trial count.
12. Freeze design -> write `FROZEN.json`.
13. Unseal, run stress test.
14. Excel export.
15. Write-ups.

---

## Revision Log
- **2026-09-02 r1** — initial plan. `RESEARCH_BRIEF.md` missing; using prompt Part 2 as spec.
