# SEARCH PLAN — second search, post-unseal

**Session date:** 2026-09-02 · **Team Avocado, IIT Bombay** · Finesse × Citadel Round 2
**Status of repo at session start:** `3be17fe`, clean tree, submitted state. **Nothing will be committed or pushed this session.**

## Purpose

A second, broader strategy search to test whether the frozen incumbent can be beaten *legitimately*. The incumbent stands unless a challenger clears all six replacement criteria. **Keeping the incumbent is an acceptable, expected outcome.**

## The incumbent (target to beat)

`COMP_allweather` — quarterly · top-10 · drop most-volatile 20% · score = equal-weighted average of four cross-sectional percentile ranks (`rar_mom_12m_skip1`, `pct_up_months_12m`, `max_dd_1y`, `efficiency_6m`) · inverse-vol weighted, 20% cap / 5% floor by waterfall.

PNL **₹2,73,92,323** · CAGR 30.23% · MDD −27.16% · Sharpe 26.28 / 1.66 · accuracy 61.54% (130 round trips) · G:L 1.78 · 320 legs · phase σ ₹24L · stress −0.22%.

## Replacement criteria (ALL must pass)

| # | Criterion | Threshold |
|---|---|---|
| a | Total Net PNL | > ₹2,73,92,323 |
| b | Rebalance-phase σ across 6 phases | ≤ ₹30L |
| c | Maximum drawdown | ≥ −32% (no worse) |
| d | Hard constraints proven in code | all |
| e | Clean 7-point audit | all |
| f | Explainable in 4 sentences without appeal to the backtest | yes |

## Contamination control — the central integrity problem

The Jan–Jun 2026 window was unsealed on 2026-09-02T17:27:58Z. Anything selected today is chosen by a process that has already seen the out-of-sample outcome.

**Control used: physical truncation, not an assertion.** The entire search runs on a world whose price panels and every derived feature are clipped to **≤ 2025-12-31** before any candidate is scored (`src/search_guard.py`). Contamination becomes impossible by construction rather than merely detected. A hard assertion fires on top of that if any panel or feature carries a post-2025 date.

**Validation of the control:** the incumbent is re-run on the truncated world and must reproduce ₹27,392,323 exactly. All features are backward-looking rolling windows, so truncating the tail must be a no-op in-sample; if it is not, the guard has found a real look-ahead bug in the incumbent and that takes priority over the search.

2026 is touched only *after* a winner is chosen, as a report-only diagnostic. It never breaks a tie. Ties break on phase stability, then explainability.

## Search families (T+10–75)

1. **Quant / factor** — momentum lookbacks, residual momentum, low-vol, low-beta, size, trend and absolute-momentum overlays, alternative aggregations of the 47 features, multi-factor composites.
2. **Permutations** — cadence, weighting (equal / inv-vol / risk-parity / capped), n ∈ {5,8,10}, screens, sleeves, rank-vs-z aggregation, cap/floor levels.
3. **Fundamental screen only** — layered on a price ranker from Jul-2022, pre-Jul-2022 rebalances unscreened, gap disclosed. Fundamentals are restated, not point-in-time. **Abandon entirely if look-ahead cannot be excluded.**
4. **ML** — regularised linear, gradient boosting, walk-forward only, deflated reporting. ~60 monthly cross-sections; expected to fail criterion (f).
5. **Hybrids** — screen→ranker, regime-conditional, ensembles.

Every variant is logged to `outputs/trials.jsonl`. The register length is the honest multiple-testing count.

## Audit gate (7 points, required before any candidate is eligible)

1. Constraints in code · 2. No look-ahead (shift test + 2026 assertion) · 3. Independent metric recomputation with denominators printed · 4. Trade-log ↔ NAV PNL reconciliation to the paisa · 5. Tripwire (CAGR > 35%, std Sharpe > 2.5, or drawdown shallower than benchmark in both 2022 and 2025) · 6. Six-phase dispersion · 7. 29 existing tests still pass.

## Disclosure obligation (either outcome)

- **Incumbent stands:** state that its seal held and that a second, wider search failed to beat it.
- **Challenger wins:** state plainly that it was selected *after* the 2026 unseal, and that its 2026 number is therefore weaker evidence than the incumbent's was.

## Git

**Frozen.** No commits, no pushes, no branches, no history edits. Tracked files are not overwritten — modified versions go to new filenames. Submitted state must remain recoverable with a plain `git checkout .`.
