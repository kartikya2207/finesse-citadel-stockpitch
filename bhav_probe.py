import sys, io, os, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import requests, pandas as pd, numpy as np, time
from concurrent.futures import ThreadPoolExecutor, as_completed
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
   'Accept':'*/*','Referer':'https://www.nseindia.com/'}
os.makedirs('data/bhav', exist_ok=True)

def fetch(d):
    ds=d.strftime('%d%m%Y'); p=f'data/bhav/{ds}.csv'
    if os.path.exists(p) and os.path.getsize(p)>1000:
        return pd.read_csv(p)
    for base in ['https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_',
                 'https://archives.nseindia.com/products/content/sec_bhavdata_full_']:
        try:
            r=requests.get(base+ds+'.csv',headers=H,timeout=60)
            if r.status_code==200 and len(r.content)>5000 and b'SYMBOL' in r.content[:400]:
                open(p,'wb').write(r.content); return pd.read_csv(io.BytesIO(r.content))
        except Exception: pass
    return None

def month_universe(year, month, ndays=20):
    days=pd.bdate_range(f'{year}-{month:02d}-01', periods=ndays+8)
    frames=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for df in ex.map(fetch, list(days)):
            if df is not None: frames.append(df)
    if not frames: return None
    b=pd.concat(frames, ignore_index=True)
    b.columns=[c.strip() for c in b.columns]
    b['SYMBOL']=b['SYMBOL'].astype(str).str.strip().str.upper()
    b['SERIES']=b['SERIES'].astype(str).str.strip()
    b=b[b['SERIES']=='EQ'].copy()
    for c in ['CLOSE_PRICE','TURNOVER_LACS','TTL_TRD_QNTY','DELIV_QTY']:
        if c in b.columns: b[c]=pd.to_numeric(b[c], errors='coerce')
    g=b.groupby('SYMBOL').agg(med_turnover_lacs=('TURNOVER_LACS','median'),
                              close=('CLOSE_PRICE','last'), ndays=('CLOSE_PRICE','size'))
    return g.sort_values('med_turnover_lacs', ascending=False)

px=pd.read_parquet('data/cache/prices_2026-09-02.parquet')
have=set(px['symbol'].unique())
print(f'yfinance panel symbols: {len(have)}')
for (y,m) in [(2021,1),(2022,1),(2023,1),(2024,1),(2025,1),(2026,1)]:
    g=month_universe(y,m)
    if g is None: print(y,m,'FAILED'); continue
    for topn in [350, 500]:
        top=set(g.index[:topn])
        miss=top-have
        if topn==350:
            print(f'{y}-{m:02d}: NSE EQ symbols traded={len(g)}  top{topn} by turnover: missing from panel = {len(miss)} ({len(miss)/topn*100:.1f}%)')
            print(f'    examples missing: {sorted(list(miss))[:18]}')
        else:
            print(f'          top{topn}: missing = {len(miss)} ({len(miss)/topn*100:.1f}%)')
