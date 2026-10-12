"""PASS B: phase-stability gate on Pass A survivors.

Criterion (b) - phase sd <= Rs 30 lakh across six rebalance phases - is the binding
constraint that killed our best momentum variants last time. Applying it EARLY is cheaper
than applying it late: a high-PNL candidate with Rs 70L dispersion is not a better
strategy, it is a luckier one, and it can be discarded before any further work.
"""
from search_lib import *
import pickle, time

w = world(); t0 = time.time()
rows = pickle.load(open('outputs/searchA_rows.pkl', 'rb'))
print(f'Pass A produced {len(rows)} candidates')

beat = [r for r in rows if r['total_net_pnl'] > INCUMBENT['pnl']]
beat.sort(key=lambda r: -r['total_net_pnl'])
print(f'{len(beat)} beat the incumbent on PNL (criterion a)')

# criterion (c): drawdown no worse than -32%
elig = [r for r in beat if r['max_drawdown_pct'] >= -32.0]
print(f'{len(elig)} of those also satisfy MDD >= -32% (criterion c)')
for r in elig[:30]:
    print(f"   {r['label'][:40]:42s} PNL={r['total_net_pnl']/1e5:7.1f}L "
          f"CAGR={r['annualised_return_pct']:5.2f} MDD={r['max_drawdown_pct']:6.2f} "
          f"Sh={r['sharpe_standard']:4.2f}")

TOPN = min(18, len(elig))
print(f'\n=== PHASE TESTING the top {TOPN} (6 phases each) ===', flush=True)
res = []
for i, r in enumerate(elig[:TOPN]):
    S = mk(r['label'], r['_spec'], family='phasecand')
    d, sd = phase_test(S, tag='searchB_phase')
    if d is None:
        continue
    res.append({'label': r['label'], 'spec': r['_spec'], 'pnl_L': r['total_net_pnl'] / 1e5,
                'mdd': r['max_drawdown_pct'], 'cagr': r['annualised_return_pct'],
                'sharpe_std': r['sharpe_standard'],
                'phase_sd': sd, 'phase_min': d['pnl_L'].min(), 'phase_max': d['pnl_L'].max(),
                'phase_mean': d['pnl_L'].mean()})
    print(f"  [{i+1}/{TOPN}] {r['label'][:38]:40s} phase_sd={sd:6.1f}L "
          f"min={d['pnl_L'].min():6.1f} max={d['pnl_L'].max():6.1f} "
          f"{'PASS(b)' if sd <= 30 else 'FAIL(b)'}  {time.time()-t0:.0f}s", flush=True)

df = pd.DataFrame(res).sort_values('phase_sd')
print('\n==== PASS B: phase dispersion (criterion b, threshold <= 30L) ====')
print(f"INCUMBENT phase_sd = {INCUMBENT['phase_sd_lakh']}L, PNL = {INCUMBENT['pnl']/1e5:.1f}L")
if not df.empty:
    print(df[['label', 'pnl_L', 'cagr', 'mdd', 'sharpe_std', 'phase_sd',
              'phase_min', 'phase_max']].round(2).to_string(index=False))
    surv = df[df['phase_sd'] <= 30.0]
    print(f'\n>>> {len(surv)} candidate(s) clear BOTH (a) PNL and (b) phase sd <= 30L')
    if len(surv):
        print(surv[['label', 'pnl_L', 'mdd', 'phase_sd']].round(2).to_string(index=False))
    df.to_csv('outputs/searchB_phase.csv', index=False)
    pickle.dump(res, open('outputs/searchB_res.pkl', 'wb'))
else:
    print('no candidates reached the phase test')
print(f'\ntrials total: {E.n_trials()}   elapsed {time.time()-t0:.0f}s')
