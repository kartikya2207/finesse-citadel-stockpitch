# DEFENCE — one page

## 1. Lead with the number nobody else will show you

We ran the **identical strategy code** twice. The only thing we changed was which universe it was allowed to pick from. *(This experiment was run on our **baseline momentum strategy**, not the frozen submission — it isolates the size of the survivorship distortion by holding the strategy constant. The frozen strategy is reported on the honest point-in-time basis throughout.)*

| Baseline momentum strategy | Point-in-time universe (**the honest basis**) | Today's constituent lists (the shortcut) |
|---|---|---|
| Final value of ₹1cr | **₹2.52 cr** | ₹3.89 cr |
| Total Net PNL | **₹1.52 cr** | ₹2.89 cr |
| CAGR | **20.3%** | 31.3% |

**Using today's index lists inflates PNL by 91% and CAGR by 11.0 percentage points.** The literature suggested 20–40%. On a 3-index Indian universe over 2021–2025 — a window that contained a violent small-cap cycle — it is more than double that.

Say the uncomfortable part plainly: **on raw Total Net PNL, an honest team looks worse than a sloppy one.** A team that downloads today's Nifty Smallcap 100 list and backtests it to 2021 has selected only the stocks that succeeded enough to still be in the index in 2026. Their number is not a strategy result; it is a definition of the sample. We chose the honest number and we are asking to be judged on it. **If our PNL is compared against a team using current constituent lists, this table is the comparison that matters.**

## 2. Why this strategy

Four legs, each defensible in one sentence: risk-adjusted 12-month momentum (skip the last month), fraction of up months, shallowness of the trailing-year drawdown, and path efficiency. Equal weight 1.0 on each, z-scored. **Nothing was optimised.** Top 10, inverse-vol weighted, capped 20% / floored 5%, rebalanced quarterly.

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
- **CYBERTECH, KESORAMIND** — corrupt/mis-mapped adjusted price series, removed and re-sourced.
- **Muhurat trading sessions** — special one-hour Diwali sessions that Yahoo either omits or double-counts against the official trading calendar.
- **Four NSE holidays** that Yahoo stale-filled as zero-return trading days — these silently deflate daily volatility and therefore *inflate* every Sharpe ratio. Removed.

Every one of these makes our numbers *worse*. That is the point.

## 6. The out-of-sample answer

The Jan–Jun 2026 window was **sealed in code** — any attempt to read a post-2025 price raised an exception until `FROZEN.json` was written with a UTC timestamp and a SHA-256 of every strategy source file. Freeze time **2026-09-02T17:27:58Z**; that is also the unseal time. One-way door, every attempt logged.

The window inverted the regime we built in: Nifty 50 −8 to −10%, Nifty IT −27.8%, smallcaps up. A momentum book fitted to 2021–2025 should have been hurt.

**The frozen book returned −0.22%** against the Nifty 500 TRI's −4.05%.

It also **underperformed its own equal-weighted universe (+1.68%) by 1.9pp**. So we claim **regime survival, not regime skill**. Six months and 17 round trips prove robustness, not edge. The drawdown and consistency legs are what held it up — which is the strongest available evidence that selecting on stability rather than on the in-sample maximum was the right call.
