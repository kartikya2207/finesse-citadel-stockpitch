# TRIALS REGISTER — every backtest we ran

Machine-readable source: `outputs/trials.jsonl` (one JSON row per trial: full parameter set + full metric set + timestamp). **119 trials.** Nothing was run and quietly excluded — the register's length *is* the multiple-testing count we would deflate against.

| Sweep | Trials | What was varied | Purpose |
|---|---:|---|---|
| `sweep1_signals` | 48 | 48 single signals & composites, all held at quarterly / inv-vol 20-5 cap / vol-q20 screen | Fair first pass across momentum, low-risk, trend, factor and composite families |
| `sweep2` | 29 | Cadence (quarterly / semi-annual / annual) × weighting (inv-vol-cap / equal) on the top 3 signals; then n=8 vs 10 and vol-screen on/off on the best 2; then 3 all-weather blends | Bounded cadence/weighting/size sweep |
| `sweep3_phase` | 30 | 5 candidates × 6 semi-annual rebalance phases (calendar shifted 0–5 months) | **The decisive test.** Is the headline number skill or calendar luck? |
| `sweep4` | 12 | 3 candidates × 3 quarterly phases, plus 3 config variants of the frozen strategy | Confirm quarterly is structurally less phase-dependent; parameter sensitivity |

By family: momentum 44 · robustness 42 · composite 18 · trend 6 · factor 5 · low-risk 4.

## The three results that actually mattered

**1. Sweep 1 said take `mom_9m` (₹293L, 31.5% CAGR).** Our own tripwire fired: >30% CAGR, and top-5 trades = 44% of PNL. Flagged, not frozen.

**2. Sweep 2 said take `mom_12m` semi-annual (₹427L, 39.5% CAGR, Sharpe 1.75).** Turnover halved vs quarterly but only ₹2L of the ₹108L improvement was cost saving — the other ₹106L was unexplained. That is a tripwire, not a discovery.

**3. Sweep 3 explained it, and killed both.** Net PNL in ₹ lakh, same strategy, calendar shifted:

| Candidate | φ0 | +1m | +2m | +3m | +4m | +5m | **std** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **COMP_allweather (FROZEN)** | 245 | 327 | 266 | 247 | 260 | 258 | **30** |
| mom_9m | 397 | 311 | 436 | 247 | 351 | 315 | 67 |
| mom_12m | **427** | 374 | 356 | **223** | 243 | 320 | 79 |
| rar_mom_12m | 270 | 367 | 347 | 182 | 247 | 308 | 68 |
| AW blended w/ rar_mom_12m | 383 | 401 | 353 | 174 | 276 | 331 | 84 |

The ₹427L headline is `mom_12m`'s **best** phase; its worst is ₹223L. Sweep 4 confirmed the same ordering at quarterly cadence (AWpure std ₹24L vs ₹70–78L for every rival) and confirmed that quarterly — 20 decisions instead of 10 — is structurally less phase-dependent.

## Not run, on purpose

- **ML / hybrid families (coded, never executed).** ~60 monthly cross-sections. Any result would need deflating for a 119-trial search, and there was no time to do that honestly. An undeflated ML number is a weaker jury answer than not running it.
- **Standalone fundamental strategies.** Fundamentals are restated, not point-in-time, and honest only from July 2022. Cannot be built for a 2021-start window without look-ahead.
- **The fundamental quality-screen overlay** (positive ROE / below-median D/E from Jul-2022, with the pre-2022 gap disclosed) was scoped and **not run** — it required wiring a new lagged panel into the feature set, and the phase-robustness finding was worth more per minute. Disclosed as untested.
- Full permutation grid (cadence × weighting × n × screens × sleeves × sector caps ≈ 900 cells), deliberately not swept: with 20 rebalances, that grid finds the maximum of a noise distribution.

## Deflation note

119 trials over ~20 independent rebalance decisions. The frozen strategy's in-sample standard Sharpe is 1.66. We make **no claim** that this survives a formal deflated-Sharpe correction, and we did not select on it. We selected on the *cross-phase stability* of the PNL distribution — a criterion that gets *harder*, not easier, as the search widens.
