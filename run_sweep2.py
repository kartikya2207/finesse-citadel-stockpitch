import sys, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, time
from src import experiments as E, pipeline as P
from src.strategies import Strategy

w = P.load_world(); print('world ok', w.snapshot_hash, flush=True)
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 40)
VOL = dict(E.VOL_SCREEN)
rows=[]; t0=time.time()

def go(name, spec, cadence, weighting, n, screens, family, cap=0.20, floor=0.05, tag='sweep2'):
    s = Strategy(name=name, score_spec=spec, family=family, cadence=cadence,
                 weighting=weighting, n_hold=n,
                 cap=(cap if weighting=='invvol' else None),
                 floor=(floor if weighting=='invvol' else None), screens=dict(screens))
    o = E.evaluate(s, tag=tag)
    if o:
        r=o['report']; r['_cad']=cadence; r['_wt']=weighting; r['_n']=n; r['_scr']=('volq20' if screens else 'none')
        rows.append(r)
    return o

CORE = {'mom_9m': {'mom_9m':1.0}, 'mom_12m': {'mom_12m':1.0}, 'rar_mom_12m': {'rar_mom_12m':1.0}}

# ---- STEP 1: cadence x weighting on top 3 signals (n=10, vol screen on)
print('\n### STEP 1: cadence x weighting', flush=True)
for sig, spec in CORE.items():
    for cad in ['quarterly','semiannual','annual']:
        for wt in ['invvol','equal']:
            go(f'S1|{sig}|{cad}|{wt}|n10', spec, cad, wt, 10, VOL, 'momentum')
print(f'  {len(rows)} done {time.time()-t0:.0f}s', flush=True)

# ---- STEP 2: n=8 vs 10 and screen on/off for best 2 of step 1
df1 = pd.DataFrame(rows)
top2 = df1.sort_values('total_net_pnl', ascending=False).head(2)
print('\n### STEP 2: n and screen on best-2', flush=True)
step2=[]
for _, r in top2.iterrows():
    sig = r['label'].split('|')[1]; spec=CORE[sig]
    for n in [8,10]:
        for scr in [VOL, {}]:
            nm=f"S2|{sig}|{r['_cad']}|{r['_wt']}|n{n}|{'volq20' if scr else 'noscr'}"
            step2.append(nm)
            go(nm, spec, r['_cad'], r['_wt'], n, scr, 'momentum')

# ---- STEP 3: COMP_allweather blended with rar_mom_12m
print('\n### STEP 3: allweather blends', flush=True)
AW = {'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'efficiency_6m':1.0}
best_cad = top2.iloc[0]['_cad']; best_wt = top2.iloc[0]['_wt']
for lam,tagn in [(1.0,'blend50'),(2.0,'blend67')]:
    spec = {k:v for k,v in AW.items()}
    spec['rar_mom_12m'] = spec.get('rar_mom_12m',0)+lam*4   # lam*4 => weight vs 4 AW legs
    go(f'S3|AWx{tagn}|{best_cad}|{best_wt}|n10', spec, best_cad, best_wt, 10, VOL, 'composite')
# also plain allweather at the best cadence/weighting for reference
go(f'S3|AWpure|{best_cad}|{best_wt}|n10', AW, best_cad, best_wt, 10, VOL, 'composite')

df = pd.DataFrame(rows)
cols=['label','total_net_pnl','annualised_return_pct','max_drawdown_pct','sharpe_competition',
      'sharpe_standard','n_trades','accuracy','gain_to_loss','annual_turnover_oneway_pct','total_costs']
df=df[cols].sort_values('total_net_pnl',ascending=False)
df['total_net_pnl']=(df['total_net_pnl']/1e5).round(1); df['total_costs']=(df['total_costs']/1e5).round(2)
print('\n==== SWEEP 2 RESULTS (PNL in lakh) ====')
print(df.round(2).to_string(index=False))
df.to_csv('outputs/sweep2.csv', index=False)
print(f'\ntrials total: {E.n_trials()}  elapsed {time.time()-t0:.0f}s')
