import sys, warnings, json; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
from src import pipeline as P, metrics as M, seal
from src.strategies import Strategy
from src.config import CAPITAL, COST_PER_SIDE, PRIMARY_BENCHMARK, OUT

AW={'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'efficiency_6m':1.0}
PARAMS=dict(score_spec=AW, cadence='quarterly', weighting='invvol', cap=0.20, floor=0.05,
            n_hold=10, screens={'vol_1y':['drop_top_pctile',0.20]},
            sleeves=['NIFTY100','MIDCAP100','SMALLCAP100'], score_method='zscore_sum',
            cost_per_side=COST_PER_SIDE, capital=CAPITAL)
RAT=("Selected on rebalance-phase STABILITY, not on the maximum of a phase distribution. "
     "Across 6 semiannual and 3 quarterly rebalance phases COMP_allweather has PNL std "
     "Rs24-30L vs Rs67-84L for every momentum rival, the shallowest max drawdown (-27.2%), "
     "and four economically distinct legs each defensible in one sentence. Rivals scoring "
     "higher (mom_12m Rs427L) do so only at their best phase and collapse ~50% at their worst.")
pay = seal.freeze_design('COMP_allweather_quarterly_invvol_n10_volq20', PARAMS, RAT)
print('FROZEN AT (UTC):', pay['frozen_at_utc']); print('UNSEAL TIMESTAMP == freeze timestamp (one-way door)')

w=P.load_world()
S=Strategy(name='FROZEN_allweather',score_spec=AW,family='composite',cadence='quarterly',
           weighting='invvol',n_hold=10,cap=0.20,floor=0.05,
           screens={'vol_1y':('drop_top_pctile',0.20)})
IS=P.run_strategy(S,start='2021-01-01',end='2025-12-31',log_selection=True)
r=IS['result']; rep=IS['report']
print('\n=== IN-SAMPLE 2021-2025 ===')
for k in ['total_net_pnl','final_value','total_return_pct','annualised_return_pct','max_drawdown_pct',
          'sharpe_competition','sharpe_standard','ann_vol_pct','daily_vol_pct','n_trades','accuracy',
          'gain_to_loss','n_legs','total_costs','annual_turnover_oneway_pct','mdd_peak_date','mdd_trough_date']:
    print(f'  {k:32s} {rep.get(k)}')

# concentration
rt=r.round_trips.copy().sort_values('pnl',ascending=False)
tot=rt['pnl'].sum(); top5=rt['pnl'].head(5).sum()
print(f'\nCONCENTRATION: top-5 round trips = {top5/tot*100:.1f}% of gross round-trip PNL (sum={tot:,.0f})')
print(rt.head(6).to_string())

# STRESS TEST (seal now broken)
ST=P.run_strategy(S,start='2026-01-01',end='2026-06-30',allow_oos=True)
sr=ST['report']
print('\n=== STRESS TEST 2026-01-01..2026-06-30 ===')
for k in ['total_net_pnl','final_value','total_return_pct','annualised_return_pct','max_drawdown_pct',
          'sharpe_standard','n_trades','accuracy','gain_to_loss','total_costs']:
    print(f'  {k:32s} {sr.get(k)}')

# CONTINUOUS: carry frozen portfolio from 2021 through Jun-2026 (true live path)
FULL=P.run_strategy(S,start='2021-01-01',end='2026-06-30',allow_oos=True,log_selection=True)
fr=FULL['report']; print('\n=== CONTINUOUS 2021-01..2026-06 final value:', f"{fr['final_value']:,.0f}", 'CAGR', round(fr['annualised_return_pct'],2))

# benchmark
cmp_is=P.compare_to_benchmark(r.nav)
print('\n=== BENCHMARK (Nifty 500 TRI) in-sample ===')
b=cmp_is['bench_report']
for k in ['final_value','total_return_pct','annualised_return_pct','max_drawdown_pct','sharpe_competition','sharpe_standard']:
    print(f'  {k:32s} {b.get(k)}')
print('  beta',round(cmp_is['beta'],3),'alpha_ann%',round(cmp_is['alpha_ann_pct'],2),'IR',round(cmp_is['information_ratio'],2))

import pickle
OUTD=OUT
pickle.dump({'IS':{'nav':r.nav,'weights':r.weights,'trades':r.trades,'rt':r.round_trips,
                   'positions':r.positions,'cash':r.cash,'report':rep,'sel':IS['selection_log'],'tw':IS['weights']},
             'ST':{'nav':ST['result'].nav,'trades':ST['result'].trades,'rt':ST['result'].round_trips,
                   'weights':ST['result'].weights,'report':sr,'tw':ST['weights']},
             'FULL':{'nav':FULL['result'].nav,'report':fr,'trades':FULL['result'].trades,
                     'weights':FULL['result'].weights,'sel':FULL['selection_log']},
             'bench_is':cmp_is,'frozen':pay},
            open(OUTD/'frozen_run.pkl','wb'))
print('\nsaved outputs/frozen_run.pkl')
