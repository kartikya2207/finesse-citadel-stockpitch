"""Machine-learning stock selection, done honestly.

SAMPLE SIZE -- READ THIS FIRST
------------------------------
Stacking ~250 names x ~60 monthly rebalances gives ~15,000 rows, which looks like plenty.
It is not. Returns within one period share a common market factor, so the rows in a period
are almost one observation. The EFFECTIVE sample size is the number of PERIODS -- about 60,
falling to 20 at quarterly cadence. Any model with more than a handful of free parameters
will fit noise.

Two design choices follow from that, and both are non-negotiable here:

1. **Cross-sectional demeaning of the target.** The label is a name's forward return MINUS
   the cross-sectional mean that period. Without this the model spends its capacity
   predicting the market's direction from 20-60 observations, which is hopeless, and the
   backtest inherits period-level luck dressed up as skill.

2. **Strict walk-forward.** At every rebalance the model is refit on data ending strictly
   before that date and never sees a single future row. There is no full-sample fit
   anywhere, not even for feature scaling.

Everything here is reported with the same deflated-Sharpe and PBO treatment as the factor
models, and every fitted variant counts against the multiple-testing budget.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import (GradientBoostingRegressor, HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.linear_model import ElasticNet, Lasso, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from .config import SEED
from .pit_universe import universe_asof
from .signals import features_asof

# Features offered to the models. Deliberately a modest, economically motivated set --
# throwing 60 engineered features at 60 effective observations is how ML strategies die.
ML_FEATURES = [
    "mom_1m", "mom_3m", "mom_6m", "mom_9m", "mom_12m", "mom_12m_skip1",
    "vol_1y", "vol_3m", "dvol_1y", "beta", "idio_vol",
    "px_over_ma200", "px_over_ma50", "prox_52w_high", "max_dd_1y",
    "pct_up_months_12m", "efficiency_6m", "log_mcap", "log_turnover", "amihud",
]


def make_model(kind: str, seed: int = SEED):
    """Model zoo. Hyperparameters are deliberately conservative -- heavy regularisation,
    shallow trees, early stopping -- because the effective sample is ~60 periods."""
    if kind == "ridge":
        return Ridge(alpha=10.0, random_state=None)
    if kind == "ridge_strong":
        return Ridge(alpha=100.0)
    if kind == "lasso":
        return Lasso(alpha=0.001, max_iter=5000, random_state=seed)
    if kind == "elasticnet":
        return ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=5000, random_state=seed)
    if kind == "rf":
        return RandomForestRegressor(n_estimators=300, max_depth=4, min_samples_leaf=50,
                                     max_features=0.5, random_state=seed, n_jobs=-1)
    if kind == "gbm":
        return GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.03,
                                         subsample=0.7, min_samples_leaf=50,
                                         random_state=seed)
    if kind == "hgb":
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.03,
                                             max_iter=250, min_samples_leaf=50,
                                             l2_regularization=1.0, random_state=seed)
    if kind == "mlp":
        return MLPRegressor(hidden_layer_sizes=(16,), alpha=1.0, max_iter=2000,
                            early_stopping=True, random_state=seed)
    raise ValueError(kind)


def build_dataset(features: dict, adjclose: pd.DataFrame, membership: dict,
                  dates: list[pd.Timestamp], feature_names: list[str] = None,
                  rank_features: bool = True) -> pd.DataFrame:
    """Panel of (date, symbol) -> features + cross-sectionally demeaned forward return."""
    feature_names = feature_names or ML_FEATURES
    rows = []
    ds = list(dates)
    for i, d in enumerate(ds[:-1]):
        nxt = ds[i + 1]
        if d not in adjclose.index or nxt not in adjclose.index:
            continue
        feat = features_asof(features, d, names=feature_names)
        if feat.empty:
            continue
        cand = [c for c in universe_asof(membership, d) if c in feat.index]
        X = feat.loc[cand, [c for c in feature_names if c in feat.columns]].astype(float)
        if rank_features:
            # cross-sectional percentile ranks: scale-free, outlier-robust, and comparable
            # across periods without any full-sample statistic
            X = X.rank(pct=True)
        y = (adjclose.loc[nxt, cand] / adjclose.loc[d, cand] - 1.0)
        ok = X.notna().all(axis=1) & y.notna()
        if ok.sum() < 30:
            continue
        X, y = X[ok], y[ok]
        y = y - y.mean()                       # CROSS-SECTIONAL DEMEANING (see module docstring)
        df = X.copy()
        df["y"] = y
        df["date"] = d
        df["symbol"] = X.index
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def walk_forward_predictions(dataset: pd.DataFrame, kind: str, min_train_periods: int = 8,
                             feature_names: list[str] = None,
                             seed: int = SEED) -> pd.DataFrame:
    """Refit at every rebalance on strictly prior data; predict the current cross-section.

    Returns (date, symbol, pred). The first `min_train_periods` dates produce no prediction,
    which is correct -- there was nothing to learn from yet. That shortens the ML backtest
    relative to the factor models, and the comparison table says so explicitly.
    """
    feature_names = feature_names or [c for c in dataset.columns
                                      if c not in ("y", "date", "symbol")]
    dates = sorted(dataset["date"].unique())
    out = []
    for i, d in enumerate(dates):
        if i < min_train_periods:
            continue
        train = dataset[dataset["date"] < d]
        test = dataset[dataset["date"] == d]
        if len(train) < 200 or test.empty:
            continue
        Xtr = train[feature_names].to_numpy()
        ytr = train["y"].to_numpy()
        Xte = test[feature_names].to_numpy()
        sc = StandardScaler().fit(Xtr)          # fitted on TRAIN ONLY
        model = make_model(kind, seed=seed)
        try:
            model.fit(sc.transform(Xtr), ytr)
            pred = model.predict(sc.transform(Xte))
        except Exception:                        # noqa: BLE001
            continue
        out.append(pd.DataFrame({"date": d, "symbol": test["symbol"].to_numpy(),
                                 "pred": pred}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def predictions_to_weights(preds: pd.DataFrame, features: dict, n_hold: int = 10,
                           weighting: str = "invvol", cap: float | None = 0.20,
                           floor: float | None = 0.05) -> dict:
    """Top-n by predicted cross-sectional return, weighted by the same rule as the factor
    models so the comparison isolates the SIGNAL, not the weighting scheme."""
    from .strategies import make_weights
    out = {}
    for d, g in preds.groupby("date"):
        g = g.sort_values("pred", ascending=False)
        picks = list(g["symbol"].head(n_hold))
        if not picks:
            continue
        feat = features_asof(features, d)
        picks = [p for p in picks if p in feat.index]
        if not picks:
            continue
        out[pd.Timestamp(d)] = make_weights(weighting, picks, feat.loc[picks],
                                            g.set_index("symbol")["pred"],
                                            cap=cap, floor=floor)
    return out


def feature_importance(dataset: pd.DataFrame, kind: str = "rf",
                       feature_names: list[str] = None, seed: int = SEED) -> pd.Series:
    """Full-sample importances, for INTERPRETATION ONLY. This is not used to select
    features for the backtest -- that would leak the whole sample into every fold."""
    feature_names = feature_names or [c for c in dataset.columns
                                      if c not in ("y", "date", "symbol")]
    X = dataset[feature_names].to_numpy()
    y = dataset["y"].to_numpy()
    m = make_model(kind, seed=seed)
    m.fit(StandardScaler().fit_transform(X), y)
    if hasattr(m, "feature_importances_"):
        imp = m.feature_importances_
    elif hasattr(m, "coef_"):
        imp = np.abs(np.ravel(m.coef_))
    else:
        return pd.Series(dtype=float)
    return pd.Series(imp, index=feature_names).sort_values(ascending=False)


# --------------------------------------------------------------------------------------
# Regime detection (overlay experiments)
# --------------------------------------------------------------------------------------
def regime_labels(bench: pd.Series, method: str = "trend", window: int = 200) -> pd.Series:
    """Simple, explainable regime labels on the benchmark. 1 = risk-on, 0 = risk-off.

    Deliberately not an HMM for the submitted model: a two-state Gaussian HMM fitted on a
    single 5-year benchmark series has enormous parameter uncertainty and its state
    assignments are not stable to the seed or the window. A 200-day trend rule says almost
    the same thing and can be defended in one sentence.
    """
    b = bench.dropna()
    if method == "trend":
        return (b > b.rolling(window, min_periods=window // 2).mean()).astype(float)
    if method == "vol":
        v = b.pct_change().rolling(60, min_periods=40).std()
        return (v < v.rolling(500, min_periods=250).median()).astype(float)
    if method == "hmm":
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            return regime_labels(bench, "trend", window)
        r = b.pct_change().dropna().to_numpy().reshape(-1, 1)
        m = GaussianHMM(n_components=2, covariance_type="diag", n_iter=200,
                        random_state=SEED).fit(r)
        st = m.predict(r)
        bull = int(np.argmax(m.means_.ravel()))
        return pd.Series((st == bull).astype(float), index=b.index[1:])
    raise ValueError(method)
