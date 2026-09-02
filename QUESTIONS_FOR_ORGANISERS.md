# Questions for the Organisers

Ranked by how much the answer changes the build. For every one of these we have proceeded
with a stated best assumption (see `ASSUMPTIONS.md`) and, where cheap, built the alternative
so it can be switched with one parameter.

---

## Tier 1 — the answer changes the submitted portfolio

**Q1. Does "maximum 10 stocks" cap CONCURRENT holdings, or total distinct names ever held?**
*Our assumption:* concurrent holdings; rotation permitted.
*Why we think so:* the submission must report total trades, trades per stock, turnover,
accuracy and gain-to-loss ratio. Every one of those is degenerate for a 10-name
buy-and-hold portfolio (10 trades, accuracy on n=10, turnover 0%). Requiring them implies
rotation is expected.
*Impact if wrong:* total. A no-rotation reading forces a single-basket buy-and-hold and
changes the entire methodology. We have built the buy-and-hold variant as a one-switch
alternate (`cadence="buyhold"`) and report it alongside.

**Q2. Is the universe point-in-time, or may we use today's published constituent lists?**
*Our assumption:* point-in-time. A stock counts only if it was in Nifty 100 / Midcap 100 /
Smallcap 100 *at the time we held it*.
*Why it matters more than anything else here:* on an identical strategy, using today's lists
raised Total Net PNL from **₹1.52 cr to ₹2.89 cr — a 91% inflation, +11.0pp of CAGR**. If
the intended reading is "today's lists", every honest team is scored against inflated
numbers. We would strongly urge the point-in-time reading, and we submit both figures.

**Q3. Is 0.1% per side, or 0.1% per completed round trip?**
*Our assumption:* per side, i.e. charged on both the buy and the sell (~0.2% round trip).
*Reading:* the rules say "0.1% per transaction"; a buy and a sell are two transactions.
*Impact:* on our submitted strategy total costs are ₹5.8L over 5 years. The round-trip
reading halves that and adds roughly ₹2.9L to Total Net PNL.

**Q4. Does the stated 0.1% already include STT, or should statutory charges be added?**
*Our assumption:* it is the all-in charge, and we do NOT add STT on top.
*Why:* the rules attribute the 0.1% to "SEBI guidelines", which most plausibly refers to the
0.1% delivery STT itself. Adding STT again would double-count. We report a cost-sensitivity
ladder at 0.10% / 0.12% / 0.15% / 0.25% per side so the ranking is visible under either reading.

## Tier 2 — the answer changes the reported numbers, not the portfolio

**Q5. Which benchmark, and PRI or TRI?**
*Our assumption:* Nifty 500 **TRI**.
*Why:* the eligible universe spans large, mid and small caps, so Nifty 100 flatters a
mid/small-tilted book. Our NAV is total return (dividends reinvested), so a price index is
not a like-for-like comparison. The downloadable series is a price index, so we add a
constant 1.20% p.a. dividend accrual and show sensitivity from 0.9% to 1.5%.
*Impact:* Nifty 500 PRI over 2021-25 returns roughly 1.2pp p.a. less than TRI, which flatters
us. We chose the harder comparison.

**Q6. Confirm the Sharpe denominator.**
The rules define Sharpe as *Annualised Return ÷ Standard Deviation of Daily Returns* with
rf = 0. That is an annual numerator over a daily denominator, so it reads about √252 ≈ 15.9x
larger than the conventional Sharpe ratio. We report it **exactly as specified** (our figure
is ~16-24) and print the conventional figure (~1.0-1.5) immediately beside it, each with its
formula written into an adjacent cell. Please confirm the intended definition so the
comparison across teams is on one basis.

**Q7. Is portfolio return total return with dividends reinvested, or price return only?**
*Our assumption:* total return, dividends reinvested into the same stock on the ex-date.
*Impact:* roughly +1.0 to +1.5pp p.a. on the reported figure. If price-return-only is
intended, every team's number falls by a similar amount and the ranking is largely unchanged,
but the benchmark basis must match.

**Q8. What counts as "a trade" for Accuracy and Gain-to-Loss Ratio?**
*Our assumption:* one completed round trip in a stock (buy → position fully closed).
We also report the per-leg count. On our submitted strategy that is 152 round trips vs 342
legs, and the two definitions give materially different Accuracy figures.
*Note:* Accuracy and Gain-to-Loss on fewer than ~30 round trips carry very wide confidence
intervals. We flag this wherever we report them rather than headlining a number built on a
dozen trades.

## Tier 3 — procedural

**Q9. How will the Jan–Jun 2026 stress test be run — frozen final weights held through the
window, or a live re-run of the methodology with its own rebalances?**
*Our assumption:* live re-run of the same methodology. We report both, because a frozen-weight
test measures a single basket while a live re-run measures the *strategy*, and for a
quarterly-rotating book the two can differ substantially.

**Q10. Is intra-period cash allowed (i.e. may the model be less than 100% invested)?**
*Our assumption:* we stay effectively fully invested. Cash arises only from the transaction
costs themselves and from share rounding. We do not use a market-timing cash overlay in the
submitted model — partly because it sits awkwardly with "the same core methodology applied
across all 10 stocks", and we would rather not rely on a rule reading we cannot confirm.

**Q11. Are fractional shares acceptable, or must holdings be whole shares?**
*Our assumption:* whole shares are the realistic case. Our primary engine holds fractional
total-return units (the standard treatment, exact for dividend reinvestment) and we report an
integer-share variant as a robustness check; the difference in terminal value is under 0.1%.

**Q12. May the portfolio hold the same stock across non-adjacent periods (exit and later
re-enter)?** *Our assumption:* yes. This affects how round trips are counted, not what we hold.
