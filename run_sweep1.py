import sys, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, time
from src import experiments as E, pipeline as P
from src.strategies import Strategy

w = P.load_world(); print('world ok', w.snapshot_hash, flush=True)
pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)

cands = (E.momentum_family() + E.lowrisk_family() + E.trend_family()
         + E.other_factor_family() + E.composite_family())
# apply the brief's default config to every single-signal candidate for a fair first pass
for s in cands:
    s.screens = dict(E.VOL_SCREEN); s.cadence='quarterly'; s.weighting='invvol'; s.cap=0.20; s.floor=0.05

# controls
controls = [Strategy(name='CTRL_random10', score_spec={'log_turnover':0.0}, family='control')]

t0=time.time(); rows=[]
for i,s in enumerate(cands):
    o = E.evaluate(s, tag='sweep1_signals')
    if o: rows.append(o['report'])
    if (i+1)%10==0: print(f'{i+1}/{len(cands)}  {time.time()-t0:.0f}s', flush=True)

df = pd.DataFrame(rows)
cols=['label','family','total_net_pnl','annualised_return_pct','max_drawdown_pct',
      'sharpe_competition','sharpe_standard','n_trades','accuracy','gain_to_loss',
      'annual_turnover_oneway_pct','total_costs']
df=df[cols].sort_values('total_net_pnl',ascending=False)
df['total_net_pnl']=(df['total_net_pnl']/1e5).round(1)   # lakh
df['total_costs']=(df['total_costs']/1e5).round(2)
print('\n==== SWEEP 1: single signals, quarterly / inv-vol 20-5 cap / vol-q20 screen ====')
print(df.round(2).to_string(index=False))
df.to_csv('outputs/sweep1_signals.csv', index=False)
print(f'\ntrials logged: {E.n_trials()}  elapsed {time.time()-t0:.0f}s')
