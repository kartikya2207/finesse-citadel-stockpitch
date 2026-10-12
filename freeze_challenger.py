"""Freeze the challenger to a NEW file, then run 2026 as a REPORT-ONLY diagnostic."""
from search_lib import *
import json, hashlib, pickle
from datetime import datetime, timezone
from src import metrics as M
from src.config import CAPITAL, ROOT
w=world()
SPEC={'rar_mom_avg_6_12_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0}
PARAMS=dict(score_spec=SPEC,cadence='quarterly',weighting='invvol',cap=0.20,floor=0.05,
            n_hold=10,screens={'vol_1y':['drop_top_pctile',0.20]},
            sleeves=['NIFTY100','MIDCAP100','SMALLCAP100'],score_method='rank',
            cost_per_side=0.001,capital=CAPITAL)
h={}
for rel in ['src/config.py','src/signals.py','src/backtest.py','src/strategies.py','src/search_guard.py']:
    h[rel]=hashlib.sha256(open(ROOT/rel,'rb').read()).hexdigest()
pay={'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
 'strategy_name':'CHALLENGER_rarAvg_up12_dd1y_quarterly_invvol_n10_volq20',
 'parameters':PARAMS,'source_sha256':h,'in_sample_window':['2021-01-01','2025-12-31'],
 'selection_basis':'2021-2025 ONLY. Search ran on a world physically truncated to 2025-12-31 '
   '(src/search_guard.py). No 2026 observation entered any signal, screen, ranking, parameter '
   'choice or tie-break.',
 'CONTAMINATION_DISCLOSURE':
   'SELECTED AFTER THE 2026 STRESS WINDOW WAS ALREADY UNSEALED (incumbent unsealed '
   '2026-09-02T17:27:58Z). Although 2026 data was physically absent from the search world and '
   'played no part in selection, the SELECTOR had already seen the incumbent 2026 outcome. This '
   "candidate's 2026 stress number is therefore WEAKER EVIDENCE than the incumbent's was: the "
   'incumbent was frozen before anyone had seen 2026, this one was not. The 2026 figures below '
   'are a report-only diagnostic and were computed AFTER this file was written.',
 'trials_at_selection': E.n_trials()}
open('FROZEN_CHALLENGER.json','w',encoding='utf-8').write(json.dumps(pay,indent=2))
print('WROTE FROZEN_CHALLENGER.json at',pay['frozen_at_utc'],'| trials:',pay['trials_at_selection'])

S=mk('CHALLENGER',SPEC)
IS=P.run_strategy(S,start='2021-01-01',end='2025-12-31',allow_oos=True,log_selection=True)
rep=IS['report']; nav=IS['result'].nav
print('\n=== IN-SAMPLE (selection basis) ===')
brief_cagr=((nav.iloc[-1]/CAPITAL)**(1/5)-1)*100
for k in ['total_net_pnl','final_value','max_drawdown_pct','sharpe_competition','sharpe_standard',
          'n_trades','n_legs','accuracy','gain_to_loss','total_costs','annual_turnover_oneway_pct']:
    print(f'  {k:30s} {rep[k]}')
print(f"  {'CAGR (brief defn ^(1/5))':30s} {brief_cagr:.4f}")

# ---- 2026 REPORT-ONLY. Uses the FULL world, deliberately rebuilt AFTER freezing. ----
import src.pipeline as PP
PP._WORLD=None
wfull=PP.load_world(force=True)
print('\n[report-only] full world restored to', wfull.trading_days.max().date())
ST=PP.run_strategy(S,start='2026-01-01',end='2026-06-30',allow_oos=True)
sr=ST['report']
print('\n=== 2026 STRESS (REPORT-ONLY DIAGNOSTIC, NOT USED IN SELECTION) ===')
for k in ['total_return_pct','total_net_pnl','max_drawdown_pct','n_trades','accuracy','gain_to_loss','total_costs']:
    print(f'  {k:30s} {sr[k]}')
bn=PP.benchmark_nav('NIFTY500','2026-01-01','2026-06-30')
print(f"  {'Nifty500 TRI same window %':30s} {M.total_return(bn)*100:.4f}")
cmp_is=PP.compare_to_benchmark(IS['result'].nav)
pickle.dump({'IS':{'nav':nav,'weights':IS['result'].weights,'trades':IS['result'].trades,
                   'rt':IS['result'].round_trips,'positions':IS['result'].positions,
                   'report':rep,'tw':IS['weights'],'brief_cagr':brief_cagr},
             'ST':{'nav':ST['result'].nav,'trades':ST['result'].trades,'rt':ST['result'].round_trips,
                   'weights':ST['result'].weights,'report':sr,'tw':ST['weights']},
             'bench_is':cmp_is,'frozen':pay},open('outputs/challenger_run.pkl','wb'))
print('\nsaved outputs/challenger_run.pkl')
