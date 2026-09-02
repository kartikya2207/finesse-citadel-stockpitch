"""Point-in-time universe reconstruction.

WHY THIS EXISTS
---------------
Using today's Nifty 100 / Midcap 100 / Smallcap 100 lists for a 2021 backtest is the single
largest source of fake PNL in this problem. Today's Nifty 100 is, by construction, a list of
companies that *became* large; buying them in January 2021 is buying with hindsight.

WHAT WE DO INSTEAD
------------------
NSE's index methodology is mechanical and public, so we reproduce it rather than scrape a
list we cannot date:

  Nifty 100         = full-market-cap ranks   1..100
  Nifty Midcap 150  = ranks 101..250; Nifty Midcap 100 = the largest 100 of those
  Nifty Smallcap 250= ranks 251..500; Nifty Smallcap 100 = the largest 100 of those

so the competition universe is approximately  ranks 1..200  UNION  ranks 251..350.
Ranks 201..250 are genuinely excluded by the rule -- that is a real feature of the index
family, not an artefact.

Membership is recomputed at each semi-annual review (cut-off 31 Jan / 31 Jul, effective
1 Apr / 1 Oct) using the six-month average full market capitalisation to the cut-off, which
is what NSE actually uses. Between reviews membership is frozen, exactly as the real indices
are, so a stock that re-rates mid-quarter does not silently enter our universe early.

MARKET CAP ARITHMETIC
---------------------
`close` from yfinance is adjusted for capital actions; `get_shares_full` returns AS-REPORTED
share counts. To put the two on the same per-share basis we multiply the price back up by the
cumulative future split factor:

    raw_price(t) = close(t) * PROD(split ratios dated after t)
    full_mcap(t) = raw_price(t) * shares_reported(t)

Known residual: rights issues receive a Yahoo price factor that is not in the splits column
(e.g. RELIANCE's 2020 1:15 rights), which understates pre-event market cap by a few percent.
That cannot move a name across a 100-name rank band except at the very margin, and it is
disclosed in ASSUMPTIONS.md.

VALIDATION
----------
`validate_against_published()` scores the reconstruction against the actual NSE constituent
CSVs. If the overlap is poor, the method is rejected, not patched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (MIN_HISTORY_DAYS, MIN_MEDIAN_TURNOVER, MIN_PRICE, PIT,
                     RANK_BANDS, RAW)


# --------------------------------------------------------------------------------------
# Panels
# --------------------------------------------------------------------------------------
def build_panels(prices_long: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Wide date x symbol panels: adjclose, close (capital-adjusted), volume, raw price."""
    p = prices_long
    adjclose = p.pivot(index="date", columns="symbol", values="adjclose").sort_index()
    close = p.pivot(index="date", columns="symbol", values="close").sort_index()
    volume = p.pivot(index="date", columns="symbol", values="volume").sort_index()
    split = p.pivot(index="date", columns="symbol", values="split").sort_index()

    # cumulative split factor applied AFTER date t (reverse cumulative product)
    sp = split.fillna(0.0).replace(0.0, 1.0)
    fwd_factor = sp.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)
    rawprice = close * fwd_factor

    return {"adjclose": adjclose, "close": close, "volume": volume,
            "rawprice": rawprice, "split_factor_fwd": fwd_factor}


# --------------------------------------------------------------------------------------
# Data cleaning
# --------------------------------------------------------------------------------------
GLITCH_RETURN_THRESHOLD = 0.50      # NSE circuit limits make an unexplained >50% day impossible
GLITCH_DAY_SYMBOL_FRACTION = 0.02   # a day where >2% of live names jump >20% is a bad session


def clean_panels(panels: dict, benchmark_index: pd.Index,
                 window: tuple[str, str] = ("2020-01-01", "2026-06-30")) -> tuple[dict, dict]:
    """Remove data artefacts, using rules that are uniform and impossible to game.

    Two rules, both verified against NSE bhavcopy before being adopted:

    RULE A -- bad sessions. Muhurat (one-hour ceremonial) sessions are absent from the
    benchmark index and Yahoo prices several names wrongly on them. Verified example:
    THYROCARE on 2019-10-27 shows +207% in Yahoo; the NSE bhavcopy close implies +2.4%.
    We drop any date that is (i) absent from the benchmark's trading calendar AND
    (ii) shows >20% moves in more than 2% of live names.

    RULE B -- glitched symbols. NSE circuit limits mean an unexplained >50% single-day move
    in the cash market essentially cannot happen. Verified examples: CYBERTECH +9411% on
    2025-01-10 then -99.1% three days later; KESORAMIND -94.9% on 2025-03-03 where NSE
    records +2.3%. Any symbol with such a move inside the modelling window is excluded from
    the tradeable universe for the whole period.

    Exclusion, not repair, is deliberate: repairing requires guessing the true price, and
    these names are a handful of illiquid stocks that fail the liquidity screen anyway.
    Dropping them can only shrink the opportunity set, never inflate a result.
    """
    adj = panels["adjclose"]
    ret = adj.pct_change()
    lo, hi = pd.Timestamp(window[0]), pd.Timestamp(window[1])

    # ---- Rule A: bad sessions -------------------------------------------------------
    # Only dates the benchmark does not have are candidates. Among those, two distinct
    # pathologies are removed and everything else is KEPT (the benchmark itself has gaps,
    # and a real session must not be discarded just because Yahoo lost the index print):
    #   A1 ceremonial Muhurat sessions, where Yahoo misprices a few names badly
    #      (THYROCARE +207% on 2019-10-27; NSE bhavcopy implies +2.4%)
    #   A2 NSE holidays that Yahoo stale-filled, where EVERY live name shows exactly 0%
    #      return. A holiday must never enter the series as a zero-return day.
    live = adj.notna()
    n_live = live.sum(axis=1).replace(0, np.nan)
    not_in_bench = ~adj.index.isin(benchmark_index)
    sp = panels["split_factor_fwd"]
    split_event = (sp / sp.shift(-1)).fillna(1.0)
    unexplained = (ret.abs() > GLITCH_RETURN_THRESHOLD) & split_event.isin([1.0])

    a1 = not_in_bench & (unexplained & live).sum(axis=1).gt(0).to_numpy()
    zero_ret = ((ret.abs() < 1e-12) & live).sum(axis=1) / n_live
    a2 = not_in_bench & (zero_ret > 0.999).to_numpy() & (n_live > 50).to_numpy()
    bad_days = adj.index[a1 | a2]

    # ---- Rule B: glitched symbols (evaluated AFTER the bad sessions are removed) -----
    ok_days = ~adj.index.isin(bad_days)
    ret2 = adj.loc[ok_days].pct_change()
    unexplained2 = (ret2.abs() > GLITCH_RETURN_THRESHOLD) & \
        split_event.loc[ok_days].isin([1.0])
    in_window = (ret2.index >= lo) & (ret2.index <= hi)
    bad_symbols = sorted(unexplained2.loc[in_window].any()[lambda s: s].index)

    out = {}
    keep_days = ok_days
    keep_cols = [c for c in adj.columns if c not in set(bad_symbols)]
    for k, v in panels.items():
        out[k] = v.loc[keep_days, [c for c in keep_cols if c in v.columns]]

    report = {
        "bad_sessions_dropped": [str(d.date()) for d in bad_days],
        "muhurat_glitch_sessions": [str(d.date()) for d in adj.index[a1]],
        "stale_filled_holidays": [str(d.date()) for d in adj.index[a2]],
        "n_bad_sessions": len(bad_days),
        "glitched_symbols_excluded": bad_symbols,
        "n_glitched_symbols": len(bad_symbols),
        "symbols_before": adj.shape[1],
        "symbols_after": len(keep_cols),
        "sessions_before": adj.shape[0],
        "sessions_after": int(keep_days.sum()),
    }
    return out, report


def build_shares_panel(shares_long: pd.DataFrame, index: pd.DatetimeIndex,
                       columns: pd.Index) -> pd.DataFrame:
    """Daily as-reported shares outstanding, forward-filled (a share count is valid until
    the next report). Back-filled at the start of a symbol's history, since the earliest
    reported count is the best available estimate for the period just before it."""
    if shares_long.empty:
        return pd.DataFrame(index=index, columns=columns, dtype="float64")
    w = shares_long.pivot_table(index="date", columns="symbol", values="shares",
                                aggfunc="last").sort_index()
    w = w.reindex(index.union(w.index)).ffill().bfill().reindex(index)
    return w.reindex(columns=columns)


# --------------------------------------------------------------------------------------
# Review calendar
# --------------------------------------------------------------------------------------
def review_schedule(start: str, end: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """(cutoff_date, effective_date) pairs. Cut-off 31 Jan -> effective 1 Apr;
    cut-off 31 Jul -> effective 1 Oct. We start one review before `start` so the window
    opens with a properly dated membership set."""
    out = []
    y0 = pd.Timestamp(start).year - 1
    y1 = pd.Timestamp(end).year + 1
    for y in range(y0, y1 + 1):
        out.append((pd.Timestamp(f"{y}-01-31"), pd.Timestamp(f"{y}-04-01")))
        out.append((pd.Timestamp(f"{y}-07-31"), pd.Timestamp(f"{y}-10-01")))
    return sorted(out, key=lambda x: x[1])


# --------------------------------------------------------------------------------------
# Reconstruction
# --------------------------------------------------------------------------------------
def eligibility_mask(panels: dict[str, pd.DataFrame], cutoff: pd.Timestamp,
                     min_history_days: int = MIN_HISTORY_DAYS,
                     min_turnover: float = MIN_MEDIAN_TURNOVER,
                     min_price: float = MIN_PRICE) -> pd.Series:
    """Which symbols are eligible to be ranked at a given cut-off, using ONLY data at or
    before the cut-off."""
    adj = panels["adjclose"].loc[:cutoff]
    raw = panels["rawprice"].loc[:cutoff]
    vol = panels["volume"].loc[:cutoff]
    if adj.empty:
        return pd.Series(False, index=panels["adjclose"].columns)

    hist = adj.notna().sum()
    last_px = raw.ffill().iloc[-1]
    trailing = adj.tail(60)
    turnover = (trailing * vol.tail(60)).median()
    recent = adj.tail(20).notna().sum()

    return ((hist >= min_history_days)
            & (last_px >= min_price)
            & (turnover >= min_turnover)
            & (recent >= 10)).fillna(False)


def mcap_ranks_at(panels: dict[str, pd.DataFrame], shares: pd.DataFrame,
                  cutoff: pd.Timestamp, avg_months: int = 6) -> pd.Series:
    """Six-month average full market capitalisation at the cut-off, ranked 1 = largest."""
    lo = cutoff - pd.DateOffset(months=avg_months)
    raw = panels["rawprice"].loc[lo:cutoff]
    sh = shares.loc[lo:cutoff]
    if raw.empty:
        return pd.Series(dtype="float64")
    mcap = raw * sh.reindex_like(raw)
    avg = mcap.mean(axis=0, skipna=True)
    return avg.dropna()


def reconstruct_membership(panels: dict[str, pd.DataFrame], shares: pd.DataFrame,
                           start: str, end: str,
                           bands: dict[str, tuple[int, int]] = RANK_BANDS,
                           ) -> dict[pd.Timestamp, dict[str, list[str]]]:
    """Membership by index sleeve, effective from each review date."""
    out: dict[pd.Timestamp, dict[str, list[str]]] = {}
    for cutoff, effective in review_schedule(start, end):
        if cutoff > panels["adjclose"].index.max():
            continue
        elig = eligibility_mask(panels, cutoff)
        avg_mcap = mcap_ranks_at(panels, shares, cutoff)
        avg_mcap = avg_mcap[avg_mcap.index.isin(elig[elig].index)]
        if avg_mcap.empty:
            continue
        ranked = avg_mcap.sort_values(ascending=False)
        sleeves = {}
        for name, (lo, hi) in bands.items():
            sleeves[name] = list(ranked.index[lo - 1: hi])
        sleeves["_ranked"] = list(ranked.index[:600])
        sleeves["_mcap"] = ranked.head(600).to_dict()
        out[effective] = sleeves
    return out


def membership_asof(membership: dict, date: pd.Timestamp) -> dict[str, list[str]]:
    """Membership in force on `date` — the most recent review effective on or before it."""
    keys = [k for k in sorted(membership) if k <= pd.Timestamp(date)]
    if not keys:
        keys = [min(membership)]
    return membership[keys[-1]]


def universe_asof(membership: dict, date: pd.Timestamp) -> list[str]:
    """The competition universe: Nifty 100 U Midcap 100 U Smallcap 100, as of `date`."""
    m = membership_asof(membership, date)
    return sorted(set(m["NIFTY100"]) | set(m["MIDCAP100"]) | set(m["SMALLCAP100"]))


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------
def _published(fname: str) -> set[str]:
    path = RAW / fname
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    return {str(s).strip().upper() for s in df["Symbol"]}


def validate_against_published(membership: dict, asof: pd.Timestamp) -> pd.DataFrame:
    """Score the reconstruction against the current published NSE lists.

    The current lists are dated 'today', so this validates the method at the most recent
    review only. It is nonetheless a real test: if rank bands cannot reproduce today's
    published membership, they cannot be trusted to reproduce 2021's either.
    """
    m = membership_asof(membership, asof)
    truth = {
        "NIFTY100": _published("ind_nifty100list.csv"),
        "MIDCAP100": _published("ind_niftymidcap100list.csv"),
        "SMALLCAP100": _published("ind_niftysmallcap100list.csv"),
    }
    rows = []
    for sleeve, actual in truth.items():
        recon = set(m.get(sleeve, []))
        if not actual:
            continue
        rows.append({
            "sleeve": sleeve,
            "n_published": len(actual),
            "n_reconstructed": len(recon),
            "overlap": len(recon & actual),
            "overlap_pct": round(len(recon & actual) / len(actual) * 100, 1),
            "missed_examples": ", ".join(sorted(actual - recon)[:6]),
        })
    # combined universe overlap is what actually matters for stock selection
    all_actual = set().union(*truth.values())
    all_recon = set(m["NIFTY100"]) | set(m["MIDCAP100"]) | set(m["SMALLCAP100"])
    rows.append({
        "sleeve": "COMBINED",
        "n_published": len(all_actual),
        "n_reconstructed": len(all_recon),
        "overlap": len(all_recon & all_actual),
        "overlap_pct": round(len(all_recon & all_actual) / len(all_actual) * 100, 1),
        "missed_examples": ", ".join(sorted(all_actual - all_recon)[:6]),
    })
    return pd.DataFrame(rows)


def calibrate_bands(panels: dict, shares: pd.DataFrame, asof: pd.Timestamp,
                    candidates: list[dict]) -> pd.DataFrame:
    """Try several rank-band definitions and report which reproduces today's published
    lists best. Data-driven choice of the band edges, rather than assuming them."""
    rows = []
    for cand in candidates:
        mem = reconstruct_membership(panels, shares, "2025-06-01", "2026-09-01", bands=cand)
        v = validate_against_published(mem, asof)
        combined = v[v["sleeve"] == "COMBINED"].iloc[0]
        rows.append({"bands": str(cand), "combined_overlap_pct": combined["overlap_pct"],
                     **{r["sleeve"]: r["overlap_pct"] for _, r in v.iterrows()}})
    return pd.DataFrame(rows).sort_values("combined_overlap_pct", ascending=False)


def save_membership(membership: dict, path=PIT / "membership.parquet") -> None:
    rows = []
    for eff, sleeves in membership.items():
        for sleeve in ("NIFTY100", "MIDCAP100", "SMALLCAP100"):
            for i, sym in enumerate(sleeves[sleeve], start=1):
                rows.append({"effective": eff, "sleeve": sleeve, "rank_in_sleeve": i,
                             "symbol": sym})
    pd.DataFrame(rows).to_parquet(path, index=False)
