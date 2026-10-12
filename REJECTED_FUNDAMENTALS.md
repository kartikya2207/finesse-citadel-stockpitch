# Fundamental family — REJECTED, with evidence

Checked at T+40 this session against `data/cache/fundamentals_raw.parquet` (665,344 rows).
The brief permitted a fundamental *screen* from Jul-2022 onward. **It cannot be built without
violating hard constraint 8, so it was not built at all.**

Three independent blockers, any one of which is disqualifying:

**1. There is no filing-date column.** Schema is `[symbol, stmt, freq, period_end, item, value]`.
Constraint 8 requires fundamentals lagged to their SEBI-LODR *filing* date, never their
period-end. With only `period_end` available I would have to assume a lag (45 days? 60?).
An assumed lag is a guess, and a guess that is too short is look-ahead bias that would
silently inflate every result built on it.

**2. Quarterly coverage begins 2024-12-31, not Jul-2022.**

| period_end year | symbols with quarterly data |
|---|---|
| 2024 | 286 |
| 2025 | 644 |
| 2026 | 641 |

That is roughly the last 12 months of a 60-month backtest — 20% of the window, not the 70%
the brief assumed. Annual data reaches back to period_end 2021-09-30, but annual-only
figures refresh once a year and, with any realistic filing lag, the first usable observation
lands around Dec-2021.

**3. The data is restated, not point-in-time.** It was fetched in 2026, so a 2021 value is
the figure as restated today, not as reported then. Ranking 2021 stocks on numbers restated
in 2026 is look-ahead bias wearing a value-investing costume.

**Decision:** no fundamental screen, no standalone fundamental strategy, no hybrid with a
fundamental leg. The brief's own instruction applies: *"If you cannot do that without
look-ahead, do not do it at all."* We would rather score lower than show a number we cannot
defend line-by-line.
