"""Performance metrics.

CRITICAL: the competition defines Sharpe as

    Sharpe = Annualised Return / Standard Deviation of DAILY Returns      (rf = 0)

That is dimensionally inconsistent — an annual numerator over a daily denominator — and
reads about sqrt(252) = 15.87x larger than the textbook figure. We compute it EXACTLY as
specified because that is what we are scored on, and report the standard version alongside,
clearly labelled. See `sharpe_theirs` and `sharpe_standard`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS


# --------------------------------------------------------------------------------------
# Core return statistics
# --------------------------------------------------------------------------------------
def daily_returns(nav: pd.Series) -> pd.Series:
    return nav.pct_change().dropna()


def total_return(nav: pd.Series) -> float:
    return float(nav.iloc[-1] / nav.iloc[0] - 1.0)


def years_calendar(nav: pd.Series) -> float:
    return (nav.index[-1] - nav.index[0]).days / 365.25


def annualised_return(nav: pd.Series) -> float:
    """Geometric average return, calendar-year basis. THEIR definition of 'Annualised Return'."""
    yrs = years_calendar(nav)
    if yrs <= 0:
        return np.nan
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1.0 / yrs) - 1.0)


def annualised_return_252(nav: pd.Series) -> float:
    """Same thing on a 252-trading-day year. Reported as a cross-check; differs by <0.1pp."""
    n = len(nav) - 1
    if n <= 0:
        return np.nan
    return float((nav.iloc[-1] / nav.iloc[0]) ** (TRADING_DAYS / n) - 1.0)


def max_drawdown(nav: pd.Series) -> float:
    """Largest peak-to-trough decline, as a negative fraction."""
    return float((nav / nav.cummax() - 1.0).min())


def drawdown_series(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def max_drawdown_dates(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = drawdown_series(nav)
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    return peak, trough, float(dd.loc[trough])


# --------------------------------------------------------------------------------------
# Sharpe — both definitions
# --------------------------------------------------------------------------------------
def sharpe_theirs(nav: pd.Series) -> float:
    """COMPETITION DEFINITION: Annualised Return / SD(daily returns), rf = 0.
    Denominator is the DAILY standard deviation, NOT annualised."""
    r = daily_returns(nav)
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float(annualised_return(nav) / sd)


def sharpe_standard(nav: pd.Series, rf: float = 0.0) -> float:
    """Textbook: (Annualised Return - rf) / Annualised Volatility, vol = SD(daily) * sqrt(252)."""
    r = daily_returns(nav)
    sd = r.std(ddof=1) * np.sqrt(TRADING_DAYS)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float((annualised_return(nav) - rf) / sd)


def sharpe_arithmetic(nav: pd.Series, rf: float = 0.0) -> float:
    """Arithmetic variant: mean(daily)*252 / (SD(daily)*sqrt(252))."""
    r = daily_returns(nav)
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float((r.mean() * TRADING_DAYS - rf) / (sd * np.sqrt(TRADING_DAYS)))


def annualised_vol(nav: pd.Series) -> float:
    return float(daily_returns(nav).std(ddof=1) * np.sqrt(TRADING_DAYS))


def daily_vol(nav: pd.Series) -> float:
    return float(daily_returns(nav).std(ddof=1))


def sortino(nav: pd.Series, rf: float = 0.0) -> float:
    r = daily_returns(nav)
    downside = r[r < 0].std(ddof=1) * np.sqrt(TRADING_DAYS)
    if downside == 0 or np.isnan(downside):
        return np.nan
    return float((annualised_return(nav) - rf) / downside)


def calmar(nav: pd.Series) -> float:
    mdd = abs(max_drawdown(nav))
    return float(annualised_return(nav) / mdd) if mdd > 0 else np.nan


# --------------------------------------------------------------------------------------
# Trade statistics — THEIR definitions
# --------------------------------------------------------------------------------------
def trade_stats(round_trips: pd.DataFrame) -> dict:
    """Gain-to-Loss and Accuracy per the competition spec.

    Accuracy      = % of trades that were profitable
    Gain-to-Loss  = average profit of winning trades / average loss of losing trades

    A 'trade' here = one completed round trip in a stock (buy -> fully closed).
    Statistical caveat: with fewer than ~30 round trips these numbers have very wide
    confidence intervals and must not be headlined.
    """
    if round_trips is None or len(round_trips) == 0:
        return {"n_trades": 0, "accuracy": np.nan, "gain_to_loss": np.nan,
                "avg_win": np.nan, "avg_loss": np.nan, "n_wins": 0, "n_losses": 0,
                "profit_factor": np.nan, "avg_hold_days": np.nan}
    pnl = round_trips["pnl"].astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    return {
        "n_trades": int(len(pnl)),
        "n_wins": int(len(wins)),
        "n_losses": int(len(losses)),
        "accuracy": float(len(wins) / len(pnl) * 100.0),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "gain_to_loss": float(avg_win / avg_loss) if avg_loss > 0 else np.inf,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else np.inf,
        "avg_hold_days": float(round_trips["hold_days"].mean()),
    }


# --------------------------------------------------------------------------------------
# Full report
# --------------------------------------------------------------------------------------
def full_report(nav: pd.Series, round_trips: pd.DataFrame | None = None,
                trades: pd.DataFrame | None = None, capital: float = 1e7,
                label: str = "") -> dict:
    nav = nav.dropna()
    out = {
        "label": label,
        "start": nav.index[0].date().isoformat(),
        "end": nav.index[-1].date().isoformat(),
        "n_days": int(len(nav)),
        "initial_value": float(nav.iloc[0]),
        "final_value": float(nav.iloc[-1]),
        # PRIMARY RANKING METRIC
        "total_net_pnl": float(nav.iloc[-1] - capital),
        "total_return_pct": total_return(nav) * 100.0,
        "annualised_return_pct": annualised_return(nav) * 100.0,
        "annualised_return_252_pct": annualised_return_252(nav) * 100.0,
        "max_drawdown_pct": max_drawdown(nav) * 100.0,
        "sharpe_competition": sharpe_theirs(nav),
        "sharpe_standard": sharpe_standard(nav),
        "sharpe_arithmetic": sharpe_arithmetic(nav),
        "ann_vol_pct": annualised_vol(nav) * 100.0,
        "daily_vol_pct": daily_vol(nav) * 100.0,
        "sortino": sortino(nav),
        "calmar": calmar(nav),
        "skew": float(daily_returns(nav).skew()),
        "kurtosis": float(daily_returns(nav).kurtosis()),
        "best_day_pct": float(daily_returns(nav).max() * 100),
        "worst_day_pct": float(daily_returns(nav).min() * 100),
        "pct_positive_days": float((daily_returns(nav) > 0).mean() * 100),
    }
    peak, trough, _ = max_drawdown_dates(nav)
    out["mdd_peak_date"] = peak.date().isoformat()
    out["mdd_trough_date"] = trough.date().isoformat()

    if round_trips is not None:
        out.update(trade_stats(round_trips))
    if trades is not None and len(trades):
        out["n_legs"] = int(len(trades))
        out["total_traded_notional"] = float(trades["notional"].sum())
        out["total_costs"] = float(trades["cost"].sum())
        out["costs_pct_of_capital"] = float(trades["cost"].sum() / capital * 100)
        yrs = years_calendar(nav)
        out["annual_turnover_oneway_pct"] = float(
            trades.loc[trades["side"] == "BUY", "notional"].sum() / nav.mean() / yrs * 100)
    return out


def calendar_year_returns(nav: pd.Series) -> pd.Series:
    """Calendar-year total returns from a daily NAV series."""
    yearly = nav.resample("YE").last()
    first = pd.Series([nav.iloc[0]], index=[nav.index[0]])
    joined = pd.concat([first, yearly])
    joined = joined[~joined.index.duplicated(keep="first")]
    out = joined.pct_change().dropna()
    out.index = out.index.year
    return out


def report_frame(reports: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(reports).set_index("label")
