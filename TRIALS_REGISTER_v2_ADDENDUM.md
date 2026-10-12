# TRIALS REGISTER — addendum, second search (2026-09-02)

Machine-readable: `outputs/trials_v2_with_search.jsonl` (**820 trials**). The committed
`outputs/trials.jsonl` was deliberately restored to its submitted 119-line state — this
session modified no tracked file.

| Sweep | Trials | What was varied |
|---|---:|---|
| (carried forward) | 119 | first search, already submitted |
| `searchA1` | 37 | every usable feature as a single-feature ranker |
| `searchA2` | 276 | 2/3/4-leg composites: momentum core × quality legs, plus each incumbent leg substituted |
| `searchB_phase` | 90 | six-phase dispersion on the 15 candidates clearing PNL + drawdown |
| `audit_phase6/3` | ~54 | phase tests inside the audit gate |
| neighbourhood | ~44 | single-leg perturbations of the winner |
| **total** | **820** | |

**This is the honest multiple-testing count.** Any deflated-Sharpe or PBO correction must
use 820, not 119. We make no claim that the challenger's Sharpe survives a formal deflation.

## Funnel

313 candidates evaluated at the incumbent's configuration → **36** beat the incumbent's PNL
(criterion a) → **15** also satisfied MDD ≥ −32% (criterion c) → **3** also passed phase
dispersion ≤ ₹30L (criterion b) → **1** cleared the full 7-point audit.

The phase gate is what did the work. It eliminated 12 of 15, including the highest-PNL
candidate of the entire search (`residR+up12`, ₹362.3L, σ = ₹33.4L) and three others above
₹300L whose dispersion ran to ₹41–110L. `mom_3m` scored ₹279L with σ = **₹109.6L** — a
range of ₹250L to ₹535L depending purely on which month the calendar started.

## Families not run, and why

- **Fundamental** — rejected outright, see `REJECTED_FUNDAMENTALS.md`. No filing-date column
  (constraint 8 unsatisfiable), quarterly coverage begins 2024-12-31 rather than Jul-2022,
  and the data is restated rather than point-in-time. Three independent blockers.
- **ML / hybrid** — not run. With ~20 rebalances and 820 trials already on the register, any
  ML result would need a deflation we cannot perform credibly, and an ML ranker fails
  criterion (f) — it cannot be explained to a jury without appealing to the backtest. The
  honest answer remains that we knew it would not survive and did not run it.
