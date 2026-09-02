"""Signal evidence: information coefficients, decile spreads, sub-period stability.

A 10-stock backtest is a very noisy estimator of whether a signal works -- with 10 names out
of ~250, a single 5-bagger swamps the result. These tools test the signal on the whole
cross-section instead, which is far stronger evidence and far harder to fool.

If a signal has a positive, stable information coefficient and a monotone decile spread
across sub-periods, the 10-stock portfolio built from it is standing on something. If it
does not, the portfolio result was luck no matter how large it is.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .pit_universe import universe_asof
from .signals import features_asof


def forward_returns(adjclose: pd.DataFrame, dates: list[pd.Timestamp],
                    horizon_dates: list[pd.Timestamp] | None = None) -> dict:
    """Total return of every name from each rebalance date to the next."""
    out = {}
    ds = list(dates)
    for i, d in enumerate(ds[:-1]):
        nxt = ds[i + 1]
        try:
            p0 = adjclose.loc[d]
            p1 = adjclose.loc[nxt]
        except KeyError:
            continue
        out[d] = (p1 / p0 - 1.0)
    return out


def information_coefficient(features: dict, adjclose: pd.DataFrame, membership: dict,
                            dates: list[pd.Timestamp], feature: str,
                            method: str = "spearman") -> pd.DataFrame:
    """Rank correlation between the signal at each rebalance and the return that followed.

    Spearman by default: we care about ordering, not magnitude, and a smallcap universe has
    return outliers that would dominate a Pearson correlation.
    """
    fwd = forward_returns(adjclose, dates)
    rows = []
    for d, r in fwd.items():
        feat = features_asof(features, d, names=[feature])
        if feat.empty or feature not in feat.columns:
            continue
        cand = [c for c in universe_asof(membership, d) if c in feat.index]
        s = feat.loc[cand, feature].astype(float)
        y = r.reindex(s.index)
        ok = s.notna() & y.notna()
        if ok.sum() < 20:
            continue
        if method == "spearman":
            ic, p = stats.spearmanr(s[ok], y[ok])
        else:
            ic, p = stats.pearsonr(s[ok], y[ok])
        rows.append({"date": d, "ic": ic, "p_value": p, "n": int(ok.sum())})
    return pd.DataFrame(rows)


def ic_summary(ic_df: pd.DataFrame) -> dict:
    if ic_df.empty:
        return {"n_periods": 0}
    ic = ic_df["ic"]
    t = ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic))) if len(ic) > 1 else np.nan
    return {
        "n_periods": len(ic),
        "mean_ic": float(ic.mean()),
        "median_ic": float(ic.median()),
        "std_ic": float(ic.std(ddof=1)),
        "ic_ir": float(ic.mean() / ic.std(ddof=1)) if ic.std(ddof=1) > 0 else np.nan,
        "t_stat": float(t),
        "hit_rate_pct": float((ic > 0).mean() * 100),
    }


def decile_spread(features: dict, adjclose: pd.DataFrame, membership: dict,
                  dates: list[pd.Timestamp], feature: str,
                  n_buckets: int = 5) -> pd.DataFrame:
    """Equal-weighted return of each signal quantile between consecutive rebalances.

    Monotonicity across buckets is the property that matters. A signal where only the top
    bucket works, with no gradient below it, is usually one lucky name.
    """
    fwd = forward_returns(adjclose, dates)
    rows = []
    for d, r in fwd.items():
        feat = features_asof(features, d, names=[feature])
        if feat.empty or feature not in feat.columns:
            continue
        cand = [c for c in universe_asof(membership, d) if c in feat.index]
        s = feat.loc[cand, feature].astype(float).dropna()
        y = r.reindex(s.index).dropna()
        s = s.reindex(y.index)
        if len(s) < n_buckets * 8:
            continue
        try:
            q = pd.qcut(s.rank(method="first"), n_buckets, labels=False)
        except ValueError:
            continue
        row = {"date": d, "n": len(s)}
        for b in range(n_buckets):
            row[f"Q{b + 1}"] = float(y[q == b].mean())
        row["spread_top_minus_bottom"] = row[f"Q{n_buckets}"] - row["Q1"]
        rows.append(row)
    return pd.DataFrame(rows)


def decile_summary(dec: pd.DataFrame, n_buckets: int = 5,
                   periods_per_year: float = 4.0) -> dict:
    if dec.empty:
        return {}
    out = {}
    for b in range(1, n_buckets + 1):
        col = f"Q{b}"
        r = dec[col]
        out[f"{col}_ann_pct"] = float(((1 + r).prod() ** (periods_per_year / len(r)) - 1) * 100)
    sp = dec["spread_top_minus_bottom"]
    out["spread_mean_per_period_pct"] = float(sp.mean() * 100)
    out["spread_hit_rate_pct"] = float((sp > 0).mean() * 100)
    out["spread_t_stat"] = float(sp.mean() / (sp.std(ddof=1) / np.sqrt(len(sp)))) if len(sp) > 1 else np.nan
    highs = [out[f"Q{b}_ann_pct"] for b in range(1, n_buckets + 1)]
    out["monotone"] = bool(all(highs[i] <= highs[i + 1] + 1e-9 for i in range(len(highs) - 1)))
    out["rank_corr_bucket_vs_return"] = float(
        stats.spearmanr(range(n_buckets), highs).statistic)
    return out


# --------------------------------------------------------------------------------------
# Sub-period stability
# --------------------------------------------------------------------------------------
def subperiod_table(nav: pd.Series, freq: str = "YE") -> pd.DataFrame:
    """Return, vol and max drawdown within each calendar year."""
    rows = []
    for period, chunk in nav.groupby(nav.index.to_period("Y" if freq == "YE" else "Q")):
        if len(chunk) < 5:
            continue
        r = chunk.pct_change().dropna()
        rows.append({
            "period": str(period),
            "return_pct": float(chunk.iloc[-1] / chunk.iloc[0] - 1) * 100,
            "vol_pct": float(r.std(ddof=1) * np.sqrt(252) * 100),
            "max_dd_pct": float((chunk / chunk.cummax() - 1).min() * 100),
            "n_days": len(chunk),
        })
    return pd.DataFrame(rows)


def stability_score(nav: pd.Series, bench: pd.Series) -> dict:
    """How often, and how consistently, does the strategy beat its benchmark?"""
    b = bench.reindex(nav.index).ffill().bfill()
    py = nav.groupby(nav.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    by = b.groupby(b.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    excess = (py - by).dropna()
    pq = nav.groupby(nav.index.to_period("Q")).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    bq = b.groupby(b.index.to_period("Q")).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    eq = (pq - bq).dropna()
    return {
        "years_beaten": int((excess > 0).sum()),
        "years_total": int(len(excess)),
        "worst_year_excess_pct": float(excess.min() * 100),
        "quarters_beaten_pct": float((eq > 0).mean() * 100),
        "n_quarters": int(len(eq)),
        "excess_by_year": {int(k): round(float(v) * 100, 2) for k, v in excess.items()},
    }


# --------------------------------------------------------------------------------------
# Turnover / concentration diagnostics
# --------------------------------------------------------------------------------------
def concentration(round_trips: pd.DataFrame) -> dict:
    """How much of the PNL came from how few trades? High concentration means the headline
    number rests on a handful of names and will not repeat."""
    if round_trips is None or round_trips.empty:
        return {}
    p = round_trips["pnl"].sort_values(ascending=False)
    total = p.sum()
    if total == 0:
        return {}
    return {
        "n_trades": len(p),
        "top1_pct_of_pnl": float(p.iloc[:1].sum() / total * 100),
        "top5_pct_of_pnl": float(p.iloc[:5].sum() / total * 100),
        "top10_pct_of_pnl": float(p.iloc[:10].sum() / total * 100),
        "pnl_gini": float(_gini(p.to_numpy())),
    }


def _gini(x: np.ndarray) -> float:
    x = np.sort(x - x.min() + 1e-12)
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))
