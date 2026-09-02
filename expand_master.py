import sys, io, os, json, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import requests, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
   'Accept':'*/*','Referer':'https://www.nseindia.com/'}
os.makedirs('data/bhav', exist_ok=True)

def fetch(d):
    ds=d.strftime('%d%m%Y'); p=f'data/bhav/{ds}.csv'
    if os.path.exists(p) and os.path.getsize(p)>1000:
        try: return pd.read_csv(p)
        except Exception: pass
    for base in ['https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_',
                 'https://archives.nseindia.com/products/content/sec_bhavdata_full_']:
        try:
            r=requests.get(base+ds+'.csv',headers=H,timeout=60)
            if r.status_code==200 and len(r.content)>5000 and b'SYMBOL' in r.content[:400]:
                open(p,'wb').write(r.content); return pd.read_csv(io.BytesIO(r.content))
        except Exception: pass
    return None

# ETF / non-equity name patterns (NSE files ETFs under series EQ)
ETF_PAT = ('BEES','GOLD','SILVER','LIQUID','ETF','IETF','NIFTY','SENSEX','BHARATBOND',
           'GSEC','SDL','MOM100','MOM50','MON100','MOM30','ALPHA','LOWVOL','HNGSNGBEES',
           'PSUBNK','CPSE','MAFANG','MASPTOP50','QUAL30','EQUAL50','CONSUMBEES','DIVOPPBEES',
           'AXISGOLD','AXISILVER','AXISBP','ICICILIQ','QUADFUTURE','GROWW','MID150','SMALLCAP',
           'TOP100','TOP50','TOP10','BSLNIFTY','UTINIFTETF','SETFNIF','SETFGOLD','LICNETFN')
def is_etf(s):
    return any(p in s for p in ETF_PAT)

dates=[]
for y in range(2021,2027):
    for m in (1,7):
        if (y,m)==(2026,7): continue
        dates += list(pd.bdate_range(f'{y}-{m:02d}-01', periods=16))
frames=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    for df in ex.map(fetch, dates):
        if df is not None: frames.append(df)
print('bhavcopy files loaded:', len(frames))
b=pd.concat(frames, ignore_index=True)
b.columns=[c.strip() for c in b.columns]
b['SYMBOL']=b['SYMBOL'].astype(str).str.strip().str.upper()
b['SERIES']=b['SERIES'].astype(str).str.strip()
b=b[b['SERIES']=='EQ']
b['DATE1']=pd.to_datetime(b['DATE1'].astype(str).str.strip(), format='%d-%b-%Y', errors='coerce')
b['TURNOVER_LACS']=pd.to_numeric(b['TURNOVER_LACS'], errors='coerce')
b['period']=b['DATE1'].dt.to_period('M')

cand=set()
for per,g in b.groupby('period'):
    gg=g.groupby('SYMBOL')['TURNOVER_LACS'].median().sort_values(ascending=False)
    cand |= set(gg.index[:500])
cand = {s for s in cand if not is_etf(s)}
print('non-ETF candidate symbols across all periods:', len(cand))

master=set(json.load(open('data/raw/master_symbols.json')))
px=pd.read_parquet('data/cache/prices_2026-09-02.parquet')
have=set(px['symbol'].unique())
new = sorted(cand - master)
print('NEW symbols to try (not in master):', len(new))
print(new[:40])
json.dump(sorted(master | cand), open('data/raw/master_symbols_v2.json','w'), indent=0)
json.dump(new, open('data/raw/new_symbols.json','w'), indent=0)
print('master v2 size:', len(master|cand))
