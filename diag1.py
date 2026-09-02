import sys, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
from src import pipeline as P, metrics as M
from src.strategies import Strategy, rebalance_dates
from src.pit_universe import universe_asof
from src.backtest import run_backtest
w=P.load_world(); adj=w.panels['adjclose']

# ---------- CONTROL 1: equal-weight the ENTIRE PIT universe (what the universe itself did)
dates = rebalance_dates(w.trading_days,'2021-01-01','2025-12-31','quarterly')
tw={}
for d in dates:
    u=[s for s in universe_asof(w.membership,d) if s in adj.columns and pd.notna(adj.loc[:d,s].iloc[-1])]
    tw[d]=pd.Series(1.0/len(u), index=u)
r_uni=run_backtest(adj,tw,'2021-01-01','2025-12-31',max_positions=10**6)
print(f"UNIVERSE EW (300 names, quarterly):  final=Rs{r_uni.nav.iloc[-1]/1e7:.3f}cr  CAGR={M.annualised_return(r_uni.nav)*100:.2f}%  MDD={M.max_drawdown(r_uni.nav)*100:.1f}%")

# ---------- CONTROL 2: random 10, 200 seeds -> the monkey distribution
from src.strategies import equal_weight_universe_weights
pnls=[]
for seed in range(200):
    twr=equal_weight_universe_weights(w.membership,dates,w.features,n=10,seed=seed)
    rr=run_backtest(adj,twr,'2021-01-01','2025-12-31',cost_per_side=0.001,max_positions=10)
    pnls.append(rr.nav.iloc[-1]-1e7)
p=np.array(pnls)/1e5
print(f"\nRANDOM-10 CONTROL (200 seeds), PNL in lakh:")
print(f"  mean={p.mean():.1f}  median={np.median(p):.1f}  sd={p.std():.1f}")
for q in [5,25,50,75,90,95,99]: print(f"  p{q:02d}={np.percentile(p,q):7.1f}")
print(f"  max={p.max():.1f}")
for tgt,name in [(293.0,'MOM_mom_9m'),(272.2,'MOM_mom_12m'),(151.6,'B0 brief baseline')]:
    print(f"  percentile of {name} ({tgt}L): {(p<tgt).mean()*100:.1f}%")
