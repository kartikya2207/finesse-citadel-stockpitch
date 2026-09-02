# DEFENCE — one page

## 1. Lead with the number nobody else will show you

We ran the **identical strategy code** twice. The only thing we changed was which universe it was allowed to pick from. *(This experiment was run on our **baseline momentum strategy**, not the frozen submission — it isolates the size of the survivorship distortion by holding the strategy constant. The frozen strategy is reported on the honest point-in-time basis throughout.)*

| Baseline momentum strategy | Point-in-time universe (**the honest basis**) | Today's constituent lists (the shortcut) |
|---|---|---|
| Final value of ₹1cr | **₹4.19 cr** | ₹5.58 cr |
| Total Net PNL | **₹3.19 cr** | ₹4.58 cr |
| CAGR | **33.23%** | 41.11% |
| Maximum drawdown | −32.65% | −33.61% |

**Using today's index lists inflates PNL by 43.7% and CAGR by 7.88 percentage points a year.** That sits at the top of the 20–40% range the literature suggests. Note what does *not* move: the drawdown is −32.7% either way. Survivorship flatters the return and leaves the risk untouched, which is precisely why it is so easy to miss — and why a PNL league table without a universe audit compares nothing.

Say the uncomfortable part plainly: **on raw Total Net PNL, an honest team looks worse than a sloppy one.** A team that downloads today's Nifty Smallcap 100 list and backtests it to 2021 has selected only the stocks that succeeded enough to still be in the index in 2026. Their number is not a strategy result; it is a definition of the sample. We chose the honest number and we are asking to be judged on it. **If our PNL is compared against a team using current constituent lists, this table is the comparison that matters.**

## 2. Why this strategy

Four legs, each defensible in one sentence: risk-adjusted 12-month momentum (skip the last month), fraction of up months, shallowness of the trailing-year drawdown, and path efficiency. Equal weight 1.0 on each, combined as cross-sectional percentile ranks (not z-scores, so a single +400% smallcap cannot hijack a leg). **Nothing was optimised.** Top 10, inverse-vol weighted, capped 20% / floored 5%, rebalanced quarterly.

We did **not** freeze the highest number we found. A pure 12-month momentum book on a semi-annual calendar scored **₹427L**. We rejected it, because when we shifted the identical calendar by 1–5 months the same strategy printed anywhere from **₹222L to ₹427L**. The rebalance phase is not information — nobody in January 2021 knew that starting in January rather than April was worth ₹200 lakh. Our frozen strategy's spread across the same six phases is ₹81L (std ₹24–30L); every momentum rival's is ₹67–84L std. **We ranked on the stability of the phase distribution and accepted a lower headline.** That is sheet 10 of the workbook and it is our best exhibit.

## 3. What it is exposed to, and the concentration stat

**Top 5 of 130 round trips produced 40.9% of PNL.** HAL alone is 15.5% (+₹42.4L, held Jul-2022 → Jul-2024). We do not claim this away. Two mitigations are real: the 20% cap means no name ever dominated the *book*, only the P&L attribution; and HAL, RECLTD, TRENT and NTPC were each re-selected by the same rule across 4–9 consecutive rebalances, not caught once by luck. What remains true: **strip the top 5 trades and this is a good strategy, not a spectacular one.** That is the nature of a 10-stock momentum book.

**What would break it:** a sharp momentum-to-value rotation; a sustained choppy market where the efficiency leg has nothing to find; and turnover — 256% p.a. one-way. We model only the mandated 0.1%/side (₹6.16L total). Adding realistic STT/stamp/GST would cost roughly 4pp of CAGR. **We do not claim this is a live-tradeable net return.**

**2025 was a losing year: −8.9% while the Nifty 500 TRI gained +8.0%.** We show it. A five-year backtest with no bad year has a bug in it.

## 4. What we deliberately did NOT do

- **No ML.** Gradient-boosting and hybrid models were coded and never run. ~60 monthly cross-sections is not a training set; any number we produced would need deflating for the search, and an undeflated ML result is worth less to a jury than the sentence "we knew it wouldn't survive and didn't run it."
- **No standalone fundamental model.** Our fundamentals are *restated*, not point-in-time, and reach back honestly only to July 2022. Ranking 2021 stocks on numbers restated in 2026 is look-ahead bias wearing a value-investing costume. We would rather score lower.
- **No hindsight-fitted basket.** No name is ever selected by hand. One rule, every stock, every date.
- **No cherry-picked calendar.** See §2.

## 5. Data errors we caught and fixed

All verified line-by-line against NSE bhavcopy, not against another vendor:
- **Corrupted adjusted price series.** CYBERTECH prints +9411% on 2025-01-10 then −99.1% three days later; KESORAMIND prints −94.9% on 2025-03-03 where the bhavcopy records +2.3%. A uniform rule excludes any symbol with an unexplained single-day move and no recorded corporate action inside the window: **32 of 1,072 symbols (3.0%)**, all listed in `outputs/cleaning_report.json`. The list includes real index members — YESBANK, VEDL, RAYMOND, ABFRL — so it strips out potential losers as well as winners and narrows what we could have bought.
- **Calendar reconciliation.** 14 dates sit in the stock panel but not in the downloaded index series: Muhurat sessions, the 01-Feb-2025 Budget Saturday, 01-Jan-2021. We checked each against the official calendar and **kept all of them** — they are real sessions. **Zero trading sessions were removed** (2,041 before and after). The benchmark is forward-filled across those dates, which slightly understates benchmark volatility and mildly flatters the benchmark: conservative for us, not for us.

We are stating the exclusion count plainly because 3% of the universe is not a rounding error, and because the direction of the effect is to shrink our opportunity set, not inflate it.

## 6. The out-of-sample answer

The Jan–Jun 2026 window was **sealed in code** — any attempt to read a post-2025 price raised an exception until `FROZEN.json` was written with a UTC timestamp and a SHA-256 of every strategy source file. Freeze time **2026-09-02T17:27:58Z**; that is also the unseal time. One-way door, every attempt logged.

The window inverted the regime we built in: Nifty 50 −8 to −10%, Nifty IT −27.8%, smallcaps up. A momentum book fitted to 2021–2025 should have been hurt.

**The frozen book returned −0.22%** against the Nifty 500 TRI's −4.05%.

It also **underperformed its own equal-weighted universe (+1.68%) by 1.9pp**. So we claim **regime survival, not regime skill**. Six months and 17 round trips prove robustness, not edge. The drawdown and consistency legs are what held it up — which is the strongest available evidence that selecting on stability rather than on the in-sample maximum was the right call.
