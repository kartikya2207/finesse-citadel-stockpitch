import sys, json, warnings
sys.path.insert(0,'.')
warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

syms = json.load(open('data/raw/master_symbols.json'))

def grab(sym):
    out = []
    try:
        t = yf.Ticker(sym + '.NS')
        fin = {}
        for name, attr in [('is_a','income_stmt'), ('bs_a','balance_sheet'), ('cf_a','cashflow'),
                           ('is_q','quarterly_income_stmt'), ('bs_q','quarterly_balance_sheet'),
                           ('cf_q','quarterly_cashflow')]:
            try:
                df = getattr(t, attr)
                if df is not None and not df.empty:
                    fin[name] = df
            except Exception:
                pass
        for key, df in fin.items():
            freq = 'A' if key.endswith('_a') else 'Q'
            stmt = key[:2]
            d = df.T
            d.index = pd.to_datetime(d.index)
            for period_end, row in d.iterrows():
                for item, val in row.items():
                    if pd.notna(val):
                        out.append((sym, stmt, freq, period_end, str(item), float(val)))
    except Exception:
        pass
    return out

rows = []
done = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(grab, s): s for s in syms}
    for f in as_completed(futs):
        rows.extend(f.result()); done += 1
        if done % 100 == 0:
            print(f'{done}/{len(syms)} rows={len(rows)}', flush=True)

df = pd.DataFrame(rows, columns=['symbol','stmt','freq','period_end','item','value'])
df.to_parquet('data/cache/fundamentals_raw.parquet', index=False)
print('DONE', df.shape, df['symbol'].nunique(), 'symbols')
print(df.groupby('freq')['period_end'].agg(['min','max']))
