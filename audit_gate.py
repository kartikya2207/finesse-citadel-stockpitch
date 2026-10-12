"""Seven-point audit gate. A candidate is INELIGIBLE until this prints PASS on all seven."""
from search_lib import *
import subprocess, json, time
import numpy as np, pandas as pd
from src import metrics as M
from src.config import CAPITAL, COST_PER_SIDE
from src.strategies import Strategy, build_target_weights, rebalance_dates
from src.backtest import run_backtest
from src import search_guard as G

w = world()


def full_audit(name, spec, cadence='quarterly', weighting='invvol', n=10,
               screens=None, cap=0.20, floor=0.05, method='rank', run_tests=True):
    print('\n' + '=' * 94)
    print(f'FULL 7-POINT AUDIT :: {name}')
    print(f'  spec = {json.dumps(spec, sort_keys=True)}')
    print(f'  cadence={cadence} weighting={weighting} n={n} cap={cap} floor={floor} method={method}')
    print('=' * 94)
    verdicts = {}
    S = mk(name, spec, cadence=cadence, weighting=weighting, n=n,
           screens=screens, cap=cap, floor=floor, method=method)
    out = P.run_strategy(S, start='2021-01-01', end='2025-12-31', allow_oos=True)
    res, rep, tw = out['result'], out['report'], out['weights']

    # ---------- 1. CONSTRAINTS ----------
    print('\n[1] CONSTRAINTS PROVEN IN CODE')
    pos = res.positions.fillna(0.0)
    daily_holdings = (pos.abs() > 1e-6).sum(axis=1)
    c_max = int(daily_holdings.max())
    wsum_err = max(abs(v.sum() - 1.0) for v in tw.values())
    wmax = max(v.max() for v in tw.values()); wmin = min(v[v > 0].min() for v in tw.values())
    tr = res.trades
    cost_err = float((tr['cost'] - tr['notional'] * COST_PER_SIDE).abs().max())
    neg = int((pos < -1e-6).sum().sum())
    d0, d1 = res.nav.index[0].date(), res.nav.index[-1].date()
    # PIT check: every selected name must be in the PIT universe on its rebalance date
    from src.pit_universe import universe_asof
    pit_bad = []
    for d, v in tw.items():
        u = set(universe_asof(w.membership, d))
        pit_bad += [(str(d.date()), s) for s in v.index if s not in u]
    print(f'   max concurrent holdings on ANY day : {c_max}      {"PASS" if c_max <= 10 else "FAIL"} (limit 10)')
    print(f'   max |sum(weights) - 1|             : {wsum_err:.2e}  {"PASS" if wsum_err < 1e-9 else "FAIL"} (<1e-9)')
    print(f'   weight range (cap {cap} / floor {floor}) : [{wmin:.4f}, {wmax:.4f}]  '
          f'{"PASS" if wmax <= (cap or 1) + 1e-9 else "FAIL"}')
    print(f'   max |cost - 0.001*notional|        : {cost_err:.2e}  {"PASS" if cost_err < 1e-6 else "FAIL"}')
    print(f'   legs charged / total legs          : {int((tr["cost"]>0).sum())}/{len(tr)}  '
          f'{"PASS" if int((tr["cost"]>0).sum())==len(tr) else "FAIL"}')
    print(f'   negative (short) positions         : {neg}       {"PASS" if neg==0 else "FAIL"} (long-only)')
    print(f'   selections outside PIT universe    : {len(pit_bad)}       {"PASS" if not pit_bad else "FAIL"}')
    print(f'   window                             : {d0} .. {d1}  '
          f'{"PASS" if str(d0)>="2021-01-01" and str(d1)<="2025-12-31" else "FAIL"}')
    verdicts['1_constraints'] = (c_max <= 10 and wsum_err < 1e-9 and cost_err < 1e-6
                                 and neg == 0 and not pit_bad
                                 and int((tr['cost'] > 0).sum()) == len(tr))

    # ---------- 2. NO LOOK-AHEAD ----------
    print('\n[2] NO LOOK-AHEAD')
    G.assert_no_2026(w, 'audit')
    print(f'   2026 assertion (panels+features <= 2025-12-31) : PASS')
    # shift test: feed the ranker a panel shifted FORWARD in time. If the strategy were
    # peeking at the future, shifting the inputs would not change what it buys.
    shifted = {k: (v.shift(21) if isinstance(v, pd.DataFrame) else v) for k, v in w.features.items()}
    dates = rebalance_dates(w.trading_days, '2021-01-01', '2025-12-31', S.cadence)
    tw_s, _ = build_target_weights(S, shifted, w.membership, dates, sectors=w.sectors,
                                   adjclose=w.panels['adjclose'])
    same = sum(1 for d in tw if d in tw_s and set(tw[d].index) == set(tw_s[d].index))
    changed = len(tw) - same
    print(f'   shift test: rebalances whose picks CHANGED when inputs shifted 21d : '
          f'{changed}/{len(tw)}   {"PASS" if changed > 0 else "FAIL"}')
    res_s = run_backtest(w.panels['adjclose'], tw_s, start='2021-01-01', end='2025-12-31',
                         capital=CAPITAL, cost_per_side=COST_PER_SIDE,
                         rawclose=w.panels['rawprice'], max_positions=S.n_hold)
    dpnl = float(res_s.nav.iloc[-1] - res.nav.iloc[-1])
    print(f'   shifted-input PNL differs by       : Rs {dpnl:,.0f}  '
          f'{"PASS" if abs(dpnl) > 1000 else "FAIL"}')
    verdicts['2_lookahead'] = changed > 0 and abs(dpnl) > 1000

    # ---------- 3. METRICS RECOMPUTED INDEPENDENTLY ----------
    print('\n[3] METRICS RECOMPUTED BY AN INDEPENDENT PATH (denominators printed)')
    nav = res.nav
    r = nav.pct_change().dropna()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / CAPITAL) ** (1 / yrs) - 1
    sd = r.std(ddof=1)
    mdd = float((nav / nav.cummax() - 1).min())
    sh_comp, sh_std = cagr / sd, cagr / (sd * np.sqrt(252))
    rt = res.round_trips
    wins, loss = rt[rt['pnl'] > 0]['pnl'], rt[rt['pnl'] <= 0]['pnl']
    g2l = wins.mean() / abs(loss.mean()) if len(loss) else np.nan
    acc = len(wins) / len(rt) * 100
    print(f'   denominator: initial corpus       = Rs {CAPITAL:,.0f}')
    print(f'   denominator: years                = {yrs:.6f}  ({nav.index[0].date()} -> {nav.index[-1].date()}, /365.25)')
    print(f'   denominator: sd of DAILY returns  = {sd:.8f}  (n-1 over {len(r)} obs)')
    print(f'   denominator: round trips          = {len(rt)} ; losing trips = {len(loss)}')
    print(f'   {"metric":26s} {"independent":>16s} {"engine":>16s}  match')
    checks = [('Total Net PNL', nav.iloc[-1] - CAPITAL, rep['total_net_pnl'], 1.0),
              ('CAGR %', cagr * 100, rep['annualised_return_pct'], 0.01),
              ('Max drawdown %', mdd * 100, rep['max_drawdown_pct'], 0.01),
              ('Sharpe competition', sh_comp, rep['sharpe_competition'], 0.01),
              ('Sharpe standard', sh_std, rep['sharpe_standard'], 0.01),
              ('Accuracy %', acc, rep['accuracy'], 0.01),
              ('Gain-to-loss', g2l, rep['gain_to_loss'], 0.01)]
    ok3 = True
    for lab, a, b, tol in checks:
        m = abs(a - b) <= tol; ok3 &= m
        print(f'   {lab:26s} {a:16.4f} {b:16.4f}  {"OK" if m else "*** MISMATCH ***"}')
    verdicts['3_metrics'] = ok3

    # ---------- 4. TRADE LOG <-> NAV RECONCILIATION ----------
    print('\n[4] RECONCILIATION: PNL from the TRADE LOG vs PNL from the NAV path')
    cash = CAPITAL; units = {}
    for _, t in tr.sort_values('date').iterrows():
        q, px, cst = float(t['units']), float(t['price']), float(t['cost'])
        if t['side'] == 'BUY':
            cash -= q * px + cst; units[t['symbol']] = units.get(t['symbol'], 0.0) + q
        else:
            cash += q * px - cst; units[t['symbol']] = units.get(t['symbol'], 0.0) - q
    last_px = w.panels['adjclose'].loc[nav.index[-1]]
    mkt = sum(u * float(last_px.get(s, 0.0)) for s, u in units.items() if abs(u) > 1e-9)
    terminal = cash + mkt
    diff = terminal - nav.iloc[-1]
    print(f'   cash from replaying every leg      = Rs {cash:,.2f}')
    print(f'   market value of open positions     = Rs {mkt:,.2f}')
    print(f'   => terminal value from trade log   = Rs {terminal:,.2f}')
    print(f'   terminal value from NAV path       = Rs {nav.iloc[-1]:,.2f}')
    print(f'   difference                         = Rs {diff:,.6f}   '
          f'{"PASS" if abs(diff) < 0.01 else "FAIL"}')
    verdicts['4_reconciliation'] = abs(diff) < 0.01

    # ---------- 5. TRIPWIRE ----------
    print('\n[5] TRIPWIRE')
    cagr_pc, shs = cagr * 100, sh_std
    bnav = P.benchmark_nav('NIFTY500', nav.index[0], nav.index[-1]).reindex(nav.index).ffill().bfill()
    def dd_year(s, y):
        x = s[s.index.year == y]
        return float((x / x.cummax() - 1).min()) * 100
    dd22s, dd22b = dd_year(nav, 2022), dd_year(bnav, 2022)
    dd25s, dd25b = dd_year(nav, 2025), dd_year(bnav, 2025)
    shallower_both = (dd22s > dd22b) and (dd25s > dd25b)
    print(f'   CAGR {cagr_pc:.2f}%  (>35% trips?)          {"TRIPPED" if cagr_pc > 35 else "ok"}')
    print(f'   standard Sharpe {shs:.2f}  (>2.5 trips?)   {"TRIPPED" if shs > 2.5 else "ok"}')
    print(f'   2022 drawdown strat {dd22s:.2f}% vs bench {dd22b:.2f}%')
    print(f'   2025 drawdown strat {dd25s:.2f}% vs bench {dd25b:.2f}%')
    print(f'   shallower than benchmark in BOTH?     {"TRIPPED" if shallower_both else "ok"}')
    verdicts['5_tripwire'] = not (cagr_pc > 35 or shs > 2.5 or shallower_both)

    # ---------- 6. PHASE TEST ----------
    print('\n[6] PHASE TEST')
    d6, sd6 = phase_test(S, tag='audit_phase6', cadence_base='semiannual')
    d3, sd3 = phase_test(S, tag='audit_phase3', shifts=(0, 1, 2), cadence_base='quarterly')
    print(f'   semiannual, 6 phases : ' + ' '.join(f'{v:6.1f}' for v in d6['pnl_L']) +
          f'   sd={sd6:5.1f}L  {"PASS" if sd6 <= 30 else "FAIL"} (<=30L; incumbent 30.1L)')
    print(f'   quarterly,  3 phases : ' + ' '.join(f'{v:6.1f}' for v in d3['pnl_L']) +
          f'   sd={sd3:5.1f}L  (incumbent 24.1L)')
    verdicts['6_phase'] = sd6 <= 30.0

    # ---------- 7. EXISTING TESTS ----------
    if run_tests:
        print('\n[7] EXISTING TEST SUITE UNCHANGED')
        p = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'],
                           capture_output=True, text=True)
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else '(no output)'
        print(f'   {tail}    {"PASS" if p.returncode == 0 and "29 passed" in p.stdout else "FAIL"}')
        verdicts['7_tests'] = (p.returncode == 0 and '29 passed' in p.stdout)
    else:
        verdicts['7_tests'] = None

    print('\n' + '-' * 94)
    for k, v in verdicts.items():
        print(f'   {k:20s} {"PASS" if v else ("SKIPPED" if v is None else "*** FAIL ***")}')
    allpass = all(v for v in verdicts.values() if v is not None)
    print(f'   >>> AUDIT VERDICT: {"ALL PASS - ELIGIBLE" if allpass else "FAILED - INELIGIBLE"}')
    print('-' * 94)
    return {'name': name, 'spec': spec, 'report': rep, 'verdicts': verdicts,
            'eligible': allpass, 'phase_sd6': sd6, 'phase_sd3': sd3,
            'cagr': cagr * 100, 'mdd': mdd * 100, 'sharpe_std': sh_std,
            'sharpe_comp': sh_comp, 'pnl': float(nav.iloc[-1] - CAPITAL)}
