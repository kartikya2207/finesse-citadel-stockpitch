"""Overfitting statistics: Deflated Sharpe Ratio and Probability of Backtest Overfitting.

Both are computed on the HONEST trial count -- every variant evaluated anywhere in the
sweep, not just the ones we liked. Reporting a best-of-N Sharpe without this correction is
precisely the failure this module exists to prevent.

References
----------
Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio: Correcting for Selection Bias,
Backtest Overfitting and Non-Normality", Journal of Portfolio Management.
Bailey, Borwein, Lopez de Prado & Zhu (2017), "The Probability of Backtest Overfitting",
Journal of Computational Finance.  (combinatorially-symmetric cross-validation)
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

from .config import TRADING_DAYS

EULER_MASCHERONI = 0.5772156649015329


def expected_max_sharpe(n_trials: int, var_trial_sharpe: float) -> float:
    """E[max SR] across `n_trials` independent trials whose SRs have variance
    `var_trial_sharpe` -- the benchmark a strategy must beat to be more than luck."""
    if n_trials < 2:
        return 0.0
    sd = math.sqrt(var_trial_sharpe) if var_trial_sharpe > 0 else 0.0
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return sd * ((1 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2)


def probabilistic_sharpe(sr_hat: float, sr_benchmark: float, n: int,
                         skew: float, kurt: float) -> float:
    """P(true SR > sr_benchmark) given the observed SR and the return distribution's
    higher moments. `sr_hat`, `sr_benchmark` and `n` must all be on the SAME frequency."""
    denom = math.sqrt(max(1e-12, 1 - skew * sr_hat + (kurt - 1) / 4.0 * sr_hat ** 2))
    z = (sr_hat - sr_benchmark) * math.sqrt(max(1, n - 1)) / denom
    return float(stats.norm.cdf(z))


def deflated_sharpe(returns: pd.Series, n_trials: int,
                    trial_sharpes: list[float] | None = None) -> dict:
    """Deflated Sharpe Ratio on a DAILY return series.

    Everything is computed at daily frequency (SR_daily = mean/sd), which is the frequency
    the observations actually have; annualising first would misstate the sample size.
    """
    r = returns.dropna()
    n = len(r)
    if n < 30:
        return {"error": "too few observations"}
    sr_d = float(r.mean() / r.std(ddof=1))
    sk = float(stats.skew(r, bias=False))
    ku = float(stats.kurtosis(r, fisher=False, bias=False))

    if trial_sharpes is not None and len(trial_sharpes) > 1:
        var_trials = float(np.var(trial_sharpes, ddof=1))
    else:                                   # fall back to the sampling variance of one SR
        var_trials = (1 + 0.5 * sr_d ** 2) / max(1, n - 1)

    sr_star = expected_max_sharpe(n_trials, var_trials)
    dsr = probabilistic_sharpe(sr_d, sr_star, n, sk, ku)
    return {
        "n_obs": n,
        "n_trials": n_trials,
        "sharpe_daily": sr_d,
        "sharpe_annualised": sr_d * math.sqrt(TRADING_DAYS),
        "skew": sk,
        "kurtosis": ku,
        "var_across_trials": var_trials,
        "expected_max_sharpe_daily": sr_star,
        "expected_max_sharpe_ann": sr_star * math.sqrt(TRADING_DAYS),
        "deflated_sharpe_prob": dsr,
        "prob_sharpe_is_a_fluke": 1 - dsr,
        "psr_vs_zero": probabilistic_sharpe(sr_d, 0.0, n, sk, ku),
    }


def pbo_cscv(perf_matrix: pd.DataFrame, n_splits: int = 12) -> dict:
    """Probability of Backtest Overfitting via combinatorially-symmetric CV.

    `perf_matrix`: rows = time slices, columns = strategy variants, values = performance
    (Sharpe or mean return) of that variant in that slice. The matrix is split into
    `n_splits` blocks; every balanced half is used once as in-sample and its complement as
    out-of-sample. PBO = P(the IS-best variant lands in the bottom half OOS).

    PBO near 0.5 means the selection procedure carries no information -- the winner is
    whoever got lucky. Below ~0.2 is the usual comfort threshold.
    """
    M = perf_matrix.dropna(axis=1, how="any")
    if M.shape[1] < 2 or M.shape[0] < n_splits:
        return {"error": "matrix too small", "shape": tuple(M.shape)}
    blocks = np.array_split(np.arange(len(M)), n_splits)
    half = n_splits // 2
    logits, ranks_oos = [], []
    combos = list(itertools.combinations(range(n_splits), half))
    if len(combos) > 2000:                       # cap the work; symmetric sample
        rng = np.random.default_rng(0)
        combos = [combos[i] for i in rng.choice(len(combos), 2000, replace=False)]
    for c in combos:
        is_idx = np.concatenate([blocks[i] for i in c])
        oos_idx = np.concatenate([blocks[i] for i in range(n_splits) if i not in c])
        is_perf = M.iloc[is_idx].mean()
        oos_perf = M.iloc[oos_idx].mean()
        best = is_perf.idxmax()
        rank = oos_perf.rank(pct=True)[best]      # 1.0 = best OOS, 0.0 = worst
        ranks_oos.append(float(rank))
        w = max(min(rank, 1 - 1e-9), 1e-9)
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return {
        "n_combinations": len(combos),
        "pbo": float((logits <= 0).mean()),
        "median_oos_rank_of_is_best": float(np.median(ranks_oos)),
        "mean_logit": float(logits.mean()),
        "interpretation": ("PBO is the probability that the variant chosen as best "
                           "in-sample underperforms the median out-of-sample."),
    }


def harvey_liu_hurdle(n_trials: int, base_t: float = 2.0) -> float:
    """Multiple-testing t-statistic hurdle. Harvey, Liu & Zhu (2016) argue ~3.0 for the
    published factor literature; the Bonferroni-style hurdle grows with the trial count."""
    if n_trials <= 1:
        return base_t
    return float(stats.norm.ppf(1 - 0.05 / (2 * n_trials)))


def t_stat_of_returns(returns: pd.Series) -> float:
    r = returns.dropna()
    return float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r))))


def walk_forward_slices(dates: pd.DatetimeIndex, n_folds: int = 5,
                        min_train_years: float = 1.5) -> list[tuple]:
    """Expanding-window folds: (train_end, test_start, test_end)."""
    start, end = dates[0], dates[-1]
    first_test = start + pd.DateOffset(days=int(min_train_years * 365.25))
    edges = pd.date_range(first_test, end, periods=n_folds + 1)
    return [(edges[i], edges[i], edges[i + 1]) for i in range(n_folds)]
