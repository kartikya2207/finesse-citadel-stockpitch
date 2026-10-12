# Drop-in disclosure text — use ONLY if the challenger is adopted

Ready-to-paste paragraphs. Nothing here has been applied to `README.md`, `RESULTS.md` or
`DEFENCE.md` — those remain exactly as submitted.

---

## For README.md and RESULTS.md (place directly under the headline results table)

> **How this strategy was selected — read before the numbers.** This strategy was chosen in a
> second search run **after** our Jan–Jun 2026 stress window had already been unsealed. The
> search itself was clean: it ran on a world physically truncated to 31 Dec 2025, so no 2026
> observation could enter any signal, screen, ranking, parameter choice or tie-break, and we
> validated that truncation by confirming our previously frozen strategy reproduces its
> ₹2,73,92,323 to the paisa on the truncated data. But the *people* running the search had
> already seen how the earlier strategy performed in 2026. That is an unfixable weakening of
> the evidence, and we state it rather than let a jury find it. **Our previously frozen
> COMP_allweather was sealed before anyone had seen 2026 and returned −0.22% there; this
> strategy returns −1.00% over the same window.** Both beat the Nifty 500 TRI's −4.05%. The
> 2026 figures for this strategy are a report-only diagnostic, computed after the design was
> written to `FROZEN_CHALLENGER.json`, and they were never used to choose between candidates.

## For DEFENCE.md (new section, place after the survivorship section)

> ### Why our out-of-sample evidence is weaker than it looks
>
> We ran two searches. The first produced COMP_allweather, which we froze **before** the 2026
> window was opened; it then survived a regime inversion at −0.22% against an index that fell
> 4.05%. That is a genuine sealed test and it is the strongest evidence in this submission.
>
> The second search, run after the unseal, produced the strategy we are presenting here. We
> controlled it as tightly as the situation allows — the search world was truncated to 31 Dec
> 2025 so 2026 was *absent* rather than merely forbidden, and we proved the truncation was a
> no-op by reproducing the earlier strategy's PNL exactly on it. Selection used 2021–2025 only.
> Even so, we will not claim this strategy's 2026 number as clean out-of-sample evidence,
> because we already knew what 2026 looked like when we went looking. If you discount that
> number, you are right to.
>
> What we can defend without reference to 2026: it clears every constraint in code, its PNL
> reconciles to the trade log to the paisa, and its rebalance-phase dispersion is ₹10.7 lakh
> against the previous strategy's ₹30.1 lakh — meaning far less of its result depends on which
> month the calendar happened to start. We also disclose the weakness: the specification sits
> on a sharper peak than its predecessor. Substituting any single leg costs between ₹41 and
> ₹148 lakh, and while that gradient is monotone and economically sensible, a peak that sharp
> across only 20 rebalance decisions is partly specific to this sample.

## For the Assumptions Register (new row)

| Item | Tag | What we did | Impact if we are wrong |
|---|---|---|---|
| Strategy selected post-unseal | **[OUR ASSUMPTION — MATERIAL]** | Second search run after the 2026 window was opened. Search world physically truncated to 2025-12-31; truncation validated as a no-op against the previously frozen strategy; 2026 used only as a report-only diagnostic after freezing. | The 2026 result is weaker evidence than a sealed test. A jury is entitled to discount it entirely and judge this strategy on 2021–2025 and on its phase stability alone. We would still stand behind it on that basis. |

---

## If the incumbent is kept instead (the alternative disclosure)

> **A second search did not displace this strategy.** After the stress window was unsealed we
> ran a wider search — 701 further trials, 820 in total — across single factors, multi-factor
> composites and every permutation of cadence, weighting, size and screen. One candidate beat
> this strategy on in-sample PNL and passed a full seven-point audit. We did not submit it,
> because it was selected after our seal was broken and could not make the claim this strategy
> can: frozen before anyone had seen 2026, and it held. We are reporting the search rather than
> quietly discarding it, and the full comparison is in `DECISION.md`.
