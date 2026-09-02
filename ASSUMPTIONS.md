# Assumptions Register

Running register. Every entry is tagged:

- **[CONFIRMED BY RULES]** — stated in the problem statement.
- **[OUR ASSUMPTION]** — our reading; needs organiser confirmation (see `QUESTIONS_FOR_ORGANISERS.md`).
- **[UNVERIFIABLE]** — cannot be checked with the data available; the residual error is stated.

---

## A. Competition mechanics

| # | Assumption | Tag | Impact if wrong |
|---|---|---|---|
| A1 | Corpus = ₹1,00,00,000, deployed on the first trading day of 2021 | CONFIRMED BY RULES | — |
| A2 | Maximum 10 stocks means ≤10 **concurrent** holdings; rotation is allowed | OUR ASSUMPTION | Total — forces buy-and-hold. Alternate built (`cadence="buyhold"`). |
| A3 | 0.1% is charged **per side**, on absolute traded notional, on every leg | OUR ASSUMPTION | ~₹2.9L of PNL on our book. Ladder reported. |
| A4 | The stated 0.1% is the **all-in** charge; STT is not added on top | OUR ASSUMPTION | Costs would roughly double. Sensitivity at 0.12/0.15/0.25% reported. |
| A5 | Universe membership is **point-in-time** | OUR ASSUMPTION | **91% of PNL.** Measured, not guessed — see `RESULTS.md`. |
| A6 | Benchmark = Nifty 500 **TRI** | OUR ASSUMPTION | Changes the reported excess return only, not the portfolio. |
| A7 | Portfolio return is **total return**, dividends reinvested in the same stock | OUR ASSUMPTION | ~+1.0 to +1.5pp p.a. |
| A8 | "A trade" = one completed round trip (buy → fully closed) | OUR ASSUMPTION | Accuracy and gain-to-loss change materially. Both definitions reported. |
| A9 | Execution at the **closing price** of the rebalance date | OUR ASSUMPTION | Open-price execution would change results by a few tenths of a percent. |
| A10 | Cash earns 0% | OUR ASSUMPTION | Conservative. Cash is only the cost residue, so the effect is <0.05%. |
| A11 | Fractional total-return units held; integer-share variant reported | OUR ASSUMPTION | <0.1% of terminal value. |

## B. Universe reconstruction

| # | Assumption | Tag | Impact if wrong |
|---|---|---|---|
| B1 | Nifty 100 = full-market-cap ranks 1–100 | CONFIRMED BY RULES (NSE methodology) | — |
| B2 | Nifty Midcap 100 ≈ ranks 101–200; Nifty Smallcap 100 ≈ ranks 251–350 | OUR ASSUMPTION | Reproduces today's published union at **79.3%** (Nifty100 94%, Midcap100 74%, Smallcap100 61%). Band tuning gave no material improvement (best alternative 79.1% F1 vs 77.7% for the methodology bands), so the published rule was kept rather than fitted. |
| B3 | Semi-annual review: cut-off 31 Jan / 31 Jul, effective 1 Apr / 1 Oct; membership frozen between reviews | CONFIRMED BY RULES (NSE methodology) | — |
| B4 | Selection uses the 6-month average full market capitalisation to the cut-off | CONFIRMED BY RULES (NSE methodology) | — |
| B5 | `full_mcap = close × cumulative future split factor × as-reported shares outstanding` | OUR ASSUMPTION | Verified: RELIANCE ₹17.4 lakh cr (2026) and ₹12.4 lakh cr (Jan 2021) — both correct. |
| B6 | Rights issues carry a Yahoo price factor absent from the splits column | UNVERIFIABLE | Understates pre-event market cap by a few percent (RELIANCE 2020 1:15 rights ≈ 9%). Cannot move a name across a 100-name band except at the margin. |
| B7 | NSE's index-maintenance buffer rules (constituent inertia) are **not** modelled | OUR ASSUMPTION | Part of the 20% reconstruction gap. Modelling it would raise the fit but would be tuned to today's list. |
| B8 | Master ticker list = NSE index CSVs ∪ NSE bhavcopy top-500-by-turnover at 12 half-yearly samples 2021–2026 ∪ known departed names | OUR ASSUMPTION | Recovers names that collapsed out of today's lists (DELTACORP, JPASSOCIAT, GMRINFRA, DHANI, …). Residual coverage reported in `RESULTS.md`. |
| B9 | ETFs excluded from the equity universe by name pattern | OUR ASSUMPTION | ETFs are not stocks and are not index constituents. Low risk. |

## C. Data

| # | Assumption | Tag | Impact if wrong |
|---|---|---|---|
| C1 | yfinance `Adj Close` = total return (splits + dividends); `Close` = capital-adjusted only | CONFIRMED (verified empirically) | TCS 2019-12-30 Close 2183.20 = true raw close; Adj Close 1844.29. |
| C2 | `get_shares_full` returns as-reported share counts | CONFIRMED (verified empirically) | RELIANCE 5.93bn (2019) → 13.53bn (post 1:1 bonus); IRCTC 160m → 800m (post 1:5 split). |
| C3 | A missing price is carried forward, not treated as a zero return; a name stale >15 trading days is force-liquidated at its last traded price | OUR ASSUMPTION | Explicit rule; no silent NaN. Zero such events occurred on the submitted strategy. |
| C4 | Nifty 500 price index + 1.20% p.a. constant dividend accrual = TRI | OUR ASSUMPTION | Sensitivity 0.9%–1.5% reported. |
| C5 | Fundamental data is available and honest only from **July 2022** onward | CONFIRMED (verified) | yfinance annual statements reach period-end March 2022 only; quarterly reach December 2024. 30% of the backtest window has no fundamental data. |
| C6 | yfinance fundamentals are as-currently-restated, not point-in-time | UNVERIFIABLE | Independent second reason the fundamental family cannot be the full-window primary. |
| C7 | SEBI-LODR filing lag: quarterly ≤45 days after quarter-end, annual audited ≤60 days | CONFIRMED BY RULES (SEBI LODR) | Applied wherever fundamentals are used. |

## D. Modelling

| # | Assumption | Tag | Impact if wrong |
|---|---|---|---|
| D1 | Signals read the last trading day **strictly before** the rebalance; execution that day's close | OUR ASSUMPTION | Enforced in code and asserted by `test_future_data_cannot_change_past_signals`. |
| D2 | Liquidity floor: ₹2 crore median 60-day traded value; price ≥ ₹10; ≥252 days of history | OUR ASSUMPTION | Keeps the book executable at ₹1 crore. Sensitivity reported. |
| D3 | Cross-sectional **percentile ranks**, not z-scores, for composite scoring | OUR ASSUMPTION | A single smallcap 10-bagger would otherwise dominate a z-scored composite. |
| D4 | Composite factor weights are round numbers, never tuned decimals | OUR ASSUMPTION | Deliberate. A tuned decimal weight on 5 years of data is noise dressed as precision. |
| D5 | 252 trading days per year; calendar-year basis (365.25 days) for annualised return | OUR ASSUMPTION | Both bases reported; they differ by <0.1pp. |

## E. Known contamination — declared

| # | Item | Tag |
|---|---|---|
| E1 | The task prompt states the Jan–Jun 2026 outcome (Nifty 50 −8..−10%, Smallcap 100 +6..12%, Nifty IT −27.8%, Defence +21%) before the design was frozen. This cannot be un-known. **Mitigation:** no rule in the submitted model references a sector or size sleeve chosen because of that information; every tilt is justified by in-sample evidence alone; `FROZEN.json` records the design and its source hashes before any 2026 result was computed. | DECLARED |
| E2 | `RESEARCH_BRIEF.md` was absent from disk. The prompt's Part 2 summary was used as the baseline spec instead. | DECLARED |
