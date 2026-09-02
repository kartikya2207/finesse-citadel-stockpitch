"""Tests for the backtest engine. These run BEFORE the engine is trusted.

The centrepiece is `test_hand_computed_case`: 3 stocks, 5 days, one rebalance, with the
expected NAV and PNL worked out by hand in the docstring and asserted to 6 decimals.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import run_backtest                      # noqa: E402
from src import metrics as M                               # noqa: E402


D = pd.date_range("2021-01-04", periods=5, freq="B")       # Mon..Fri


def _panel():
    """3 stocks, 5 days. Deliberately simple round numbers."""
    return pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0, 121.0, 121.0],
            "BBB": [200.0, 200.0, 200.0, 220.0, 198.0],
            "CCC": [ 50.0,  45.0,  45.0,  45.0,  54.0],
        },
        index=D,
    )


# ======================================================================================
# 1. HAND-COMPUTED CASE
# ======================================================================================
def test_hand_computed_case():
    r"""HAND CALCULATION — verify every line by eye.

    Capital = 1,000,000.  Cost = 0.1% per side.  One rebalance on day 0 (2021-01-04),
    equal weights 50/50 in AAA and BBB, no further rebalancing.

    DAY 0 (prices AAA=100, BBB=200):
      NAV before trading                       = 1,000,000.000000
      Target value each                        =   500,000.000000
      Units AAA = 500000/100                   =     5,000.000000
      Units BBB = 500000/200                   =     2,500.000000
      Traded notional                          = 500,000 + 500,000 = 1,000,000
      Cost = 1,000,000 * 0.001                 =     1,000.000000
      Cash = 1,000,000 - 1,000,000 - 1,000     =    -1,000.000000  <-- would be negative

      The engine funds costs from cash, so buying 100% of NAV leaves cash short by the
      cost. To keep cash non-negative the test targets 99% invested / 1% cash:
      Target value each = 0.495 * 1,000,000    =   495,000.000000
      Units AAA = 495000/100                   =     4,950.000000
      Units BBB = 495000/200                   =     2,475.000000
      Traded notional = 990,000
      Cost = 990,000 * 0.001                   =       990.000000
      Cash = 1,000,000 - 990,000 - 990         =     9,010.000000
      NAV day 0 = 9,010 + 4950*100 + 2475*200  =   999,010.000000
                = 9,010 + 495,000 + 495,000    =   999,010.000000   [= 1,000,000 - 990]

    DAY 1 (AAA=110, BBB=200):
      NAV = 9,010 + 4950*110 + 2475*200
          = 9,010 + 544,500 + 495,000          = 1,048,510.000000

    DAY 2 (AAA=121, BBB=200):
      NAV = 9,010 + 4950*121 + 2475*200
          = 9,010 + 598,950 + 495,000          = 1,102,960.000000

    DAY 3 (AAA=121, BBB=220):
      NAV = 9,010 + 598,950 + 2475*220
          = 9,010 + 598,950 + 544,500          = 1,152,460.000000

    DAY 4 (AAA=121, BBB=198):
      NAV = 9,010 + 598,950 + 2475*198
          = 9,010 + 598,950 + 490,050          = 1,098,010.000000

    Total Net PNL = 1,098,010 - 1,000,000      =    98,010.000000
    Total costs                                =       990.000000
    """
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.495, "BBB": 0.495})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1_000_000.0,
                       cost_per_side=0.001, max_positions=10)

    expected = [999_010.0, 1_048_510.0, 1_102_960.0, 1_152_460.0, 1_098_010.0]
    for i, e in enumerate(expected):
        assert res.nav.iloc[i] == pytest.approx(e, abs=1e-6), \
            f"day {i}: got {res.nav.iloc[i]:.6f}, hand-computed {e:.6f}"

    assert res.cash.iloc[0] == pytest.approx(9_010.0, abs=1e-6)
    assert res.trades["cost"].sum() == pytest.approx(990.0, abs=1e-9)
    assert res.nav.iloc[-1] - 1_000_000.0 == pytest.approx(98_010.0, abs=1e-6)
    assert len(res.trades) == 2
    assert set(res.trades["side"]) == {"BUY"}


# ======================================================================================
# 2. COST ARITHMETIC
# ======================================================================================
def test_cost_is_exactly_ten_bps_of_every_leg():
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.49}),
          D[2]: pd.Series({"BBB": 0.5, "CCC": 0.49})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1_000_000.0,
                       cost_per_side=0.001)
    assert np.allclose(res.trades["cost"], res.trades["notional"] * 0.001, atol=1e-12)
    assert (res.trades["notional"] > 0).all()


def test_zero_cost_beats_costed_by_exactly_the_costs():
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.5})}
    hi = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, cost_per_side=0.0)
    lo = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, cost_per_side=0.001)
    assert hi.nav.iloc[-1] > lo.nav.iloc[-1]
    # 0.1% entry drag on a fully invested book, compounded through the period
    assert lo.nav.iloc[-1] / hi.nav.iloc[-1] == pytest.approx(1/1.001, rel=1e-9)


# ======================================================================================
# 3. INVARIANTS
# ======================================================================================
def test_max_positions_enforced():
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.33, "BBB": 0.33, "CCC": 0.33})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, max_positions=2)
    assert res.holdings_count.max() <= 2


def test_nav_continuity_across_rebalance():
    """NAV immediately after a rebalance must equal NAV before, minus exactly the costs."""
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.49}),
          D[2]: pd.Series({"CCC": 0.5, "BBB": 0.49})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, strict=True)
    assert res.diagnostics["nav_continuity_max_err"] < 1e-6

    nav_prev = res.nav.iloc[1]                       # end of day 1, no trades that day
    day2_cost = res.trades.loc[res.trades["date"] == D[2], "cost"].sum()
    # revalue day-1 units at day-2 prices, then subtract the day-2 costs
    drift = (res.positions.iloc[1].dropna() / px.iloc[1][res.positions.iloc[1].dropna().index]
             * px.iloc[2][res.positions.iloc[1].dropna().index]).sum() + res.cash.iloc[1]
    assert res.nav.iloc[2] == pytest.approx(drift - day2_cost, abs=1e-6)


def test_no_negative_holdings_or_cash():
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.6, "BBB": 0.39}),
          D[1]: pd.Series({"CCC": 0.99}),
          D[3]: pd.Series({"AAA": 0.5, "CCC": 0.49})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, strict=True)
    assert (res.cash >= -1e-9).all()
    assert (res.positions.fillna(0.0) >= -1e-9).all().all()


def test_weights_sum_to_one_when_fully_invested():
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.5})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, cost_per_side=0.0)
    assert res.weights.iloc[0].sum() == pytest.approx(1.0, abs=1e-12)


def test_no_nan_in_nav():
    px = _panel().copy()
    px.loc[D[2], "BBB"] = np.nan                 # simulate a missing print
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.49})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6)
    assert res.nav.notna().all()
    # stale price carried forward, not dropped to zero
    assert res.nav.iloc[2] == pytest.approx(
        res.cash.iloc[2] + res.positions.iloc[2].sum(), abs=1e-6)


# ======================================================================================
# 4. LOOK-AHEAD
# ======================================================================================
def test_shifting_prices_changes_results():
    """If the engine used future data, shifting the price panel forward would not change
    the answer in the way it must. Shift by one day and assert the result moves."""
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.49})}
    base = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6)
    shifted = px.shift(1).bfill()
    alt = run_backtest(shifted, tw, start=D[0], end=D[-1], capital=1e6)
    assert abs(base.nav.iloc[-1] - alt.nav.iloc[-1]) > 1.0


def test_future_prices_do_not_affect_past_nav():
    """Perturbing prices AFTER a date must leave NAV on and before that date unchanged."""
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.5, "BBB": 0.49}),
          D[1]: pd.Series({"AAA": 0.3, "CCC": 0.69})}
    base = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6)
    tampered = px.copy()
    tampered.iloc[3:] *= 3.0                     # blow up the future
    alt = run_backtest(tampered, tw, start=D[0], end=D[-1], capital=1e6)
    pd.testing.assert_series_equal(base.nav.iloc[:3], alt.nav.iloc[:3])


# ======================================================================================
# 5. ROUND TRIPS / TRADE STATS
# ======================================================================================
def test_round_trip_accounting():
    """Buy AAA at 100, sell at 121 -> gross +21% on the deployed capital, less two
    0.1% legs. Verify the recorded round-trip PNL to the rupee."""
    px = _panel()
    tw = {D[0]: pd.Series({"AAA": 0.99}),
          D[2]: pd.Series({"BBB": 0.99})}
    res = run_backtest(px, tw, start=D[0], end=D[-1], capital=1e6, cost_per_side=0.001)
    rt = res.round_trips[res.round_trips["symbol"] == "AAA"].iloc[0]
    # entry: 990,000 notional -> 990 cost -> 9,900 units at 100
    # exit at 121: notional = 9,900*121 = 1,197,900 -> cost 1,197.90
    # pnl = (1,197,900 - 1,197.90) - (990,000 + 990) = 205,712.10
    assert rt["pnl"] == pytest.approx(205_712.10, abs=1e-6)
    assert rt["status"] == "CLOSED"
    assert rt["hold_days"] == 2                    # 2021-01-04 -> 2021-01-06
    stats = M.trade_stats(res.round_trips)
    assert stats["n_trades"] == 2                  # AAA closed, BBB open at end
    assert stats["n_wins"] >= 1


def test_trade_stats_formulas():
    rt = pd.DataFrame({"pnl": [100.0, 200.0, -50.0, -150.0], "hold_days": [10, 20, 30, 40]})
    s = M.trade_stats(rt)
    assert s["accuracy"] == pytest.approx(50.0)
    assert s["avg_win"] == pytest.approx(150.0)
    assert s["avg_loss"] == pytest.approx(100.0)
    assert s["gain_to_loss"] == pytest.approx(1.5)


# ======================================================================================
# 6. METRICS — competition definitions
# ======================================================================================
def test_sharpe_definitions_differ_by_sqrt252():
    idx = pd.bdate_range("2021-01-01", periods=500)
    rng = np.random.default_rng(0)
    nav = pd.Series(1e7 * np.cumprod(1 + rng.normal(0.0005, 0.01, 500)), index=idx)
    assert M.sharpe_theirs(nav) == pytest.approx(
        M.sharpe_standard(nav) * np.sqrt(252), rel=1e-12)


def test_max_drawdown_hand_case():
    nav = pd.Series([100, 120, 90, 95, 150], index=pd.bdate_range("2021-01-01", periods=5))
    assert M.max_drawdown(nav) == pytest.approx(-0.25)      # 120 -> 90


def test_annualised_return_hand_case():
    idx = pd.to_datetime(["2021-01-01", "2026-01-01"])      # 5 calendar years (1826 days)
    nav = pd.Series([100.0, 200.0], index=idx)
    yrs = (idx[-1] - idx[0]).days / 365.25
    assert M.annualised_return(nav) == pytest.approx(2 ** (1 / yrs) - 1, rel=1e-12)


def test_total_net_pnl_is_final_minus_capital():
    idx = pd.bdate_range("2021-01-01", periods=10)
    nav = pd.Series(np.linspace(1e7, 1.5e7, 10), index=idx)
    rep = M.full_report(nav, capital=1e7, label="x")
    assert rep["total_net_pnl"] == pytest.approx(5e6)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
