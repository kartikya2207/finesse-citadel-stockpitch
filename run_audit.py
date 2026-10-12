from audit_gate import *
import pickle
CANDS=[
 ('CHALLENGER_rarAvg_up12_dd1y',
  {'rar_mom_avg_6_12_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0}),
 ('CHALLENGER_rar12s_up12_dd1y',
  {'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0}),
 ('CHALLENGER_sub3resid',
  {'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'resid_mom_12m':1.0}),
 ('INCUMBENT_allweather',
  {'rar_mom_12m_skip1':1.0,'pct_up_months_12m':1.0,'max_dd_1y':1.0,'efficiency_6m':1.0}),
]
out=[]
for i,(nm,sp) in enumerate(CANDS):
    out.append(full_audit(nm,sp,run_tests=(i==0)))
pickle.dump(out,open('outputs/audit_results.pkl','wb'))
print('\n\n================ SHORTLIST SUMMARY ================')
print(f"{'candidate':32s} {'PNL(L)':>8s} {'CAGR':>7s} {'MDD':>8s} {'Sh':>6s} {'ph_sd6':>7s} {'ph_sd3':>7s}  eligible")
for o in out:
    print(f"{o['name'][:32]:32s} {o['pnl']/1e5:8.1f} {o['cagr']:7.2f} {o['mdd']:8.2f} "
          f"{o['sharpe_std']:6.2f} {o['phase_sd6']:7.1f} {o['phase_sd3']:7.1f}  {o['eligible']}")
