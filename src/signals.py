"""Signal library.

Every feature is a rolling function of the daily panel, so a value at date t depends only
on data up to and including t. That is what makes the pipeline look-ahead free BY
CONSTRUCTION rather than by inspection: there is no `.shift(-k)` and no full-sample
statistic anywhere in this module. `tests/test_signals.py` asserts it.

Usage: build the feature panels once over the full history, then at each rebalance date r
read the row for the LAST TRADING DAY STRICTLY BEFORE r (`features_asof`). Trades then
execute at r's close, so the signal is always older than the trade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def daily_returns(adjclose: pd.DataFrame) -> pd.DataFrame:
    return adjclose.pct_change()


def _mom(adjclose: pd.DataFrame, lookback: int, skip: int = 0) -> pd.DataFrame:
    """Total return over `lookback` days ending `skip` days ago."""
    end = adjclose.shift(skip)
    start = adjclose.shift(skip + lookback)
    return end / start - 1.0


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score, row-wise."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1)
    return df.sub(mu, axis=0).div(sd.replace(0, np.nan), axis=0)


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional percentile rank in [0, 1], row-wise. Robust to outliers, which
    matters a lot in a smallcap universe where a single name can 10x."""
    return df.rank(axis=1, pct=True)


def winsorise(s: pd.Series, lo: float = 0.02, hi: float = 0.98) -> pd.Series:
    if s.dropna().empty:
        return s
    a, b = s.quantile(lo), s.quantile(hi)
    return s.clip(a, b)


# --------------------------------------------------------------------------------------
# Feature panels
# --------------------------------------------------------------------------------------
def build_features(adjclose: pd.DataFrame, volume: pd.DataFrame,
                   rawprice: pd.DataFrame, shares: pd.DataFrame,
                   bench: pd.Series | None = None) -> dict[str, pd.DataFrame]:
    """All price/volume-derived features. Keys are feature names used by strategies."""
    f: dict[str, pd.DataFrame] = {}
    ret = daily_returns(adjclose)
    f["ret"] = ret

    # ---- momentum -----------------------------------------------------------------
    for m, d in [(1, 21), (3, 63), (6, 126), (9, 189), (12, 252), (18, 378), (24, 504)]:
        f[f"mom_{m}m"] = _mom(adjclose, d)
    f["mom_12m_skip1"] = _mom(adjclose, 231, skip=21)     # 12m return, last month skipped
    f["mom_6m_skip1"] = _mom(adjclose, 105, skip=21)
    f["mom_3m_skip1"] = _mom(adjclose, 42, skip=21)
    f["mom_avg_6_12_skip1"] = 0.5 * (f["mom_6m_skip1"] + f["mom_12m_skip1"])
    f["reversal_1m"] = -f["mom_1m"]
    f["reversal_1w"] = -_mom(adjclose, 5)

    # ---- volatility / risk ---------------------------------------------------------
    f["vol_1y"] = ret.rolling(TRADING_DAYS, min_periods=180).std()
    f["vol_6m"] = ret.rolling(126, min_periods=90).std()
    f["vol_3m"] = ret.rolling(63, min_periods=45).std()
    f["dvol_1y"] = ret.where(ret < 0).rolling(TRADING_DAYS, min_periods=180).std()
    f["lowvol"] = -f["vol_1y"]

    # ---- risk-adjusted momentum ----------------------------------------------------
    for k in ["mom_6m", "mom_12m", "mom_12m_skip1", "mom_avg_6_12_skip1", "mom_3m"]:
        f[f"rar_{k}"] = f[k] / f["vol_1y"].replace(0, np.nan)

    # ---- trend / position ----------------------------------------------------------
    ma50 = adjclose.rolling(50, min_periods=40).mean()
    ma200 = adjclose.rolling(200, min_periods=150).mean()
    f["px_over_ma200"] = adjclose / ma200 - 1.0
    f["px_over_ma50"] = adjclose / ma50 - 1.0
    f["ma50_over_ma200"] = ma50 / ma200 - 1.0
    hi52 = adjclose.rolling(TRADING_DAYS, min_periods=180).max()
    lo52 = adjclose.rolling(TRADING_DAYS, min_periods=180).min()
    f["prox_52w_high"] = adjclose / hi52
    f["off_52w_low"] = adjclose / lo52 - 1.0
    f["above_ma200"] = (adjclose > ma200).astype(float)

    # ---- consistency ---------------------------------------------------------------
    f["pct_up_days_6m"] = (ret > 0).rolling(126, min_periods=90).mean()
    monthly_up = (adjclose / adjclose.shift(21) - 1 > 0).astype(float)
    f["pct_up_months_12m"] = monthly_up.rolling(252, min_periods=180).mean()
    # path smoothness: return divided by the sum of absolute daily moves
    f["efficiency_6m"] = (_mom(adjclose, 126)
                          / ret.abs().rolling(126, min_periods=90).sum().replace(0, np.nan))

    # ---- drawdown ------------------------------------------------------------------
    roll_max = adjclose.rolling(TRADING_DAYS, min_periods=180).max()
    f["dd_from_1y_high"] = adjclose / roll_max - 1.0
    f["max_dd_1y"] = (adjclose / adjclose.rolling(TRADING_DAYS, min_periods=180).max() - 1
                      ).rolling(TRADING_DAYS, min_periods=180).min()

    # ---- liquidity / size ----------------------------------------------------------
    turnover = adjclose * volume
    f["turnover_60d"] = turnover.rolling(60, min_periods=40).median()
    f["log_turnover"] = np.log(f["turnover_60d"].replace(0, np.nan))
    f["amihud"] = (ret.abs() / turnover.replace(0, np.nan)).rolling(
        60, min_periods=40).mean() * 1e9
    mcap = rawprice * shares.reindex_like(rawprice)
    f["mcap"] = mcap
    f["log_mcap"] = np.log(mcap.replace(0, np.nan))
    f["size"] = -f["log_mcap"]                     # small-size factor

    # ---- beta / residual momentum --------------------------------------------------
    if bench is not None:
        b = bench.reindex(adjclose.index).ffill()
        br = b.pct_change()
        cov = ret.rolling(TRADING_DAYS, min_periods=180).cov(br)
        var = br.rolling(TRADING_DAYS, min_periods=180).var()
        beta = cov.div(var, axis=0)
        f["beta"] = beta
        f["lowbeta"] = -beta
        resid = ret.sub(beta.mul(br, axis=0))
        f["resid_mom_12m"] = (1 + resid).rolling(231, min_periods=180).apply(
            np.prod, raw=True).shift(21) - 1 if False else \
            resid.rolling(231, min_periods=180).sum().shift(21)
        f["resid_mom_6m"] = resid.rolling(105, min_periods=80).sum().shift(21)
        f["idio_vol"] = resid.rolling(TRADING_DAYS, min_periods=180).std()
        f["rar_resid_mom_12m"] = f["resid_mom_12m"] / f["idio_vol"].replace(0, np.nan)

    return f


def features_asof(features: dict[str, pd.DataFrame], date: pd.Timestamp,
                  names: list[str] | None = None) -> pd.DataFrame:
    """Feature values on the last trading day STRICTLY BEFORE `date`.

    Strictly-before is the whole point: the signal must be observable before the trade.
    """
    key = next(iter(features))
    idx = features[key].index
    prior = idx[idx < pd.Timestamp(date)]
    if len(prior) == 0:
        return pd.DataFrame()
    t = prior[-1]
    cols = names or [k for k in features if k != "ret"]
    return pd.DataFrame({k: features[k].loc[t] for k in cols if k in features})


# --------------------------------------------------------------------------------------
# Composite scoring
# --------------------------------------------------------------------------------------
def composite_score(feat: pd.DataFrame, spec: dict[str, float],
                    method: str = "rank") -> pd.Series:
    """Weighted combination of features after cross-sectional standardisation.

    `method='rank'` (default) uses percentile ranks — far more robust than z-scores in a
    universe where one smallcap can return +400% and blow up every mean and variance.
    """
    parts = []
    for name, w in spec.items():
        if name not in feat.columns:
            continue
        s = feat[name].astype(float)
        if s.notna().sum() < 3:      # need a cross-section to rank against
            continue
        if method == "rank":
            v = s.rank(pct=True)
        elif method == "z":
            v = winsorise(s)
            v = (v - v.mean()) / (v.std() if v.std() else np.nan)
        else:
            raise ValueError(method)
        parts.append(w * v)
    if not parts:
        return pd.Series(dtype="float64")
    total = sum(abs(w) for w in spec.values() if w) or 1.0
    return pd.concat(parts, axis=1).sum(axis=1, min_count=1) / total
