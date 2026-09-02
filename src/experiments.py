"""Systematic strategy exploration.

Every variant evaluated anywhere in this module is appended to the trials register, and the
register's length is the `n_trials` fed to the deflated-Sharpe and PBO corrections. There is
no separate "exploratory" count that quietly does not count.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from . import pipeline as P
from .config import BACKTEST_END, BACKTEST_START, OUT
from .strategies import Strategy

TRIALS_PATH = OUT / "trials.jsonl"


# --------------------------------------------------------------------------------------
# Trials register
# --------------------------------------------------------------------------------------
def log_trial(strategy: Strategy, report: dict, tag: str = "") -> None:
    row = {"ts": time.time(), "tag": tag, "name": strategy.name,
           "family": strategy.family,
           "params": {k: (list(v) if isinstance(v, tuple) else v)
                      for k, v in asdict(strategy).items()},
           "result": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                      for k, v in report.items()
                      if k not in ("label",)}}
    with TRIALS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def load_trials() -> pd.DataFrame:
    if not TRIALS_PATH.exists():
        return pd.DataFrame()
    rows = [json.loads(l) for l in TRIALS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    flat = []
    for r in rows:
        d = {"name": r["name"], "family": r["family"], "tag": r["tag"]}
        d.update({f"p_{k}": v for k, v in r["params"].items()})
        d.update(r["result"])
        flat.append(d)
    return pd.DataFrame(flat)


def n_trials() -> int:
    if not TRIALS_PATH.exists():
        return 0
    return sum(1 for l in TRIALS_PATH.read_text(encoding="utf-8").splitlines() if l.strip())


# --------------------------------------------------------------------------------------
# Evaluate
# --------------------------------------------------------------------------------------
_NAV_CACHE: dict[str, pd.Series] = {}


def evaluate(strategy: Strategy, tag: str = "", start: str = BACKTEST_START,
             end: str = BACKTEST_END, keep_nav: bool = True,
             quiet: bool = True, **kw) -> dict | None:
    try:
        out = P.run_strategy(strategy, start=start, end=end, **kw)
    except Exception as exc:                                   # noqa: BLE001
        if not quiet:
            print(f"  [fail] {strategy.name}: {type(exc).__name__} {exc}")
        return None
    if "report" not in out:
        return None
    rep = out["report"]
    log_trial(strategy, rep, tag=tag)
    if keep_nav:
        _NAV_CACHE[strategy.name] = out["result"].nav
    return out


def nav_cache() -> dict[str, pd.Series]:
    return _NAV_CACHE


# --------------------------------------------------------------------------------------
# Strategy zoo
# --------------------------------------------------------------------------------------
VOL_SCREEN = {"vol_1y": ("drop_top_pctile", 0.20)}


def momentum_family() -> list[Strategy]:
    """Cross-sectional momentum at many lookbacks, raw and risk-adjusted."""
    out = []
    for feat in ["mom_3m", "mom_6m", "mom_9m", "mom_12m", "mom_18m", "mom_24m",
                 "mom_3m_skip1", "mom_6m_skip1", "mom_12m_skip1", "mom_avg_6_12_skip1"]:
        out.append(Strategy(name=f"MOM_{feat}", score_spec={feat: 1.0}, family="momentum",
                            notes=f"raw cross-sectional {feat}"))
        rar = f"rar_{feat}"
        out.append(Strategy(name=f"RAR_{feat}", score_spec={rar: 1.0}, family="momentum",
                            notes=f"{feat} divided by trailing 1y daily vol"))
    for feat in ["resid_mom_12m", "resid_mom_6m", "rar_resid_mom_12m"]:
        out.append(Strategy(name=f"RESID_{feat}", score_spec={feat: 1.0}, family="momentum",
                            notes="momentum of returns orthogonalised to the Nifty 500"))
    return [s for s in out if s.score_spec]


def lowrisk_family() -> list[Strategy]:
    return [
        Strategy(name="LOWVOL", score_spec={"lowvol": 1.0}, family="lowrisk"),
        Strategy(name="LOWBETA", score_spec={"lowbeta": 1.0}, family="lowrisk"),
        Strategy(name="LOWIDIO", score_spec={"idio_vol": -1.0}, family="lowrisk"),
        Strategy(name="SHALLOW_DD", score_spec={"max_dd_1y": 1.0}, family="lowrisk"),
    ]


def trend_family() -> list[Strategy]:
    return [
        Strategy(name="TREND_MA200", score_spec={"px_over_ma200": 1.0}, family="trend"),
        Strategy(name="TREND_MA50", score_spec={"px_over_ma50": 1.0}, family="trend"),
        Strategy(name="GOLDEN_CROSS", score_spec={"ma50_over_ma200": 1.0}, family="trend"),
        Strategy(name="PROX_52W_HIGH", score_spec={"prox_52w_high": 1.0}, family="trend"),
        Strategy(name="EFFICIENCY", score_spec={"efficiency_6m": 1.0}, family="trend"),
        Strategy(name="CONSISTENCY", score_spec={"pct_up_months_12m": 1.0}, family="trend"),
    ]


def other_factor_family() -> list[Strategy]:
    return [
        Strategy(name="SIZE_SMALL", score_spec={"size": 1.0}, family="factor"),
        Strategy(name="SIZE_LARGE", score_spec={"log_mcap": 1.0}, family="factor"),
        Strategy(name="REVERSAL_1M", score_spec={"reversal_1m": 1.0}, family="factor"),
        Strategy(name="LIQUIDITY", score_spec={"log_turnover": 1.0}, family="factor"),
        Strategy(name="ILLIQ_AMIHUD", score_spec={"amihud": 1.0}, family="factor"),
    ]


def composite_family() -> list[Strategy]:
    """Multi-factor blends. Weights are round numbers on purpose -- a tuned decimal weight
    on a 5-year sample is noise dressed as precision."""
    specs = {
        "COMP_mom_lowvol":       {"mom_12m_skip1": 1.0, "lowvol": 1.0},
        "COMP_mom_trend":        {"mom_12m_skip1": 1.0, "px_over_ma200": 1.0},
        "COMP_mom_quality_px":   {"mom_12m_skip1": 1.0, "efficiency_6m": 1.0},
        "COMP_rar_trend":        {"rar_mom_12m_skip1": 1.0, "px_over_ma200": 1.0},
        "COMP_rar_consistency":  {"rar_mom_12m_skip1": 1.0, "pct_up_months_12m": 1.0},
        "COMP_multi3":           {"mom_12m_skip1": 1.0, "lowvol": 1.0, "px_over_ma200": 1.0},
        "COMP_multi4":           {"mom_6m_skip1": 1.0, "mom_12m_skip1": 1.0,
                                  "lowvol": 1.0, "px_over_ma200": 1.0},
        "COMP_mom_dd":           {"mom_12m_skip1": 1.0, "max_dd_1y": 1.0},
        "COMP_rar_dd":           {"rar_mom_12m_skip1": 1.0, "max_dd_1y": 1.0},
        "COMP_mom_rev":          {"mom_12m_skip1": 1.0, "reversal_1m": 0.5},
        "COMP_rar_rev":          {"rar_mom_12m_skip1": 1.0, "reversal_1m": 0.5},
        "COMP_allweather":       {"rar_mom_12m_skip1": 1.0, "pct_up_months_12m": 1.0,
                                  "max_dd_1y": 1.0, "efficiency_6m": 1.0},
        "COMP_mom_size":         {"mom_12m_skip1": 1.0, "size": 0.5},
        "COMP_trend_lowvol":     {"px_over_ma200": 1.0, "lowvol": 1.0},
        "COMP_52w_lowvol":       {"prox_52w_high": 1.0, "lowvol": 1.0},
    }
    return [Strategy(name=k, score_spec=v, family="composite") for k, v in specs.items()]


def permutations_of(base: Strategy, tag: str = "perm") -> list[Strategy]:
    """Cadence x weighting x n_hold x screens around one core signal."""
    out = []
    for cadence in ["buyhold", "annual", "semiannual", "quarterly", "2monthly", "monthly"]:
        for weighting in ["equal", "invvol", "invvol_cap", "score_rank", "minvar", "invbeta"]:
            for n in [5, 8, 10]:
                cap, floor, wname = None, None, weighting
                if weighting == "invvol_cap":
                    wname, cap, floor = "invvol", 0.20, 0.05
                out.append(Strategy(
                    name=f"{base.name}|{cadence}|{weighting}|n{n}",
                    score_spec=base.score_spec, family=base.family,
                    cadence=cadence, weighting=wname, n_hold=n,
                    cap=cap, floor=floor, screens=base.screens,
                    score_method=base.score_method))
    return out


def screen_variants(base: Strategy) -> list[Strategy]:
    screens = {
        "noscreen": {},
        "volq20": {"vol_1y": ("drop_top_pctile", 0.20)},
        "volq10": {"vol_1y": ("drop_top_pctile", 0.10)},
        "volq30": {"vol_1y": ("drop_top_pctile", 0.30)},
        "liq50": {"log_turnover": ("min_pctile", 0.50)},
        "liq30": {"log_turnover": ("min_pctile", 0.30)},
        "trendonly": {"px_over_ma200": ("min", 0.0)},
        "vol20_liq30": {"vol_1y": ("drop_top_pctile", 0.20),
                        "log_turnover": ("min_pctile", 0.30)},
        "vol20_trend": {"vol_1y": ("drop_top_pctile", 0.20),
                        "px_over_ma200": ("min", 0.0)},
        "dd_shallow": {"max_dd_1y": ("min_pctile", 0.30)},
    }
    return [Strategy(name=f"{base.name}|scr:{k}", score_spec=base.score_spec,
                     family=base.family, cadence=base.cadence, weighting=base.weighting,
                     n_hold=base.n_hold, cap=base.cap, floor=base.floor, screens=v)
            for k, v in screens.items()]


def sleeve_variants(base: Strategy) -> list[Strategy]:
    combos = {
        "all3": ("NIFTY100", "MIDCAP100", "SMALLCAP100"),
        "large": ("NIFTY100",),
        "mid": ("MIDCAP100",),
        "small": ("SMALLCAP100",),
        "midsmall": ("MIDCAP100", "SMALLCAP100"),
        "largemid": ("NIFTY100", "MIDCAP100"),
    }
    return [Strategy(name=f"{base.name}|slv:{k}", score_spec=base.score_spec,
                     family=base.family, cadence=base.cadence, weighting=base.weighting,
                     n_hold=base.n_hold, cap=base.cap, floor=base.floor,
                     screens=base.screens, sleeves=v)
            for k, v in combos.items()]


def sector_cap_variants(base: Strategy) -> list[Strategy]:
    return [Strategy(name=f"{base.name}|sec{k}", score_spec=base.score_spec,
                     family=base.family, cadence=base.cadence, weighting=base.weighting,
                     n_hold=base.n_hold, cap=base.cap, floor=base.floor,
                     screens=base.screens, max_per_sector=k)
            for k in [2, 3, 4]]
