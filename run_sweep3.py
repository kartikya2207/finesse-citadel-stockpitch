import sys, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, time
from src import experiments as E, pipeline as P
from src.strategies import Strategy
w=P.load_world(); pd.set_option('display.width',300)
VOL=dict(E.VOL_SCREEN)
AW={'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'efficiency_6m':1.0}
AWB={**AW,'rar_mom_12m':4.0}
CANDS={'mom_12m':{'mom_12m':1.0},'rar_mom_12m':{'rar_mom_12m':1.0},
       'AWblend':AWB,'AWpure':AW,'mom_9m':{'mom_9m':1.0}}
rows=[]
for nm,spec in CANDS.items():
    for sh in [0,1,2,3,4,5]:
        s=Strategy(name=f'PH|{nm}|semiannual@{sh}',score_spec=spec,family='robustness',
                   cadence=f'semiannual@{sh}' if sh else 'semiannual',
                   weighting='invvol',n_hold=10,cap=0.20,floor=0.05,screens=VOL)
        o=E.evaluate(s,tag='sweep3_phase')
        if o:
            r=o['report']; rows.append({'cand':nm,'shift':sh,'pnl_L':r['total_net_pnl']/1e5,
              'cagr':r['annualised_return_pct'],'mdd':r['max_drawdown_pct'],
              'sh_std':r['sharpe_standard'],'acc':r['accuracy'],'g2l':r['gain_to_loss']})
d=pd.DataFrame(rows)
print('\n==== PHASE-SHIFT ROBUSTNESS (semiannual, 6 phases) ====')
print(d.round(2).to_string(index=False))
g=d.groupby('cand')['pnl_L'].agg(['mean','min','max','std']).round(1).sort_values('mean',ascending=False)
g['spread']=(g['max']-g['min']).round(1)
print('\n---- stability summary (PNL lakh across 6 phases) ----')
print(g.to_string())
d.to_csv('outputs/sweep3_phase.csv',index=False)
print('trials',E.n_trials())
