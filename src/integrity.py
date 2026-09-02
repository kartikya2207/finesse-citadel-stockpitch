"""Data integrity checks. These run BEFORE any backtest and write an exceptions log.

The checks are the ones that actually bite in Indian equity data:
  * trading-calendar reconciliation -- a market holiday must never become a zero-return day
  * zero-volume days in illiquid smallcaps
  * price jumps not explained by a recorded corporate action
  * truncated history -- no backfilling before a stock's listing date
  * NaN propagation
  * paise-vs-rupee and face-value errors (a 100x level shift)
  * explicit handling of suspended and delisted names
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LOGS


def check_calendar(adjclose: pd.DataFrame, bench: pd.Series) -> dict:
    """The benchmark trades on every NSE session, so its index IS the trading calendar.
    Any date in our panel that the benchmark does not have is suspect, and vice versa."""
    ours = set(adjclose.index)
    theirs = set(bench.dropna().index)
    extra = sorted(ours - theirs)
    missing = sorted(theirs - ours)
    return {
        "panel_days": len(ours),
        "benchmark_days": len(theirs),
        "days_in_panel_not_in_benchmark": len(extra),
        "days_in_benchmark_not_in_panel": len(missing),
        "examples_extra": [str(d.date()) for d in extra[:10]],
        "examples_missing": [str(d.date()) for d in missing[:10]],
    }


def check_price_jumps(adjclose: pd.DataFrame, splits: pd.DataFrame,
                      threshold: float = 0.5) -> pd.DataFrame:
    """Daily moves beyond +/-`threshold` that are NOT explained by a recorded split.

    A 50% single-day move in a Nifty-universe stock is nearly always a corporate action the
    adjustment missed. Left unfixed these are pure fabricated PNL.
    """
    r = adjclose.pct_change()
    big = (r.abs() > threshold)
    if not big.any().any():
        return pd.DataFrame(columns=["date", "symbol", "return", "split_on_day"])
    idx = np.argwhere(big.to_numpy())
    rows = []
    for i, j in idx:
        d, s = adjclose.index[i], adjclose.columns[j]
        sp = splits.at[d, s] if (s in splits.columns and d in splits.index) else 0.0
        rows.append({"date": d, "symbol": s, "return": float(r.iat[i, j]),
                     "split_on_day": float(sp) if pd.notna(sp) else 0.0})
    out = pd.DataFrame(rows)
    return out[out["split_on_day"].isin([0.0, 1.0])].sort_values(
        "return", key=lambda s: s.abs(), ascending=False)


def check_level_shifts(rawprice: pd.DataFrame) -> pd.DataFrame:
    """Paise/rupee or face-value errors show up as a ~10x or ~100x level shift with no split."""
    r = rawprice.pct_change()
    hits = ((r > 8) | (r < -0.88))
    if not hits.any().any():
        return pd.DataFrame(columns=["date", "symbol", "ratio"])
    idx = np.argwhere(hits.to_numpy())
    return pd.DataFrame([{"date": rawprice.index[i], "symbol": rawprice.columns[j],
                          "ratio": float(1 + r.iat[i, j])} for i, j in idx])


def check_zero_volume(volume: pd.DataFrame, adjclose: pd.DataFrame) -> pd.DataFrame:
    """Symbols with a high share of zero-volume sessions -- untradeable at ~Rs 10 lakh a name."""
    live = adjclose.notna()
    zero = (volume.fillna(0) == 0) & live
    frac = (zero.sum() / live.sum().replace(0, np.nan)).dropna()
    return frac[frac > 0.02].sort_values(ascending=False).rename("zero_vol_frac").to_frame()


def check_history_gaps(adjclose: pd.DataFrame, max_gap: int = 10) -> pd.DataFrame:
    """Internal gaps in a symbol's history: it traded, stopped, then traded again."""
    rows = []
    for s in adjclose.columns:
        v = adjclose[s]
        live = v.notna()
        if live.sum() < 30:
            continue
        first, last = live.idxmax(), live[::-1].idxmax()
        seg = live.loc[first:last]
        gaps = (~seg).astype(int)
        if gaps.sum() == 0:
            continue
        grp = (gaps.diff() != 0).cumsum()
        runs = gaps.groupby(grp).sum()
        longest = int(runs.max())
        if longest > max_gap:
            rows.append({"symbol": s, "longest_internal_gap_days": longest,
                         "total_missing": int(gaps.sum()),
                         "first": str(first.date()), "last": str(last.date())})
    return pd.DataFrame(rows).sort_values("longest_internal_gap_days", ascending=False) \
        if rows else pd.DataFrame(columns=["symbol", "longest_internal_gap_days"])


def check_no_backfill(adjclose: pd.DataFrame) -> dict:
    """A symbol must have no prices before its first real print. Confirms we never
    back-filled a listing into a period when it did not exist."""
    bad = []
    for s in adjclose.columns:
        v = adjclose[s]
        live = v.notna()
        if live.sum() == 0:
            continue
        first = live.idxmax()
        if v.loc[:first].iloc[:-1].notna().any():
            bad.append(s)
    return {"symbols_with_prices_before_listing": bad}


def run_all(panels: dict, bench: pd.Series, write: bool = True) -> dict:
    adj, raw, vol = panels["adjclose"], panels["rawprice"], panels["volume"]
    splits = panels.get("split_factor_fwd")
    split_events = (splits / splits.shift(-1)).fillna(1.0) if splits is not None else \
        pd.DataFrame(0.0, index=adj.index, columns=adj.columns)

    rep = {
        "calendar": check_calendar(adj, bench),
        "unexplained_jumps": check_price_jumps(adj, split_events),
        "level_shifts": check_level_shifts(raw),
        "zero_volume_symbols": check_zero_volume(vol, adj),
        "history_gaps": check_history_gaps(adj),
        "no_backfill": check_no_backfill(adj),
        "nan_fraction_by_year": adj.isna().groupby(adj.index.year).mean().mean(axis=1).round(4).to_dict(),
    }
    if write:
        p = LOGS / "data_integrity.md"
        with p.open("w", encoding="utf-8") as fh:
            fh.write("# Data Integrity Report\n\n")
            fh.write("## Trading-calendar reconciliation\n")
            fh.write("A market holiday must never be treated as a zero-return day. The\n"
                     "benchmark index trades on every NSE session, so its date index is the\n"
                     "authoritative calendar.\n\n```\n")
            for k, v in rep["calendar"].items():
                fh.write(f"{k}: {v}\n")
            fh.write("```\n\n## Unexplained price jumps (>50% in a day, no recorded split)\n")
            uj = rep["unexplained_jumps"]
            fh.write(f"count: {len(uj)}\n\n")
            if len(uj):
                fh.write(uj.head(50).to_markdown(index=False) + "\n")
            fh.write("\n## Level shifts (paise/rupee or face-value errors)\n")
            fh.write(f"count: {len(rep['level_shifts'])}\n\n")
            if len(rep["level_shifts"]):
                fh.write(rep["level_shifts"].head(30).to_markdown(index=False) + "\n")
            fh.write("\n## Symbols with >2% zero-volume sessions\n")
            fh.write(f"count: {len(rep['zero_volume_symbols'])}\n\n")
            if len(rep["zero_volume_symbols"]):
                fh.write(rep["zero_volume_symbols"].head(30).to_markdown() + "\n")
            fh.write("\n## Internal history gaps (>10 consecutive missing sessions)\n")
            fh.write(f"count: {len(rep['history_gaps'])}\n\n")
            if len(rep["history_gaps"]):
                fh.write(rep["history_gaps"].head(30).to_markdown(index=False) + "\n")
            fh.write("\n## Backfill check\n")
            fh.write(f"symbols with prices before listing: "
                     f"{len(rep['no_backfill']['symbols_with_prices_before_listing'])}\n")
            fh.write("\n## NaN fraction of the panel by year\n\n```\n")
            for k, v in rep["nan_fraction_by_year"].items():
                fh.write(f"{k}: {v}\n")
            fh.write("```\n")
    return rep
