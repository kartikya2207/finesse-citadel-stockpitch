import sys, warnings, pickle, json; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
from src import pipeline as P, metrics as M, pit_universe as U
from src.config import CAPITAL, OUT, PRIMARY_BENCHMARK
D=pickle.load(open(OUT/'frozen_run.pkl','rb')); w=P.load_world()

# --- equal-weight PIT universe index (the honest internal bar) ---
ac=w.panels['adjclose']; ret=ac.pct_change()
def ew_nav(start,end):
    idx=ac.loc[start:end].index; vals=[]
    memb_dates=pd.date_range(start,end,freq='MS')
    cur=None; navv=CAPITAL; out={}
    for d in idx:
        mm=[m for m in memb_dates if m<=d]
        key=mm[-1] if mm else pd.Timestamp(start)
        names=[s for s in U.universe_asof(w.membership,key) if s in ret.columns]
        r=ret.loc[d,names].dropna()
        navv=navv*(1+ (r.mean() if len(r) else 0.0))
        out[d]=navv
    return pd.Series(out)
ew_is=ew_nav('2021-01-01','2025-12-31'); ew_st=ew_nav('2026-01-01','2026-06-30')
ew_is_rep=M.full_report(ew_is,capital=CAPITAL,label='EW PIT universe')
ew_st_rep=M.full_report(ew_st,capital=CAPITAL,label='EW PIT universe (stress)')
print('EW universe IS CAGR', round(ew_is_rep['annualised_return_pct'],2), 'final', f"{ew_is_rep['final_value']:,.0f}")
print('EW universe ST ret%', round(ew_st_rep['total_return_pct'],2))

# --- benchmark stress ---
bn_st=P.benchmark_nav(PRIMARY_BENCHMARK,'2026-01-01','2026-06-30')
bst=M.full_report(bn_st,capital=CAPITAL,label='Nifty500 TRI stress')
print('Nifty500 TRI stress ret%', round(bst['total_return_pct'],2), 'MDD', round(bst['max_drawdown_pct'],2))
bn_is=D['bench_is']['bench_nav']

# --- calendar-year table ---
def yr(nav):
    o=[]
    for y in sorted(set(nav.index.year)):
        s=nav[nav.index.year==y]
        o.append({'year':y,'ret_pct':(s.iloc[-1]/s.iloc[0]-1)*100,'mdd_pct':M.max_drawdown(s)*100})
    return pd.DataFrame(o).set_index('year')
full=D['FULL']['nav']
bn_full=P.benchmark_nav(PRIMARY_BENCHMARK,full.index[0],full.index[-1])
ew_full=pd.concat([ew_is,ew_st*(ew_is.iloc[-1]/CAPITAL)])
# ffill THEN bfill: 2021-01-01 is a real NSE session present in the stock panel but
# absent from the downloaded index series, so a plain ffill leaves a leading NaN.
ytab=yr(full).join(yr(bn_full.reindex(full.index).ffill().bfill()),rsuffix='_bm').join(yr(ew_full.reindex(full.index).ffill().bfill()),rsuffix='_ew')
print('\n',ytab.round(2).to_string())

pickle.dump({'ew_is':ew_is,'ew_st':ew_st,'ew_is_rep':ew_is_rep,'ew_st_rep':ew_st_rep,
             'bn_st':bn_st,'bst':bst,'bn_is':bn_is,'bn_full':bn_full,'ew_full':ew_full,'ytab':ytab},
            open(OUT/'exhibits.pkl','wb'))
print('\nsaved exhibits.pkl')
