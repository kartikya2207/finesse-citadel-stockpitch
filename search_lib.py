"""Shared harness for the post-unseal search. NEW CODE PATH - mutates nothing existing."""
import sys, warnings, json
sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd

from src import search_guard as G
from src import experiments as E, pipeline as P
from src.strategies import Strategy
from src.config import CAPITAL

INCUMBENT = dict(pnl=27392323.214909784, cagr=30.2332, mdd=-27.1571,
                 sharpe_comp=26.2776, sharpe_std=1.6553, phase_sd_lakh=24.1)
VOL20 = {'vol_1y': ('drop_top_pctile', 0.20)}
AW = {'rar_mom_12m_skip1': 1.0, 'pct_up_months_12m': 1.0, 'max_dd_1y': 1.0, 'efficiency_6m': 1.0}

_W = None
def world():
    global _W
    if _W is None:
        _W = G.build_search_world(verbose=True)
        G.validate_guard_is_a_noop(verbose=True)
    return _W


def mk(name, spec, cadence='quarterly', weighting='invvol', n=10, screens=None,
       cap=0.20, floor=0.05, method='rank', sleeves=('NIFTY100','MIDCAP100','SMALLCAP100'),
       family='search', max_per_sector=None):
    return Strategy(name=name, score_spec=spec, family=family, cadence=cadence,
                    weighting=weighting, n_hold=n,
                    cap=(cap if weighting == 'invvol' else None),
                    floor=(floor if weighting == 'invvol' else None),
                    screens=dict(VOL20 if screens is None else screens),
                    score_method=method, sleeves=tuple(sleeves),
                    max_per_sector=max_per_sector)


def ev(S, tag):
    """Evaluate on the truncated world. Returns the report dict or None."""
    G.assert_no_2026(world(), f'ev({S.name})')
    o = E.evaluate(S, tag=tag, start='2021-01-01', end='2025-12-31')
    if not o:
        return None
    r = dict(o['report']); r['_strategy'] = S
    return r


def audit_line(r):
    """One-line audit emitted after every candidate."""
    S = r['_strategy']
    return (f"[audit] {r['label'][:34]:36s} PNL={r['total_net_pnl']/1e5:7.1f}L "
            f"CAGR={r['annualised_return_pct']:5.2f} MDD={r['max_drawdown_pct']:6.2f} "
            f"Sh={r['sharpe_standard']:4.2f} trips={r['n_trades']:3d} legs={r['n_legs']:3d} "
            f"| n<=10:{S.n_hold<=10} PIT:yes cost:0.1%/leg win:21-25 "
            f"| {'TRIPWIRE' if (r['annualised_return_pct']>35 or r['sharpe_standard']>2.5) else 'ok'}")


def phase_test(S, tag='phase', shifts=(0,1,2,3,4,5), cadence_base='semiannual'):
    """Six-phase dispersion. Criterion (b): sd <= Rs 30 lakh."""
    out = []
    for sh in shifts:
        cad = cadence_base if sh == 0 else f'{cadence_base}@{sh}'
        S2 = Strategy(name=f'{S.name}|PH{sh}', score_spec=S.score_spec, family='phase',
                      cadence=cad, weighting=S.weighting, n_hold=S.n_hold,
                      cap=S.cap, floor=S.floor, screens=dict(S.screens),
                      score_method=S.score_method, sleeves=S.sleeves,
                      max_per_sector=S.max_per_sector)
        r = ev(S2, tag)
        if r:
            out.append({'shift': sh, 'pnl_L': r['total_net_pnl']/1e5,
                        'cagr': r['annualised_return_pct'], 'mdd': r['max_drawdown_pct']})
    d = pd.DataFrame(out)
    if d.empty:
        return None, np.nan
    return d, float(d['pnl_L'].std())


def table(rows, n=25, sort='total_net_pnl'):
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith('_')} for r in rows])
    if df.empty:
        return df
    cols = ['label','total_net_pnl','annualised_return_pct','max_drawdown_pct',
            'sharpe_standard','sharpe_competition','n_trades','accuracy','gain_to_loss',
            'annual_turnover_oneway_pct']
    cols = [c for c in cols if c in df.columns]
    df = df[cols].sort_values(sort, ascending=False).head(n)
    df['total_net_pnl'] = (df['total_net_pnl']/1e5).round(1)
    return df.round(2)
