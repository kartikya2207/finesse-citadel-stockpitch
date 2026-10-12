"""Contamination guard for the post-unseal search (session 2026-09-02).

The Jan-Jun 2026 stress window has already been unsealed, so any strategy chosen from
now on is being chosen by a process that has seen the out-of-sample outcome. An assertion
that merely *detects* a post-2025 read is not enough, because a search can leak 2026
information in subtle ways (a feature's rolling window, a screen percentile computed over
the full sample, a volatility estimate).

The control used here is PHYSICAL TRUNCATION, not detection: every price panel and every
derived feature is clipped to <= SEARCH_END before a single candidate is scored. 2026 data
is not merely forbidden to the search, it is absent from the objects the search can see.

NEW CODE PATH ONLY. Nothing in this module mutates the frozen strategy, the engine, the
metrics or the existing tests. It builds a second, truncated World and installs it into the
pipeline singleton for the duration of the search process.
"""
from __future__ import annotations

import pandas as pd

from . import pipeline as P
from .config import CAPITAL

SEARCH_END = pd.Timestamp("2025-12-31")


class ContaminationError(RuntimeError):
    """Raised when an object visible to the search carries a post-2025 observation."""


def _clip(obj):
    """Clip any date-indexed pandas object to SEARCH_END. Non-dated objects pass through."""
    if isinstance(obj, (pd.DataFrame, pd.Series)) and isinstance(obj.index, pd.DatetimeIndex):
        return obj.loc[obj.index <= SEARCH_END]
    return obj


def assert_no_2026(world, context: str = "") -> None:
    """Hard check: nothing the search can read may carry a post-2025 date."""
    bad = []
    for name, df in world.panels.items():
        if isinstance(df.index, pd.DatetimeIndex) and len(df) and df.index.max() > SEARCH_END:
            bad.append(f"panel[{name}] max={df.index.max().date()}")
    for name, df in world.features.items():
        if isinstance(df.index, pd.DatetimeIndex) and len(df) and df.index.max() > SEARCH_END:
            bad.append(f"feature[{name}] max={df.index.max().date()}")
    if len(world.trading_days) and world.trading_days.max() > SEARCH_END:
        bad.append(f"trading_days max={world.trading_days.max().date()}")
    if bad:
        raise ContaminationError(
            f"post-2025 data reachable by the search ({context}): " + "; ".join(bad[:6]))


def build_search_world(verbose: bool = True):
    """Return the pipeline World with every dated object truncated to 2025-12-31.

    Installs the truncated world into the pipeline singleton so that every downstream
    caller (experiments.evaluate, run_strategy, build_target_weights) sees only in-sample
    data. Idempotent.
    """
    w = P.load_world()
    if getattr(w, "_search_truncated", False):
        assert_no_2026(w, "already truncated")
        return w

    before = (len(w.trading_days), w.trading_days.max().date())
    w.panels = {k: _clip(v) for k, v in w.panels.items()}
    w.features = {k: _clip(v) for k, v in w.features.items()}
    w.shares = _clip(w.shares)
    w.trading_days = w.panels["adjclose"].index
    # membership is a {date -> sleeves} dict; drop any review effective after the cutoff
    w.membership = {k: v for k, v in w.membership.items() if pd.Timestamp(k) <= SEARCH_END}
    w._search_truncated = True

    assert_no_2026(w, "build_search_world")
    if verbose:
        print(f"[search_guard] trading days {before[0]} (to {before[1]}) -> "
              f"{len(w.trading_days)} (to {w.trading_days.max().date()})")
        print(f"[search_guard] membership reviews kept: {len(w.membership)}")
        print("[search_guard] 2026 data is ABSENT from every object the search can read.")
    return w


def validate_guard_is_a_noop(verbose: bool = True) -> dict:
    """Prove truncation does not change any in-sample result.

    Every feature is a backward-looking rolling window, so clipping the tail must leave
    values at dates <= 2025-12-31 untouched. If the incumbent's PNL moves under truncation,
    that is a look-ahead bug in the incumbent and it outranks anything else in this session.
    """
    import json
    from .strategies import Strategy

    p = json.load(open("FROZEN.json", encoding="utf-8"))["parameters"]
    S = Strategy(name="INCUMBENT_guardcheck", score_spec=p["score_spec"], family="incumbent",
                 cadence=p["cadence"], weighting=p["weighting"], n_hold=p["n_hold"],
                 cap=p["cap"], floor=p["floor"],
                 screens={k: tuple(v) for k, v in p["screens"].items()},
                 sleeves=tuple(p["sleeves"]), score_method=p["score_method"])
    rep = P.run_strategy(S, start="2021-01-01", end="2025-12-31", allow_oos=True)["report"]
    expected = {"total_net_pnl": 27392323.214909784, "n_trades": 130, "n_legs": 320}
    ok = (abs(rep["total_net_pnl"] - expected["total_net_pnl"]) < 1.0
          and rep["n_trades"] == expected["n_trades"]
          and rep["n_legs"] == expected["n_legs"])
    if verbose:
        print(f"[search_guard] incumbent on truncated world: PNL={rep['total_net_pnl']:,.2f} "
              f"trades={rep['n_trades']} legs={rep['n_legs']}")
        print(f"[search_guard] expected                    : PNL={expected['total_net_pnl']:,.2f} "
              f"trades={expected['n_trades']} legs={expected['n_legs']}")
        print(f"[search_guard] TRUNCATION IS A NO-OP IN SAMPLE: {ok}")
    if not ok:
        raise ContaminationError(
            "Truncating to 2025-12-31 CHANGED the incumbent's in-sample result. That means a "
            "feature or screen was reading future data. Stop the search and fix this first.")
    return rep
