"""Look-ahead and correctness tests for the signal layer.

The strongest of these is `test_future_data_cannot_change_past_signals`: it corrupts the
price panel AFTER a date and asserts that every feature value on and before that date is
bit-identical. A feature that peeked would fail it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import signals as S                                   # noqa: E402
from src.strategies import apply_cap_floor, rebalance_dates    # noqa: E402


@pytest.fixture
def panel():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2019-01-01", periods=900)
    cols = [f"S{i}" for i in range(12)]
    px = pd.DataFrame(
        100 * np.cumprod(1 + rng.normal(0.0004, 0.015, (len(idx), len(cols))), axis=0),
        index=idx, columns=cols)
    vol = pd.DataFrame(rng.integers(1e5, 1e7, px.shape), index=idx, columns=cols).astype(float)
    shares = pd.DataFrame(1e8, index=idx, columns=cols)
    bench = pd.Series(100 * np.cumprod(1 + rng.normal(0.0003, 0.010, len(idx))), index=idx)
    return px, vol, shares, bench


# ======================================================================================
# LOOK-AHEAD
# ======================================================================================
def test_future_data_cannot_change_past_signals(panel):
    """THE look-ahead test. Corrupt everything after a cut date; assert no feature value
    on or before that date moves."""
    px, vol, shares, bench = panel
    cut = px.index[600]

    base = S.build_features(px, vol, px, shares, bench=bench)

    px2 = px.copy()
    px2.loc[px2.index > cut] *= 5.0                      # violent future perturbation
    vol2 = vol.copy()
    vol2.loc[vol2.index > cut] *= 100.0
    alt = S.build_features(px2, vol2, px2, shares, bench=bench)

    checked = 0
    for k in base:
        a = base[k].loc[:cut]
        b = alt[k].loc[:cut]
        assert a.shape == b.shape, k
        # NaN pattern must match too
        assert (a.isna() == b.isna()).all().all(), f"{k}: NaN pattern changed"
        np.testing.assert_allclose(a.fillna(0).to_numpy(), b.fillna(0).to_numpy(),
                                   rtol=1e-12, atol=1e-12,
                                   err_msg=f"feature {k!r} leaked future data")
        checked += 1
    assert checked > 25, "too few features checked -- the test is not doing its job"


def test_features_asof_is_strictly_before(panel):
    """The signal row used at a rebalance must be dated STRICTLY BEFORE the trade date."""
    px, vol, shares, bench = panel
    f = S.build_features(px, vol, px, shares, bench=bench)
    d = px.index[500]
    row = S.features_asof(f, d)
    prior = px.index[px.index < d][-1]
    assert row["mom_6m"].equals(f["mom_6m"].loc[prior].reindex(row.index))
    # and it must NOT equal the value on the trade date itself
    assert not np.allclose(row["mom_6m"].fillna(0),
                           f["mom_6m"].loc[d].reindex(row.index).fillna(0))


def test_no_negative_shift_in_source():
    """Static guard: a `.shift(-n)` in the feature builder is almost always look-ahead.
    Only the two documented reverse-window uses are allowed, and they are in pit_universe."""
    src = (Path(__file__).resolve().parent.parent / "src" / "signals.py").read_text(encoding="utf-8")
    import re
    bad = [m for m in re.findall(r"\.shift\(\s*-\s*\d+", src)]
    assert not bad, f"negative shift found in signals.py: {bad}"


# ======================================================================================
# FEATURE CORRECTNESS
# ======================================================================================
def test_momentum_hand_case():
    idx = pd.bdate_range("2021-01-01", periods=300)
    px = pd.DataFrame({"A": np.linspace(100, 200, 300)}, index=idx)
    f = S._mom(px, 252)
    expected = px["A"].iloc[252] / px["A"].iloc[0] - 1
    assert f["A"].iloc[252] == pytest.approx(expected)


def test_skip_month_momentum_excludes_last_month():
    idx = pd.bdate_range("2021-01-01", periods=300)
    a = np.linspace(100, 150, 300)
    a[-21:] = 1000.0                                    # explode the last month only
    px = pd.DataFrame({"A": a}, index=idx)
    m_skip = S._mom(px, 231, skip=21).iloc[-1]["A"]
    m_plain = S._mom(px, 252).iloc[-1]["A"]
    assert m_plain > 5.0                                # plain sees the explosion
    assert m_skip < 1.0                                 # skip version does not


def test_cs_rank_is_row_wise():
    df = pd.DataFrame({"a": [1.0, 4.0], "b": [2.0, 3.0], "c": [3.0, 2.0], "d": [4.0, 1.0]})
    r = S.cs_rank(df)
    assert r.iloc[0].tolist() == [0.25, 0.5, 0.75, 1.0]
    assert r.iloc[1].tolist() == [1.0, 0.75, 0.5, 0.25]


def test_composite_score_depends_only_on_rank_not_magnitude():
    """A 500x outlier must score exactly the same as a mild outperformer, because only its
    RANK enters. This is why the composite uses percentile ranks in a universe where a
    single smallcap can return +40000%."""
    mild = pd.DataFrame({"mom_12m": [0.1, 0.2, 0.3, 0.31], "lowvol": [4.0, 3.0, 2.0, 1.0]},
                        index=list("ABCD"))
    wild = pd.DataFrame({"mom_12m": [0.1, 0.2, 0.3, 500.0], "lowvol": [4.0, 3.0, 2.0, 1.0]},
                        index=list("ABCD"))
    spec = {"mom_12m": 1.0, "lowvol": 1.0}
    s_mild = S.composite_score(mild, spec, method="rank")
    s_wild = S.composite_score(wild, spec, method="rank")
    pd.testing.assert_series_equal(s_mild, s_wild)
    assert s_wild.between(0, 1).all()

    # a single dominant feature must produce a strict ordering
    only_mom = S.composite_score(wild, {"mom_12m": 1.0}, method="rank")
    assert only_mom.idxmax() == "D" and only_mom.idxmin() == "A"


# ======================================================================================
# WEIGHTING
# ======================================================================================
def test_cap_floor_respected_and_sums_to_one():
    """The real configuration: 10 names, 20% cap, 5% floor -- feasible (0.2*10 = 2 >= 1)."""
    w = pd.Series([0.60, 0.20, 0.06, 0.04, 0.03, 0.025, 0.02, 0.015, 0.006, 0.004],
                  index=list("ABCDEFGHIJ"))
    out = apply_cap_floor(w, cap=0.20, floor=0.05)
    assert out.sum() == pytest.approx(1.0, abs=1e-12)
    assert out.max() <= 0.20 + 1e-9
    assert out.min() >= 0.05 - 1e-9
    # ordering preserved among the un-clipped names
    assert out["A"] >= out["B"] >= out["C"]


def test_cap_floor_infeasible_falls_back_to_equal_weight():
    """With 4 names a 20% cap cannot reach 100%. The correct fallback is equal weight,
    NOT the un-capped weights -- otherwise a 'capped' book silently holds 85% in one name."""
    w = pd.Series([0.9, 0.05, 0.03, 0.02], index=list("ABCD"))
    out = apply_cap_floor(w, cap=0.20, floor=0.05)
    assert out.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.allclose(out.to_numpy(), 0.25)

    w2 = pd.Series([0.5, 0.5], index=["A", "B"])
    out2 = apply_cap_floor(w2, cap=0.20, floor=None)
    assert np.allclose(out2.to_numpy(), 0.5)


def test_invvol_gives_more_weight_to_calmer_names():
    from src.strategies import make_weights
    feat = pd.DataFrame({"vol_1y": [0.01, 0.04]}, index=["CALM", "WILD"])
    w = make_weights("invvol", ["CALM", "WILD"], feat, pd.Series(dtype=float),
                     cap=None, floor=None)
    assert w["CALM"] > w["WILD"]
    assert w["CALM"] / w["WILD"] == pytest.approx(4.0)


# ======================================================================================
# CALENDAR
# ======================================================================================
def test_quarterly_cadence_gives_20_rebalances_over_5_years():
    td = pd.bdate_range("2021-01-01", "2025-12-31")
    d = rebalance_dates(td, "2021-01-01", "2025-12-31", "quarterly")
    assert len(d) == 20
    assert d[0] == td[0]


def test_buyhold_gives_exactly_one_rebalance():
    td = pd.bdate_range("2021-01-01", "2025-12-31")
    assert len(rebalance_dates(td, "2021-01-01", "2025-12-31", "buyhold")) == 1


def test_monthly_gives_60_rebalances():
    td = pd.bdate_range("2021-01-01", "2025-12-31")
    assert len(rebalance_dates(td, "2021-01-01", "2025-12-31", "monthly")) == 60


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
