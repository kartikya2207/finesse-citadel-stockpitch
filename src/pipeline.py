"""Pipeline: load cached data -> panels -> PIT membership -> features -> run a Strategy.

Everything is cached in a module-level singleton so the sweep can evaluate hundreds of
variants without rebuilding panels each time.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import metrics as M
from . import pit_universe as U
from . import signals as S
from .backtest import run_backtest
from .config import (BACKTEST_END, BACKTEST_START, CACHE, CAPITAL, COST_PER_SIDE,
                     PRIMARY_BENCHMARK, RAW, TRI_DIVIDEND_YIELD)
from .seal import assert_sealed
from .strategies import Strategy, build_target_weights, rebalance_dates

SNAPSHOT = "v2"   # expanded, bhavcopy-augmented master list (see ASSUMPTIONS B8)


@dataclass
class World:
    panels: dict
    shares: pd.DataFrame
    features: dict
    membership: dict
    bench: pd.DataFrame
    sectors: dict
    trading_days: pd.DatetimeIndex
    snapshot_hash: str
    clean_report: dict


_WORLD: World | None = None


def load_world(force: bool = False) -> World:
    global _WORLD
    if _WORLD is not None and not force:
        return _WORLD

    px = pd.read_parquet(CACHE / f"prices_{SNAPSHOT}.parquet")
    sh = pd.read_parquet(CACHE / f"shares_{SNAPSHOT}.parquet")
    bench = pd.read_parquet(CACHE / "bench_2026-09-02.parquet").set_index("date").sort_index()

    panels = U.build_panels(px)
    panels, clean_report = U.clean_panels(panels, bench.index)
    shares = U.build_shares_panel(sh, panels["adjclose"].index, panels["adjclose"].columns)
    membership = U.reconstruct_membership(panels, shares, "2020-01-01", "2026-09-01")

    bench_px = bench[PRIMARY_BENCHMARK].reindex(panels["adjclose"].index).ffill()
    features = S.build_features(panels["adjclose"], panels["volume"],
                                panels["rawprice"], shares, bench=bench_px)

    sectors = {}
    for f in ["ind_niftytotalmarket_list.csv", "ind_nifty500list.csv"]:
        p = RAW / f
        if p.exists():
            d = pd.read_csv(p)
            for _, r in d.iterrows():
                sectors.setdefault(str(r["Symbol"]).strip().upper(),
                                   str(r.get("Industry", "UNKNOWN")))

    h = hashlib.sha256()
    for p in sorted(CACHE.glob("*.parquet")):
        h.update(p.name.encode())
        h.update(str(p.stat().st_size).encode())

    _WORLD = World(panels=panels, shares=shares, features=features, membership=membership,
                   bench=bench, sectors=sectors,
                   trading_days=panels["adjclose"].index, snapshot_hash=h.hexdigest()[:16],
                   clean_report=clean_report)
    return _WORLD


# --------------------------------------------------------------------------------------
# Benchmark NAV
# --------------------------------------------------------------------------------------
def benchmark_nav(name: str, start, end, capital: float = CAPITAL,
                  tri: bool = True) -> pd.Series:
    """Benchmark NAV rebased to the corpus.

    The downloadable index is a PRICE index; our portfolio NAV is total return. To compare
    like with like we add a constant dividend accrual (TRI_DIVIDEND_YIELD / 252 per day).
    Sensitivity to that assumption is reported in the workbook.
    """
    w = load_world()
    s = w.bench[name].dropna()
    s = s.loc[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
    r = s.pct_change().fillna(0.0)
    if tri:
        r = r + TRI_DIVIDEND_YIELD / 252.0
    return capital * (1 + r).cumprod()


# --------------------------------------------------------------------------------------
# Run one strategy
# --------------------------------------------------------------------------------------
def run_strategy(strategy: Strategy, start: str = BACKTEST_START, end: str = BACKTEST_END,
                 cost_per_side: float = COST_PER_SIDE, capital: float = CAPITAL,
                 integer_shares: bool = False, log_selection: bool = False,
                 allow_oos: bool = False) -> dict:
    w = load_world()
    dates = rebalance_dates(w.trading_days, start, end, strategy.cadence)
    if not allow_oos:
        assert_sealed(pd.DatetimeIndex(dates + [pd.Timestamp(end)]),
                      context=f"run_strategy({strategy.name})")

    tw, log = build_target_weights(strategy, w.features, w.membership, dates,
                                   sectors=w.sectors, adjclose=w.panels["adjclose"],
                                   log_selection=log_selection)
    if not tw:
        return {"strategy": strategy, "error": "no target weights produced"}

    res = run_backtest(w.panels["adjclose"], tw, start=start, end=end,
                       capital=capital, cost_per_side=cost_per_side,
                       rawclose=w.panels["rawprice"], integer_shares=integer_shares,
                       max_positions=strategy.n_hold)
    rep = M.full_report(res.nav, res.round_trips, res.trades, capital=capital,
                        label=strategy.name)
    rep["family"] = strategy.family
    rep["cadence"] = strategy.cadence
    rep["weighting"] = strategy.weighting
    rep["n_hold"] = strategy.n_hold
    rep["n_rebalances"] = len(tw)
    rep["cost_per_side"] = cost_per_side
    return {"strategy": strategy, "result": res, "report": rep, "weights": tw,
            "selection_log": log}


def compare_to_benchmark(nav: pd.Series, bench_name: str = PRIMARY_BENCHMARK,
                         capital: float = CAPITAL) -> dict:
    b = benchmark_nav(bench_name, nav.index[0], nav.index[-1], capital=capital)
    b = b.reindex(nav.index).ffill().bfill()
    b = b / b.iloc[0] * capital
    rep = M.full_report(b, capital=capital, label=bench_name)
    excess = nav.iloc[-1] - b.iloc[-1]
    pr = nav.pct_change().dropna()
    br = b.pct_change().reindex(pr.index).fillna(0.0)
    cov = np.cov(pr, br)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    alpha_ann = (pr.mean() - beta * br.mean()) * 252
    te = (pr - br).std(ddof=1) * np.sqrt(252)
    return {"bench_report": rep, "bench_nav": b, "excess_final_value": float(excess),
            "beta": float(beta), "alpha_ann_pct": float(alpha_ann * 100),
            "tracking_error_pct": float(te * 100),
            "information_ratio": float((pr.mean() - br.mean()) * 252 / te) if te > 0 else np.nan}
