"""Measure the survivorship distortion: identical strategy, two universes.

PIT  = point-in-time reconstructed membership (what we submit on).
TODAY = today's published Nifty 100 / Midcap 100 / Smallcap 100 constituent lists,
        held constant across the whole 2021-2025 backtest (the common shortcut).
Only the universe changes. The strategy, costs, cadence and weighting are identical.
"""
import sys, warnings, json; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
from src import pipeline as P, metrics as M
from src import pit_universe as U
from src.strategies import Strategy, build_target_weights, rebalance_dates
from src.backtest import run_backtest
from src.config import CAPITAL, COST_PER_SIDE, RAW, OUT

w = P.load_world()

# ---- BASELINE strategy: plain 12-month momentum, same plumbing as everything else ----
BASE = dict(score_spec={'mom_12m':1.0}, cadence='quarterly', weighting='invvol',
            n_hold=10, cap=0.20, floor=0.05,
            screens={'vol_1y':('drop_top_pctile',0.20)})

def run_with(membership, label):
    S = Strategy(name=f'SURV_{label}', family='survivorship', **BASE)
    dates = rebalance_dates(w.trading_days, '2021-01-01', '2025-12-31', S.cadence)
    tw,_ = build_target_weights(S, w.features, membership, dates,
                                sectors=w.sectors, adjclose=w.panels['adjclose'])
    res = run_backtest(w.panels['adjclose'], tw, start='2021-01-01', end='2025-12-31',
                       capital=CAPITAL, cost_per_side=COST_PER_SIDE,
                       rawclose=w.panels['rawprice'], max_positions=S.n_hold)
    rep = M.full_report(res.nav, res.round_trips, res.trades, capital=CAPITAL, label=label)
    return rep, tw

# ---- universe 1: point-in-time (what we submit) ----
pit_rep, pit_tw = run_with(w.membership, 'PIT')

# ---- universe 2: today's published constituent lists, constant through time ----
def load_list(fn):
    d = pd.read_csv(RAW/fn)
    return [str(s).strip().upper() for s in d['Symbol']]
today = sorted(set(load_list('ind_nifty100list.csv'))
             | set(load_list('ind_niftymidcap100list.csv'))
             | set(load_list('ind_niftysmallcap100list.csv')))
avail = [s for s in today if s in w.panels['adjclose'].columns]
print(f'today-lists universe: {len(today)} names, {len(avail)} present in the price panel')
static = {k: {'NIFTY100': avail, 'MIDCAP100': [], 'SMALLCAP100': []} for k in w.membership}
tod_rep, tod_tw = run_with(static, 'TODAY')

pit_u = sorted({s for v in pit_tw.values() for s in v.index})
tod_u = sorted({s for v in tod_tw.values() for s in v.index})

print('\n================ SURVIVORSHIP EXHIBIT (baseline 12m-momentum strategy) ================')
rows=[('Final value of Rs 1cr','final_value','%.0f'),('Total Net PNL','total_net_pnl','%.0f'),
      ('CAGR %','annualised_return_pct','%.2f'),('Max drawdown %','max_drawdown_pct','%.2f'),
      ('Sharpe standard','sharpe_standard','%.2f'),('Round trips','n_trades','%.0f')]
print(f"{'metric':26s} {'PIT (honest)':>18s} {'TODAY lists':>18s}")
for lab,k,f in rows:
    print(f'{lab:26s} {f%pit_rep[k]:>18s} {f%tod_rep[k]:>18s}')
infl_pnl = tod_rep['total_net_pnl']/pit_rep['total_net_pnl']-1
infl_cagr = tod_rep['annualised_return_pct']-pit_rep['annualised_return_pct']
print(f"\nPNL INFLATION  : {infl_pnl*100:.1f}%")
print(f"CAGR INFLATION : +{infl_cagr:.2f} percentage points per year")
print(f"distinct names actually held: PIT {len(pit_u)}  vs TODAY {len(tod_u)}")

json.dump({'baseline_strategy':'mom_12m quarterly invvol cap20/floor5 volq20 n10',
           'pit':{k:float(pit_rep[k]) for _,k,_ in rows},
           'today':{k:float(tod_rep[k]) for _,k,_ in rows},
           'pnl_inflation_pct':float(infl_pnl*100),
           'cagr_inflation_pp':float(infl_cagr),
           'today_list_names':len(today),'today_names_in_panel':len(avail)},
          open(OUT/'survivorship_exhibit.json','w'), indent=2)
print('\nwritten outputs/survivorship_exhibit.json')
