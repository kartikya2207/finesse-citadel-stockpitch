import sys, json, warnings; sys.path.insert(0,'.'); warnings.filterwarnings('ignore')
import pandas as pd
from src import data_fetch as D
syms = json.load(open('data/raw/master_symbols_v2.json'))
print('fetching', len(syms), 'symbols', flush=True)
px = D.download_prices(syms, end='2026-09-02', cache_key='v2')
print('prices', px.shape, px['symbol'].nunique(), flush=True)
sh = D.download_shares(syms, end='2026-09-02', cache_key='v2')
print('shares', sh.shape, sh['symbol'].nunique(), flush=True)
