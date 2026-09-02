"""Strategy specification and target-weight construction.

A Strategy is a pure declarative object. Given the PIT membership map and the feature
panels it produces `{rebalance_date -> target weight Series}`, which the backtest engine
consumes. Nothing here reads a price on or after the rebalance date: `features_asof`
returns the row for the last trading day STRICTLY BEFORE the rebalance.

RULE COMPLIANCE
---------------
* `n_hold <= 10` enforced here and re-asserted in the engine.
* The candidate set at every rebalance is the PIT Nifty 100 U Midcap 100 U Smallcap 100.
* One scoring function and one weighting rule are applied identically to every name --
  the competition's "same core methodology across all 10 stocks" requirement. There are no
  per-name overrides anywhere in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import MAX_POSITIONS
from .pit_universe import universe_asof
from .signals import composite_score, features_asof


# --------------------------------------------------------------------------------------
# Rebalance calendars
# --------------------------------------------------------------------------------------
def rebalance_dates(trading_days: pd.DatetimeIndex, start, end,
                    cadence: str) -> list[pd.Timestamp]:
    """First trading day of each period. `cadence` in
    {buyhold, annual, semiannual, quarterly, monthly, 2monthly}."""
    d = trading_days[(trading_days >= pd.Timestamp(start)) & (trading_days <= pd.Timestamp(end))]
    if len(d) == 0:
        return []
    if cadence == "buyhold":
        return [d[0]]
    shift = 0
    if "@" in cadence:                      # e.g. "semiannual@1" = phase-shifted by 1 month
        cadence, sh = cadence.split("@")
        shift = int(sh)
    freq = {"annual": "YS", "semiannual": "2QS", "quarterly": "QS",
            "2monthly": "2MS", "monthly": "MS"}[cadence]
    marks = pd.date_range(d[0], d[-1], freq=freq)
    if shift:
        marks = marks + pd.DateOffset(months=shift)
    out = []
    for m in marks:
        nxt = d[d >= m]
        if len(nxt):
            out.append(nxt[0])
    if d[0] not in out:
        out = [d[0]] + out
    return sorted(set(out))


# --------------------------------------------------------------------------------------
# Weighting
# --------------------------------------------------------------------------------------
def apply_cap_floor(w: pd.Series, cap: float | None, floor: float | None,
                    iters: int = 100) -> pd.Series:
    """Enforce a per-name cap and floor while summing to exactly 1.

    Uses a waterfall, not repeated clip-and-renormalise. Clipping and renormalising
    oscillates: renormalising after a clip pushes the clipped names back over the cap, so
    the result silently breaches the constraint by a small amount every time. The waterfall
    freezes each breaching name at its bound, then re-solves for the remainder among the
    names still free. It terminates exactly.
    """
    w = w.astype(float).clip(lower=0)
    if len(w) == 0 or w.sum() <= 0:
        return w
    w = w / w.sum()
    n = len(w)
    # A cap is infeasible when cap*n < 1 (the book cannot reach 100% without breaching it);
    # a floor is infeasible when floor*n > 1. In either case the closest feasible portfolio
    # is equal weight -- NOT the un-capped weights, which would silently concentrate exactly
    # where the cap was meant to prevent it.
    if (cap is not None and cap * n < 1 - 1e-12) or \
       (floor is not None and floor * n > 1 + 1e-12):
        return pd.Series(1.0 / n, index=w.index)

    fixed: dict = {}
    free = list(w.index)
    for _ in range(iters):
        remaining = 1.0 - sum(fixed.values())
        if not free or remaining <= 0:
            break
        sub = w[free]
        sub = sub / sub.sum() * remaining if sub.sum() > 0 else \
            pd.Series(remaining / len(free), index=free)
        if cap is not None:
            over = sub.index[sub > cap + 1e-15]
            if len(over):
                for s in over:
                    fixed[s] = cap
                free = [s for s in free if s not in set(over)]
                continue
        if floor is not None:
            under = sub.index[sub < floor - 1e-15]
            if len(under):
                for s in under:
                    fixed[s] = floor
                free = [s for s in free if s not in set(under)]
                continue
        for s in free:
            fixed[s] = float(sub[s])
        free = []
        break
    out = pd.Series({s: fixed.get(s, 0.0) for s in w.index})
    total = out.sum()
    return out / total if total > 0 else out


def make_weights(scheme: str, picks: list[str], feat: pd.DataFrame,
                 score: pd.Series, cap: float | None = None,
                 floor: float | None = None,
                 cov: pd.DataFrame | None = None) -> pd.Series:
    if scheme == "equal":
        w = pd.Series(1.0, index=picks)
    elif scheme == "invvol":
        v = feat.loc[picks, "vol_1y"].replace(0, np.nan)
        w = 1.0 / v
    elif scheme == "invvol_sqrt":
        v = feat.loc[picks, "vol_1y"].replace(0, np.nan)
        w = 1.0 / np.sqrt(v)
    elif scheme == "invdd":
        v = feat.loc[picks, "max_dd_1y"].abs().replace(0, np.nan)
        w = 1.0 / v
    elif scheme == "score":
        s = score.loc[picks]
        w = (s - s.min() + 1e-6) if s.min() < 0 else s
    elif scheme == "score_rank":
        w = pd.Series(np.arange(len(picks), 0, -1), index=picks, dtype=float)
    elif scheme == "mcap":
        w = feat.loc[picks, "mcap"]
    elif scheme == "invbeta":
        b = feat.loc[picks, "beta"].clip(lower=0.2)
        w = 1.0 / b
    elif scheme == "minvar" and cov is not None:
        c = cov.loc[picks, picks].to_numpy()
        c = c + np.eye(len(picks)) * 1e-8
        try:
            inv = np.linalg.pinv(c)
            raw = inv @ np.ones(len(picks))
            w = pd.Series(np.clip(raw, 0, None), index=picks)
            if w.sum() <= 0:
                w = pd.Series(1.0, index=picks)
        except np.linalg.LinAlgError:
            w = pd.Series(1.0, index=picks)
    else:
        w = pd.Series(1.0, index=picks)
    w = w.replace([np.inf, -np.inf], np.nan).fillna(w.median() if w.notna().any() else 1.0)
    return apply_cap_floor(w, cap, floor)


# --------------------------------------------------------------------------------------
# Strategy spec
# --------------------------------------------------------------------------------------
@dataclass
class Strategy:
    name: str
    score_spec: dict[str, float]              # feature -> weight (higher score = better)
    n_hold: int = MAX_POSITIONS
    cadence: str = "quarterly"
    weighting: str = "invvol"
    cap: float | None = 0.20
    floor: float | None = 0.05
    score_method: str = "rank"                # "rank" or "z"
    screens: dict = field(default_factory=dict)
    sleeves: tuple[str, ...] = ("NIFTY100", "MIDCAP100", "SMALLCAP100")
    max_per_sector: int | None = None
    trend_filter: str | None = None           # e.g. "above_ma200"
    invested_frac: float = 1.0
    family: str = "quant"
    notes: str = ""

    def __post_init__(self):
        if self.n_hold > MAX_POSITIONS:
            raise ValueError(f"{self.name}: n_hold={self.n_hold} exceeds the 10-stock cap")


def _apply_screens(feat: pd.DataFrame, screens: dict, cand: list[str]) -> list[str]:
    """Screens are expressed as quantile or absolute bounds on a feature, evaluated
    cross-sectionally within the candidate set at this date only."""
    keep = pd.Index(cand)
    for feature, rule in screens.items():
        if feature not in feat.columns:
            continue
        s = feat.loc[keep, feature].astype(float)
        kind, val = rule
        if kind == "max_pctile":
            thr = s.quantile(val)
            keep = s.index[(s <= thr) | s.isna()]
        elif kind == "min_pctile":
            thr = s.quantile(val)
            keep = s.index[(s >= thr) | s.isna()]
        elif kind == "min":
            keep = s.index[(s >= val) | s.isna()]
        elif kind == "max":
            keep = s.index[(s <= val) | s.isna()]
        elif kind == "drop_top_pctile":
            thr = s.quantile(1 - val)
            keep = s.index[(s < thr) | s.isna()]
        else:
            raise ValueError(kind)
        feat = feat.loc[keep]
    return list(keep)


def build_target_weights(strategy: Strategy, features: dict[str, pd.DataFrame],
                         membership: dict, dates: list[pd.Timestamp],
                         sectors: dict[str, str] | None = None,
                         cov_lookback: int = 252,
                         adjclose: pd.DataFrame | None = None,
                         log_selection: bool = False,
                         ) -> tuple[dict, list[dict]]:
    """Produce `{date -> weight Series}` plus a per-rebalance selection log."""
    out: dict[pd.Timestamp, pd.Series] = {}
    log: list[dict] = []

    for d in dates:
        m = membership
        cand = set()
        for sleeve in strategy.sleeves:
            cand |= set(universe_asof(m, d)) if sleeve == "ALL" else set(
                __import__("src.pit_universe", fromlist=["membership_asof"])
                .membership_asof(m, d).get(sleeve, []))
        cand = sorted(cand)
        if not cand:
            continue

        feat = features_asof(features, d)
        if feat.empty:
            continue
        cand = [c for c in cand if c in feat.index]
        feat = feat.loc[cand]

        # must have a computable score
        need = [k for k in strategy.score_spec if k in feat.columns]
        if not need:
            continue
        feat = feat[feat[need].notna().any(axis=1)]
        cand = list(feat.index)

        cand = _apply_screens(feat, strategy.screens, cand)
        if strategy.trend_filter and strategy.trend_filter in feat.columns:
            tf = feat.loc[cand, strategy.trend_filter]
            cand = list(tf.index[tf > 0])
        if not cand:
            continue
        feat = feat.loc[cand]

        score = composite_score(feat, strategy.score_spec, method=strategy.score_method)
        score = score.dropna().sort_values(ascending=False)
        if score.empty:
            continue

        # sector cap, applied greedily down the ranking (same rule for every name)
        if strategy.max_per_sector and sectors:
            picks, counts = [], {}
            for s in score.index:
                sec = sectors.get(s, "UNKNOWN")
                if counts.get(sec, 0) >= strategy.max_per_sector:
                    continue
                picks.append(s)
                counts[sec] = counts.get(sec, 0) + 1
                if len(picks) == strategy.n_hold:
                    break
        else:
            picks = list(score.index[:strategy.n_hold])
        if not picks:
            continue

        cov = None
        if strategy.weighting == "minvar" and adjclose is not None:
            hist = adjclose.loc[:d, picks].iloc[-cov_lookback - 1:-1]
            cov = hist.pct_change().dropna(how="all").cov()

        w = make_weights(strategy.weighting, picks, feat, score,
                         cap=strategy.cap, floor=strategy.floor, cov=cov)
        w = w * strategy.invested_frac
        out[d] = w

        if log_selection:
            log.append({"date": d, "n_candidates": len(cand),
                        "picks": list(picks),
                        "weights": {k: round(float(v), 6) for k, v in w.items()},
                        "scores": {k: round(float(score[k]), 6) for k in picks}})
    return out, log


# --------------------------------------------------------------------------------------
# Benchmark helpers
# --------------------------------------------------------------------------------------
def equal_weight_universe_weights(membership: dict, dates: list[pd.Timestamp],
                                  features: dict, n: int = 10,
                                  seed: int = 0) -> dict:
    """Random-10 control. Establishes what a monkey scores in this universe, which is the
    honest reference point for judging whether a signal added anything."""
    rng = np.random.default_rng(seed)
    out = {}
    for d in dates:
        cand = universe_asof(membership, d)
        feat = features_asof(features, d)
        cand = [c for c in cand if c in feat.index and pd.notna(feat.loc[c, "vol_1y"])]
        if len(cand) < n:
            continue
        picks = list(rng.choice(cand, size=n, replace=False))
        out[d] = pd.Series(1.0 / n, index=picks)
    return out
