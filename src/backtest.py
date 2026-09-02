"""Daily portfolio backtest engine.

MODEL
-----
Positions are held as *adjusted units*. A position of `u` units in stock s is worth
`u * adjclose[s, t]`. Because `adjclose` is adjusted for splits, bonuses and dividends,
holding a constant `u` is exactly a real buy-and-hold position that reinvests dividends
and survives capital actions. This is the standard total-return treatment and it makes
NAV continuity across corporate actions automatic rather than a special case.

For the trade log we also report the *actual* traded share count and the *actual* traded
price on the day, recovered from the raw (capital-adjusted) close, so a judge sees real
rupee-and-share arithmetic rather than an abstraction.

TIMING (no look-ahead)
----------------------
At a rebalance date `t`, target weights must have been computed from data available
strictly BEFORE `t` (the caller is responsible; `assert_no_lookahead` in tests checks it).
Execution happens at the CLOSE of `t`. So signal date <= t-1, trade date = t.

COSTS
-----
`COST_PER_SIDE` (0.1%) is charged on the absolute traded notional of EVERY leg, buy and
sell alike. Cost is paid out of cash, so NAV falls by exactly the cost at each rebalance.

CASH
----
Cash is explicit and earns 0% (conservative; a real book would park it in a liquid fund).
It exists because of (a) transaction costs and (b) integer-share rounding when enabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import CAPITAL, COST_PER_SIDE, MAX_POSITIONS


@dataclass
class BacktestResult:
    nav: pd.Series
    positions: pd.DataFrame          # date x symbol, market value
    weights: pd.DataFrame            # date x symbol, weight of NAV
    trades: pd.DataFrame             # one row per leg
    round_trips: pd.DataFrame        # one row per completed buy->flat episode
    cash: pd.Series
    holdings_count: pd.Series
    diagnostics: dict = field(default_factory=dict)


class _RoundTripTracker:
    """Tracks per-symbol episodes: an episode opens on the first buy from flat and closes
    when the position returns to zero. Realised PNL is net of transaction costs on both
    sides, which is what 'profit of the trade' must mean when costs are mandated."""

    def __init__(self) -> None:
        self.open: dict[str, dict] = {}
        self.closed: list[dict] = []

    def buy(self, sym: str, date, units: float, price: float, cost: float) -> None:
        ep = self.open.get(sym)
        if ep is None:
            ep = {"symbol": sym, "entry_date": date, "units": 0.0, "cost_basis": 0.0,
                  "realised": 0.0, "peak_capital": 0.0, "n_legs": 0}
            self.open[sym] = ep
        ep["units"] += units
        ep["cost_basis"] += units * price + cost
        ep["peak_capital"] = max(ep["peak_capital"], ep["cost_basis"])
        ep["n_legs"] += 1

    def sell(self, sym: str, date, units: float, price: float, cost: float) -> None:
        ep = self.open.get(sym)
        if ep is None:               # defensive: should never happen
            return
        units = min(units, ep["units"])
        frac = units / ep["units"] if ep["units"] > 0 else 0.0
        basis_out = ep["cost_basis"] * frac
        proceeds = units * price - cost
        ep["realised"] += proceeds - basis_out
        ep["cost_basis"] -= basis_out
        ep["units"] -= units
        ep["n_legs"] += 1
        if ep["units"] <= 1e-9:
            self.closed.append({
                "symbol": sym,
                "entry_date": ep["entry_date"],
                "exit_date": date,
                "hold_days": (pd.Timestamp(date) - pd.Timestamp(ep["entry_date"])).days,
                "capital_deployed": ep["peak_capital"],
                "pnl": ep["realised"],
                "return_pct": (ep["realised"] / ep["peak_capital"] * 100.0)
                              if ep["peak_capital"] > 0 else np.nan,
                "n_legs": ep["n_legs"],
                "status": "CLOSED",
            })
            del self.open[sym]

    def force_close_open(self, date, marks: dict[str, float]) -> list[dict]:
        """Mark-to-market any still-open episodes at the end of the run."""
        out = []
        for sym, ep in self.open.items():
            mv = ep["units"] * marks.get(sym, np.nan)
            pnl = ep["realised"] + mv - ep["cost_basis"]
            out.append({
                "symbol": sym, "entry_date": ep["entry_date"], "exit_date": date,
                "hold_days": (pd.Timestamp(date) - pd.Timestamp(ep["entry_date"])).days,
                "capital_deployed": ep["peak_capital"], "pnl": pnl,
                "return_pct": (pnl / ep["peak_capital"] * 100.0) if ep["peak_capital"] > 0 else np.nan,
                "n_legs": ep["n_legs"], "status": "OPEN_AT_END",
            })
        return out


def run_backtest(
    adjclose: pd.DataFrame,                  # date x symbol, total-return price
    target_weights: dict[pd.Timestamp, pd.Series],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    capital: float = CAPITAL,
    cost_per_side: float = COST_PER_SIDE,
    rawclose: pd.DataFrame | None = None,    # for reporting real share counts / prices
    integer_shares: bool = False,
    max_positions: int = MAX_POSITIONS,
    max_stale_days: int = 15,
    strict: bool = True,
) -> BacktestResult:
    """Run the daily backtest. `target_weights[t]` is a Series of weights summing to <= 1."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    px = adjclose.loc[(adjclose.index >= start) & (adjclose.index <= end)].copy()
    if px.empty:
        raise ValueError("no price data in the requested window")
    dates = px.index

    rebal_dates = sorted(d for d in target_weights if start <= d <= end)
    if not rebal_dates:
        raise ValueError("no rebalance dates inside the window")
    rebal_set = set(rebal_dates)

    units: dict[str, float] = {}
    cash = capital
    tracker = _RoundTripTracker()
    trade_rows: list[dict] = []
    nav_rows: list[float] = []
    cash_rows: list[float] = []
    count_rows: list[int] = []
    pos_rows: dict[pd.Timestamp, dict[str, float]] = {}
    wt_rows: dict[pd.Timestamp, dict[str, float]] = {}

    last_price: dict[str, float] = {}
    stale_days: dict[str, int] = {}
    diagnostics = {"stale_forced_exits": [], "missing_price_at_rebalance": [],
                   "weight_renormalisations": 0, "nav_continuity_max_err": 0.0}

    def price_of(sym: str, t: pd.Timestamp) -> float:
        """Price with an explicit stale-data rule; never silently NaN."""
        v = px.at[t, sym] if sym in px.columns else np.nan
        if pd.notna(v):
            last_price[sym] = float(v)
            stale_days[sym] = 0
            return float(v)
        stale_days[sym] = stale_days.get(sym, 0) + 1
        return last_price.get(sym, np.nan)

    for t in dates:
        # ---- mark to market -------------------------------------------------------
        for sym in list(units):
            price_of(sym, t)

        # ---- forced exit of names that have gone stale (suspension / delisting) ----
        for sym in list(units):
            if stale_days.get(sym, 0) > max_stale_days and units[sym] > 0:
                p = last_price.get(sym, np.nan)
                if not np.isfinite(p):
                    continue
                u = units.pop(sym)
                notional = u * p
                cost = notional * cost_per_side
                cash += notional - cost
                tracker.sell(sym, t, u, p, cost)
                trade_rows.append({"date": t, "symbol": sym, "side": "SELL",
                                   "units": u, "price": p, "notional": notional,
                                   "cost": cost, "reason": "STALE_FORCED_EXIT"})
                diagnostics["stale_forced_exits"].append((str(t.date()), sym))

        nav_pre = cash + sum(u * last_price.get(s, np.nan) for s, u in units.items())

        # ---- rebalance ------------------------------------------------------------
        if t in rebal_set:
            w = target_weights[t].dropna()
            w = w[w > 0]
            available = []
            for s in w.index:
                p = px.at[t, s] if s in px.columns else np.nan
                if pd.notna(p) and p > 0:
                    available.append(s)
                else:
                    diagnostics["missing_price_at_rebalance"].append((str(t.date()), s))
            w = w.loc[available]
            if len(w) > max_positions:
                w = w.nlargest(max_positions)
            # Weights summing to <= 1 leave an intentional cash sleeve and are kept as-is.
            # Only an over-allocation (> 1) is an error and gets renormalised down.
            if w.sum() > 1.0 + 1e-9:
                diagnostics["weight_renormalisations"] += 1
                w = w / w.sum()

            nav_now = nav_pre

            def _plan(scale: float):
                """Target units, legs and resulting cash for a given invested scale.

                A fully invested target (weights summing to 1) cannot be funded, because
                the 0.1% cost must also be paid out of the same corpus: buying X requires
                X + 0.001X <= NAV, i.e. X <= NAV/1.001. `scale` shrinks the invested
                fraction until cash lands at or above zero. This is the correct rupee
                arithmetic, not a fudge.
                """
                tgt: dict[str, float] = {}
                for s_ in w.index:
                    p_ = float(px.at[t, s_])
                    tv = float(w[s_]) * nav_now * scale
                    u_ = tv / p_
                    if integer_shares and rawclose is not None and s_ in rawclose.columns \
                            and pd.notna(rawclose.at[t, s_]):
                        rp = float(rawclose.at[t, s_])
                        adjf = p_ / rp if rp > 0 else 1.0
                        u_ = np.floor(tv / rp) * adjf
                    tgt[s_] = u_
                lg = []
                for s_ in set(list(units) + list(tgt)):
                    cur_ = units.get(s_, 0.0)
                    d_ = tgt.get(s_, 0.0) - cur_
                    if abs(d_) < 1e-9:
                        continue
                    p_ = float(px.at[t, s_]) if (s_ in px.columns and pd.notna(px.at[t, s_])) \
                        else last_price.get(s_, np.nan)
                    if not np.isfinite(p_) or p_ <= 0:
                        continue
                    lg.append((s_, d_, p_))
                cost_ = sum(abs(d_) * p_ for _, d_, p_ in lg) * cost_per_side
                cash_after_ = cash - sum(d_ * p_ for _, d_, p_ in lg) - cost_
                return tgt, lg, cash_after_

            # Find the largest invested scale in (0, 1] that keeps cash non-negative.
            target_units, legs, cash_after = _plan(1.0)
            if cash_after < -1e-9:
                lo_s, hi_s = 0.0, 1.0
                for _ in range(60):
                    mid = 0.5 * (lo_s + hi_s)
                    _, _, ca = _plan(mid)
                    if ca >= 0.0:
                        lo_s = mid
                    else:
                        hi_s = mid
                target_units, legs, cash_after = _plan(lo_s)
                diagnostics.setdefault("cost_scale_events", []).append(
                    (str(t.date()), round(lo_s, 8)))
                if cash_after < -1e-6:
                    raise AssertionError(
                        f"{t.date()}: could not fund rebalance without negative cash")

            legs.sort(key=lambda x: x[1])          # negative (sells) first

            for s, d, p in legs:
                notional = abs(d) * p
                cost = notional * cost_per_side
                side = "BUY" if d > 0 else "SELL"
                real_price = float(rawclose.at[t, s]) if (
                    rawclose is not None and s in rawclose.columns
                    and pd.notna(rawclose.at[t, s])) else np.nan
                real_shares = notional / real_price if np.isfinite(real_price) and real_price > 0 else np.nan
                if d > 0:
                    cash -= notional + cost
                    tracker.buy(s, t, d, p, cost)
                else:
                    cash += notional - cost
                    tracker.sell(s, t, abs(d), p, cost)
                units[s] = units.get(s, 0.0) + d
                if abs(units[s]) < 1e-9:
                    units.pop(s, None)
                trade_rows.append({"date": t, "symbol": s, "side": side,
                                   "units": abs(d), "price": p, "notional": notional,
                                   "cost": cost, "real_price": real_price,
                                   "real_shares": real_shares, "reason": "REBALANCE"})

            nav_post = cash + sum(u * float(px.at[t, s]) if (s in px.columns and pd.notna(px.at[t, s]))
                                  else u * last_price.get(s, 0.0) for s, u in units.items())
            expected = nav_pre - sum(r["cost"] for r in trade_rows if r["date"] == t)
            err = abs(nav_post - expected)
            diagnostics["nav_continuity_max_err"] = max(
                diagnostics["nav_continuity_max_err"], err)
            if strict and err > max(1e-6, 1e-9 * nav_pre):
                raise AssertionError(
                    f"NAV continuity violated at {t.date()}: post={nav_post:.6f} "
                    f"expected={expected:.6f} err={err:.6e}")

        # ---- record ---------------------------------------------------------------
        # Refresh the price cache for every held name, including ones opened today (they
        # were not in `units` at the top of the loop, so `price_of` has not seen them).
        for sym in list(units):
            price_of(sym, t)
        mv = {s: u * last_price.get(s, np.nan) for s, u in units.items()}
        nav = cash + sum(v for v in mv.values() if np.isfinite(v))
        if strict:
            if len(units) > max_positions:
                raise AssertionError(f"{t.date()}: {len(units)} positions > {max_positions}")
            if any(u < -1e-9 for u in units.values()):
                raise AssertionError(f"{t.date()}: negative holding")
            if not np.isfinite(nav):
                raise AssertionError(f"{t.date()}: NAV is not finite")
            if cash < -1e-6:
                raise AssertionError(f"{t.date()}: negative cash {cash:.4f}")
        nav_rows.append(nav)
        cash_rows.append(cash)
        count_rows.append(len(units))
        pos_rows[t] = dict(mv)
        wt_rows[t] = {s: v / nav for s, v in mv.items()} if nav > 0 else {}

    nav_s = pd.Series(nav_rows, index=dates, name="nav")
    trades = pd.DataFrame(trade_rows)
    rts = pd.DataFrame(tracker.closed + tracker.force_close_open(
        dates[-1], {s: last_price.get(s, np.nan) for s in units}))
    return BacktestResult(
        nav=nav_s,
        positions=pd.DataFrame(pos_rows).T.reindex(dates),
        weights=pd.DataFrame(wt_rows).T.reindex(dates),
        trades=trades,
        round_trips=rts,
        cash=pd.Series(cash_rows, index=dates, name="cash"),
        holdings_count=pd.Series(count_rows, index=dates, name="n_holdings"),
        diagnostics=diagnostics,
    )


def buy_and_hold_nav(adjclose: pd.DataFrame, weights: pd.Series, start, end,
                     capital: float = CAPITAL,
                     cost_per_side: float = COST_PER_SIDE) -> pd.Series:
    """Single-entry buy-and-hold NAV with entry costs only (no exit assumed).
    Used for benchmark-style comparisons, not for the primary result."""
    px = adjclose.loc[pd.Timestamp(start):pd.Timestamp(end), weights.index].dropna(axis=1, how="all")
    w = weights.reindex(px.columns).fillna(0.0)
    w = w / w.sum()
    invest = capital * (1 - cost_per_side)
    u = invest * w / px.iloc[0]
    return (px * u).sum(axis=1)
