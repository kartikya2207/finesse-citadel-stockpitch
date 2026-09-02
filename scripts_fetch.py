import sys, time
sys.path.insert(0, '.')
from src import data_fetch as D
t0 = time.time()
syms = D.build_master_symbols()
print(f"symbols={len(syms)}", flush=True)
bm = D.download_benchmarks(end="2026-09-02")
print("benchmarks done", bm.shape, flush=True)
px = D.download_prices(syms, end="2026-09-02")
print(f"prices done {px.shape} in {time.time()-t0:.0f}s", flush=True)
sh = D.download_shares(syms, end="2026-09-02")
print(f"shares done {sh.shape} in {time.time()-t0:.0f}s", flush=True)
