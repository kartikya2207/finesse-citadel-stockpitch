"""PASS A: broad single-feature and composite ranker sweep at the incumbent's config."""
from search_lib import *
import time
w = world(); t0=time.time()
rows=[]; F=sorted(w.features.keys())
SKIP={'ret','mcap','turnover_60d','vol_3m','vol_6m','dvol_1y','idio_vol','vol_1y','beta','log_mcap'}

# --- A1: every feature as a single ranker (both signs where ambiguous) ---
for f in F:
    if f in SKIP: continue
    r=ev(mk(f'A1|{f}', {f:1.0}, family='single'), 'searchA1')
    if r: rows.append(r)
print(f'A1 single features: {len(rows)} evaluated  {time.time()-t0:.0f}s', flush=True)
print(table(rows,12).to_string(index=False))

# --- A2: composites. Systematic 2/3/4/5-leg blends of the strongest primitives ---
LEGS={
 'rar12s':'rar_mom_12m_skip1','rar12':'rar_mom_12m','rar6':'rar_mom_6m','rarAvg':'rar_mom_avg_6_12_skip1',
 'mom12':'mom_12m','mom9':'mom_9m','mom6s':'mom_6m_skip1','momAvg':'mom_avg_6_12_skip1',
 'residR':'rar_resid_mom_12m','resid':'resid_mom_12m',
 'up12':'pct_up_months_12m','up6d':'pct_up_days_6m','dd1y':'max_dd_1y','ddnow':'dd_from_1y_high',
 'eff6':'efficiency_6m','ma200':'px_over_ma200','ma50':'px_over_ma50','x52':'prox_52w_high',
 'lowvol':'lowvol','lowbeta':'lowbeta','size':'size','rev1m':'reversal_1m','liq':'log_turnover',
}
import itertools
QUAL=['up12','dd1y','eff6','up6d','ddnow','lowvol','ma200','x52']
MOM =['rar12s','rar12','rarAvg','mom12','mom9','momAvg','residR','resid','rar6','mom6s']
specs={}
# momentum core x one quality leg
for m in MOM:
    for q in QUAL:
        specs[f'A2|{m}+{q}']={LEGS[m]:1.0, LEGS[q]:1.0}
# momentum core x two quality legs
for m in ['rar12s','rar12','rarAvg','mom12','residR']:
    for q1,q2 in itertools.combinations(QUAL,2):
        specs[f'A2|{m}+{q1}+{q2}']={LEGS[m]:1.0,LEGS[q1]:1.0,LEGS[q2]:1.0}
# incumbent-shaped 4-leg with each leg substituted
base=['rar12s','up12','dd1y','eff6']
for i,slot in enumerate(base):
    for alt in MOM+QUAL:
        if alt==slot: continue
        legs=list(base); legs[i]=alt
        if len(set(legs))<4: continue
        specs[f'A2|sub{i}:{alt}']={LEGS[x]:1.0 for x in legs}
print(f'A2 composites queued: {len(specs)}', flush=True)
for i,(nm,sp) in enumerate(specs.items()):
    r=ev(mk(nm,sp,family='composite'),'searchA2')
    if r: rows.append(r)
    if (i+1)%80==0: print(f'  {i+1}/{len(specs)}  {time.time()-t0:.0f}s',flush=True)

df=table(rows,30)
print('\n==== PASS A TOP 30 (incumbent config: quarterly/invvol20-5/n10/volq20/rank) ====')
print(f"INCUMBENT: PNL={INCUMBENT['pnl']/1e5:.1f}L CAGR={INCUMBENT['cagr']} MDD={INCUMBENT['mdd']}")
print(df.to_string(index=False))
df.to_csv('outputs/searchA.csv',index=False)
import pickle; pickle.dump([{k:v for k,v in r.items() if k!='_strategy'} | {'_spec':r['_strategy'].score_spec} for r in rows], open('outputs/searchA_rows.pkl','wb'))
print(f'\ntrials total now: {E.n_trials()}   elapsed {time.time()-t0:.0f}s')
