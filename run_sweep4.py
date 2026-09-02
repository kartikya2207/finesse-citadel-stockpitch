import sys, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, time
from src import experiments as E, pipeline as P
from src.strategies import Strategy
w=P.load_world(); pd.set_option('display.width',300)
VOL=dict(E.VOL_SCREEN)
AW={'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'efficiency_6m':1.0}
AWB={**AW,'rar_mom_12m':4.0}
rows=[]
def run(nm,spec,cad,wt,n,scr,tag='sweep4'):
    s=Strategy(name=nm,score_spec=spec,family='robustness',cadence=cad,weighting=wt,n_hold=n,
               cap=(0.20 if wt=='invvol' else None),floor=(0.05 if wt=='invvol' else None),screens=dict(scr))
    o=E.evaluate(s,tag=tag)
    if o:
        r=o['report']; rows.append({'cand':nm.split('|')[1],'cad':cad,'wt':wt,'n':n,
          'scr':('vol' if scr else 'none'),'shift':nm.split('@')[-1] if '@' in cad else '0',
          'pnl_L':r['total_net_pnl']/1e5,'cagr':r['annualised_return_pct'],'mdd':r['max_drawdown_pct'],
          'sh_std':r['sharpe_standard'],'sh_comp':r['sharpe_competition'],'acc':r['accuracy'],
          'g2l':r['gain_to_loss'],'trades':r['n_trades'],'turn':r['annual_turnover_oneway_pct']})
    return o
# quarterly phase-stability for AW variants + rar (3 phases covers quarterly fully)
for nm,spec in [('AWpure',AW),('AWblend',AWB),('rar12',{'rar_mom_12m':1.0})]:
    for sh in [0,1,2]:
        cad='quarterly' if sh==0 else f'quarterly@{sh}'
        run(f'Q|{nm}|{cad}',spec,cad,'invvol',10,VOL)
# AWpure config variants at quarterly (equal wt, n=8, no screen)
for wt,n,scr,lab in [('equal',10,VOL,'eq10'),('invvol',8,VOL,'iv8'),('invvol',10,{},'noscr')]:
    run(f'QV|AWpure_{lab}|quarterly',AW,'quarterly',wt,n,scr)
d=pd.DataFrame(rows)
print('\n==== SWEEP 4: quarterly phase stability + AW config variants ====')
print(d.round(2).to_string(index=False))
g=d[d['cad'].str.startswith('quarterly')&(d['wt']=='invvol')&(d['n']==10)&(d['scr']=='vol')].groupby('cand')['pnl_L'].agg(['mean','min','max','std']).round(1)
print('\n--- quarterly phase stability (3 phases) ---'); print(g.to_string())
d.to_csv('outputs/sweep4.csv',index=False); print('trials',E.n_trials())
