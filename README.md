# Finesse × Citadel Stock Pitch — Round 2

A point-in-time-honest systematic equity backtest for the Finesse × Citadel stock-pitch competition (Round 2).

**Mandate:** ₹1,00,00,000 corpus · maximum 10 stocks · universe restricted to Nifty 100 + Nifty Midcap 100 + Nifty Smallcap 100 · backtest 1 Jan 2021 – 31 Dec 2025 · out-of-sample stress test 1 Jan – 30 Jun 2026 · 0.1% transaction cost per side · ranked on Total Net PNL.

**Primary deliverable:** [`FINESSE_CITADEL_SUBMISSION.xlsx`](FINESSE_CITADEL_SUBMISSION.xlsx) — 10 sheets, 7,329 live Excel formulas, 0 broken references.

---

## The frozen strategy

**`COMP_allweather`.** Every quarter (first trading day of Jan/Apr/Jul/Oct) we take the **point-in-time** membership of the three eligible indices — the constituents as of *that date*, reconstructed from market-cap ranking and listing history, never today's lists. We drop the most volatile 20% of that universe, then rank every survivor on an **equal-weighted average of four cross-sectional percentile ranks**: risk-adjusted 12-month momentum (skip the most recent month), fraction of up months over 12 months, trailing-1-year maximum drawdown, and 6-month path efficiency. We buy the top 10, weighted **inverse-volatility with a 20% cap and 5% floor**, and hold three months. One rule, every stock, every date — no hand-picked names, no per-stock overrides, no tuned weights.

Frozen at **2026-09-02T17:27:58Z** — see [`FROZEN.json`](FROZEN.json), which stores the full parameter set plus a SHA-256 of every strategy source file. The 2026 stress window was **sealed in code** (any post-2025 price read raised an exception) until that moment; the freeze timestamp is also the unseal timestamp, and every attempt is logged to `logs/seal.log`.

## Headline results

*In-sample, 1 Jan 2021 – 31 Dec 2025, point-in-time universe, net of all transaction costs.*

| Metric | Strategy | Nifty 500 TRI | Equal-weight PIT universe |
|---|---:|---:|---:|
| **Total Net PNL (primary rank)** | **₹2.739 cr** | ₹1.165 cr | ₹1.818 cr |
| Final value of ₹1 cr | **₹3.739 cr** | ₹2.165 cr | ₹2.818 cr |
| Absolute return | 273.92% | 116.47% | 181.84% |
| **Annualised return (CAGR)** | **30.23%** | 16.71% | 22.83% |
| **Maximum drawdown** | **−27.16%** | −18.44% | −22.59% |
| Sharpe — *competition definition* (annualised return ÷ SD of **daily** returns, rf=0) | **26.28** | 18.45 | 22.58 |
| Sharpe — standard (same numerator, denominator annualised ×√252) | **1.66** | 1.16 | 1.42 |
| Accuracy (% profitable trades) | **61.54%** | — | — |
| Gain-to-loss ratio | **1.78** | — | — |

**Trades:** 130 completed round trips · **320 legs** · 256.5% annual one-way turnover · ₹6,16,428 total transaction cost, charged on every leg inside the daily NAV path.

**Stress test (1 Jan – 30 Jun 2026, sealed until freeze): −0.22%**, against the Nifty 500 TRI's **−4.05%**. The window inverted the backtest regime (Nifty 50 −8 to −10%, Nifty IT −27.8%, smallcaps up). The book was flat — but it also trailed its own equal-weighted universe (+1.68%), so we claim **regime survival, not regime skill**.

> The competition Sharpe divides an *annual* numerator by a *daily* denominator, making it ≈√252 = 15.9× larger than any published Sharpe. We report it exactly as specified **and** flag the inconsistency rather than silently "fixing" it.

> **2025 was a losing year: −8.89%, while the benchmark gained +7.95%.** We show it. A five-year backtest with no bad year has a bug in it.

## The survivorship finding

We ran **identical strategy code** twice, changing only which universe it was allowed to pick from. **Basis: our BASELINE 12-month-momentum strategy, not the frozen submission above** — this experiment isolates the size of the distortion by holding the strategy constant, so its figures are deliberately *not* the ₹3.739 cr headline. Reproduce with `python survivorship_exhibit.py`; raw output in [`outputs/survivorship_exhibit.json`](outputs/survivorship_exhibit.json).

| Baseline momentum strategy | Point-in-time universe (honest) | Today's constituent lists (the shortcut) |
|---|---:|---:|
| Final value of ₹1 cr | **₹4.19 cr** | ₹5.58 cr |
| Total Net PNL | **₹3.19 cr** | ₹4.58 cr |
| CAGR | **33.23%** | 41.11% |
| Maximum drawdown | −32.65% | −33.61% |

**Using today's index lists inflates PNL by 43.7% and CAGR by 7.88 percentage points a year** — at the top of the 20–40% range the literature suggests. Note the drawdown barely moves: survivorship flatters the *return*, not the risk, which is what makes it so easy to miss. The uncomfortable consequence, stated plainly: on raw Total Net PNL an honest team looks *worse* than a sloppy one. We chose the honest number.

## Install

```bash
git clone https://github.com/kartikya2207/finesse-citadel-stockpitch.git
cd finesse-citadel-stockpitch
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.11+ (produced on 3.14.4). **No API keys, tokens or credentials are required** — every data source is public and unauthenticated, so there are no environment variables to set.

## Reproduce the result end to end

The large caches (`data/cache/` ≈63 MB, `data/bhav/` ≈73 MB) are **git-ignored** so the repo clones in seconds. Everything needed to regenerate them is committed.

```bash
# 1. Rebuild the caches: index lists, NSE bhavcopies, prices, shares, benchmarks,
#    then run the integrity checks. Needs network; ~10-20 min.
python reproduce_data.py
#    (add --skip-bhav to skip the 73 MB bhavcopy archive and go ~3x faster)

# 2. Reproduce the frozen backtest, the sealed stress test and the benchmark comparison.
#    NOTE: FROZEN.json already exists, so the stress window is legitimately unsealed.
#    Delete it only if you intend to re-run the freeze from scratch.
python freeze_and_build.py        # -> outputs/frozen_run.pkl
python build_exhibits.py          # -> outputs/exhibits.pkl (benchmark + EW universe)
python build_workbook.py          # -> FINESSE_CITADEL_SUBMISSION.xlsx
python verify_wb.py               # re-opens the workbook, checks every formula reference
python survivorship_exhibit.py    # -> outputs/survivorship_exhibit.json (the PIT vs today's-lists test)

# Optional: re-run the strategy search (119 trials, appends to outputs/trials.jsonl)
python run_sweep1.py    # 48 single signals and composites
python run_sweep2.py    # cadence x weighting x n x screen
python run_sweep3.py    # rebalance-phase robustness  <-- the decisive test
python run_sweep4.py    # quarterly phase stability + parameter sensitivity
```

`outputs/trials.jsonl` (every trial ever run) and the `sweep*.csv` summaries are committed, so the search history is auditable without re-running anything.

## Tests

```bash
python -m pytest tests -q      # 29 passed
```

Coverage includes a **hand-computed ₹98,010 round-trip case** (buy and sell a known notional, verify the NAV lands on the figure computed by hand with 0.1% charged on both legs) and **two look-ahead tests** asserting that no signal at a rebalance date can see data on or after that date.

## Repo structure

| Path | What it does |
|---|---|
| `src/config.py` | Single source of truth for every constant; `[SPEC]` = from the rules, `[ASSUMPTION]` = our choice |
| `src/data_fetch.py` | Downloads prices, shares outstanding and the benchmark; writes the parquet caches |
| `reproduce_data.py` | One-command rebuild of every git-ignored data cache, then the integrity checks |
| `src/integrity.py` | Data-quality checks against NSE bhavcopy (calendar reconciliation, unexplained jumps, level shifts, history gaps, backfill) |
| `survivorship_exhibit.py` | Runs the baseline strategy on the PIT universe and on today's constituent lists, and writes the comparison |
| `src/pit_universe.py` | Reconstructs point-in-time index membership; builds and cleans the price/volume panels |
| `src/signals.py` | All 47 features (momentum, volatility, trend, quality-of-trend, liquidity, size, beta/residual) |
| `src/strategies.py` | Declarative `Strategy` object → target weights; rebalance calendars, cap/floor waterfall, screens |
| `src/backtest.py` | Event-driven engine; charges 0.1% on every leg, tracks positions, legs and round trips |
| `src/metrics.py` | Both Sharpe definitions, CAGR, MDD, gain-to-loss, accuracy, trade statistics |
| `src/pipeline.py` | Loads the cached world once, runs a `Strategy`, compares to benchmark |
| `src/experiments.py` | The strategy zoo and the trials register (every evaluation is logged) |
| `src/seal.py` | Stress-window seal, `freeze_design()`, source-hash drift detection |
| `src/analysis.py` | Information coefficient, decile spreads, sub-period tables, concentration |
| `src/overfit.py` | Deflated-Sharpe and PBO machinery |
| `src/ml.py` | Gradient-boosting / hybrid models — **coded and deliberately never run** (see below) |
| `freeze_and_build.py` · `build_exhibits.py` · `build_workbook.py` · `verify_wb.py` | Freeze → run → exhibits → workbook → verification |
| `run_sweep1..4.py` | The four bounded search sweeps |
| `tests/` | 29 tests |

**Documents:** [`RESULTS.md`](RESULTS.md) (full numbers) · [`DEFENCE.md`](DEFENCE.md) (the jury argument) · [`TRIALS_REGISTER.md`](TRIALS_REGISTER.md) (all 119 trials) · [`ASSUMPTIONS.md`](ASSUMPTIONS.md) · [`PLAN.md`](PLAN.md) · [`QUESTIONS_FOR_ORGANISERS.md`](QUESTIONS_FOR_ORGANISERS.md).

## Data sources and how PIT membership is built

- **Prices / volumes / shares outstanding** — Yahoo Finance via `yfinance`, adjusted for splits and bonuses.
- **NSE bhavcopy** — official daily end-of-day files, used as the *arbiter* whenever Yahoo and the official record disagree. This is how we caught the corrupted adjusted series — CYBERTECH prints +9411% on 2025-01-10 then −99.1% three days later; KESORAMIND prints −94.9% on 2025-03-03 where the bhavcopy records +2.3%. A uniform rule (`clean_panels` Rule B) excludes any symbol with an unexplained single-day move and no recorded corporate action inside the window: **32 of 1,072 symbols, 3.0%**, listed in `outputs/cleaning_report.json`. That list includes real index members (YESBANK, VEDL, RAYMOND, ABFRL), so it removes potential losers as well as winners — it narrows the opportunity set rather than flattering the result. **No trading sessions were removed** (2,041 before and after): the 14 dates present in the stock panel but missing from the downloaded index series — Muhurat sessions, the 01-Feb-2025 Budget Saturday, 01-Jan-2021 — are real NSE sessions and were correctly kept. The benchmark is forward-filled across them, which slightly understates benchmark volatility and mildly flatters the benchmark, i.e. it is conservative for us.
- **Index constituent lists** — NSE's published `ind_nifty*list.csv` files (committed in `data/raw/`), used for *current* membership and sector tags only.
- **Benchmark** — Nifty 500. The freely downloadable series is a **price** index; we approximate the TRI by adding a constant dividend accrual. A 0.5pp error in that assumption moves the benchmark CAGR by 0.5pp, against our 13.5pp alpha.

**Point-in-time membership** is *reconstructed*, because NSE does not publish free historical constituent files. At each month-end we rank the traded universe by market capitalisation (price × shares outstanding, both as of that date), apply listing-date and trading-status filters so a stock cannot be selected before it listed or after it stopped trading, and assign the top 100 to the Nifty 100 sleeve and the appropriate rank bands to the Midcap 100 and Smallcap 100 sleeves. Delisted and suspended names remain in the panel until they genuinely stop trading, so they can be selected and exited normally. This is **directionally right rather than exact** — it will differ from the true historical lists at the margin — and it is flagged as `[OUR ASSUMPTION]` in `ASSUMPTIONS.md` and on workbook sheet 7. It is also vastly better than the alternative: see the survivorship table above.

## What we deliberately did not do

- **No ML.** `src/ml.py` is written and was never executed. ~60 monthly cross-sections is not a training set, and any result would need deflating against a 119-trial search. An undeflated ML number is a weaker answer to a quant jury than not running it.
- **No standalone fundamental model.** Our fundamentals are *restated*, not point-in-time, and reach back honestly only to July 2022. Ranking 2021 stocks on figures restated in 2026 is look-ahead bias.
- **We did not submit the highest number we found.** A pure 12-month momentum book on a semi-annual calendar scored ₹427L — but shifting that identical calendar by 1–5 months moves it between ₹222L and ₹427L. The rebalance phase is not information. We ranked candidates on the *stability* of their phase distribution (frozen strategy: std ₹24–30L; every rival: ₹67–84L) and accepted a lower headline. Workbook sheet 10.

## Known limitations

Only the mandated 0.1%/side is modelled — no STT, stamp duty, GST or slippage; at 256% turnover a realistic statutory add-on would cost roughly 4pp of CAGR, so **this is not a claim of live-tradeable net return**. Fractional shares assumed. "Maximum 10 stocks" is read as 10 *concurrent* holdings with quarterly rotation permitted — our single biggest interpretation risk, flagged in `ASSUMPTIONS.md`. Accuracy of 61.5% carries a ±8.4pp 95% interval on 130 trades. **40.9% of PNL came from 5 of those 130 trades**; HAL alone is 15.5%.
