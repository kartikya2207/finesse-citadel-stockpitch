"""Regenerate the git-ignored data caches from scratch.

The repo ships without data/cache (~63 MB) and data/bhav (~73 MB) so it clones in
seconds. This script rebuilds both from public, unauthenticated sources. Needs network.
Expect roughly 10-20 minutes end to end.

    python reproduce_data.py            # full rebuild
    python reproduce_data.py --skip-bhav  # prices/shares/benchmark only (faster)

Afterwards run:  python freeze_and_build.py && python build_exhibits.py && python build_workbook.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

END = "2026-09-02"          # data snapshot date used for the submission


def step(n: int, msg: str) -> None:
    print(f"\n{'=' * 70}\n[{n}] {msg}\n{'=' * 70}", flush=True)


def main() -> int:
    skip_bhav = "--skip-bhav" in sys.argv
    from src import data_fetch as D
    from src.config import CACHE, RAW

    step(1, "NSE index constituent lists + master symbol universe")
    D.fetch_index_lists()
    D.build_master_symbols()
    print("index lists and master_symbols.json written to data/raw/")

    if not skip_bhav:
        step(2, "NSE bhavcopy archive (data/bhav) + expanded master list")
        # expand_master.py downloads the official daily bhavcopies and widens the
        # symbol universe to everything that actually traded in the window.
        rc = subprocess.call([sys.executable, "expand_master.py"])
        if rc != 0:
            print("WARNING: expand_master.py exited non-zero; falling back to the "
                  "committed data/raw/master_symbols_v2.json if present.")
    else:
        step(2, "SKIPPED bhavcopy download (--skip-bhav)")

    step(3, "Prices and shares outstanding (data/cache/*_v2.parquet)")
    v2 = RAW / "master_symbols_v2.json"
    if not v2.exists():
        print(f"FATAL: {v2} missing and could not be rebuilt. Re-run without --skip-bhav.")
        return 1
    syms = json.load(open(v2))
    print(f"fetching {len(syms)} symbols ...", flush=True)
    px = D.download_prices(syms, end=END, cache_key="v2")
    print("prices:", px.shape, px["symbol"].nunique(), "symbols")
    sh = D.download_shares(syms, end=END, cache_key="v2")
    print("shares:", sh.shape, sh["symbol"].nunique(), "symbols")

    step(4, "Benchmark series (Nifty 500 and friends)")
    bench = D.download_benchmarks(end=END)
    print("benchmarks:", bench.shape)

    step(5, "Data-integrity checks against the official bhavcopy")
    from src import pipeline as P
    from src import integrity as I
    from src.config import PRIMARY_BENCHMARK
    w = P.load_world(force=True)
    rep = I.run_all(w.panels, w.bench[PRIMARY_BENCHMARK], write=True)
    print("integrity report written to logs/data_integrity.md")
    print(json.dumps({k: (v if not isinstance(v, dict) else list(v)[:3])
                      for k, v in rep.items()}, default=str, indent=2)[:1200])

    print(f"\n{'=' * 70}\nDONE. Caches rebuilt in data/cache/ and data/bhav/.\n"
          f"Next:  python freeze_and_build.py && python build_exhibits.py "
          f"&& python build_workbook.py\n{'=' * 70}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
