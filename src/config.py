"""Global configuration. Single source of truth for every constant in the build.

Every number here that comes from the problem statement is tagged [SPEC].
Every number that is our choice is tagged [ASSUMPTION] and must appear in ASSUMPTIONS.md.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
PIT = DATA / "pit"
OUT = ROOT / "outputs"
LOGS = ROOT / "logs"
for _p in (DATA, RAW, CACHE, PIT, OUT, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Competition constants  [SPEC]
# --------------------------------------------------------------------------------------
CAPITAL = 10_000_000.0                 # [SPEC] INR 1 crore virtual corpus
MAX_POSITIONS = 10                     # [SPEC] maximum 10 stocks
COST_PER_SIDE = 0.001                  # [SPEC] 0.1% per transaction
BACKTEST_START = "2021-01-01"          # [SPEC]
BACKTEST_END = "2025-12-31"            # [SPEC]
STRESS_START = "2026-01-01"            # [SPEC] sealed
STRESS_END = "2026-06-30"              # [SPEC] sealed

# History needed before BACKTEST_START to compute 12m momentum + 1y vol without look-ahead.
HISTORY_START = "2018-06-01"           # [ASSUMPTION] >= 2y warm-up

# --------------------------------------------------------------------------------------
# Cost sensitivity ladder  [ASSUMPTION]
# Primary result uses the literal spec (COST_PER_SIDE). The ladder is reported as a
# sensitivity so the jury can see we know what real all-in Indian equity costs look like.
#   0.0010  literal spec, per side
#   0.0012  + exchange txn charge ~0.00297%, SEBI fee, 18% GST, stamp 0.015% (buy side)
#   0.0015  + conservative impact cost for mid/small caps
#   0.0025  stress: wide-spread smallcap execution
# NOTE: STT (0.1% delivery, both sides) is NOT added on top of the spec's 0.1% because the
# spec calls its 0.1% "per SEBI guidelines", which most plausibly *is* the STT-like charge.
# Double-counting it would misstate the primary result. Flagged in QUESTIONS_FOR_ORGANISERS.
# --------------------------------------------------------------------------------------
COST_LADDER = [0.0010, 0.0012, 0.0015, 0.0025]

# --------------------------------------------------------------------------------------
# Benchmarks
# --------------------------------------------------------------------------------------
BENCH_TICKERS = {
    "NIFTY500": "^CRSLDX",
    "NIFTY50": "^NSEI",
    "NIFTYMIDCAP100": "NIFTY_MIDCAP_100.NS",
    "NIFTYSMLCAP100": "^CNXSC",
}
PRIMARY_BENCHMARK = "NIFTY500"         # [ASSUMPTION] universe spans large+mid+small

# Nifty 500 TRI vs PRI: the index we can download is a price index. Indian large/mid/small
# dividend yield has run ~1.1-1.3% over the window. We add a constant TRI uplift so the
# comparison is total-return vs total-return (our NAV reinvests dividends).
TRI_DIVIDEND_YIELD = 0.0120            # [ASSUMPTION] 1.20% p.a., sensitivity 0.9%-1.5%

# --------------------------------------------------------------------------------------
# Index reconstruction bands (NSE published methodology)
# --------------------------------------------------------------------------------------
# Nifty 100        = full-mcap ranks 1..100
# Nifty Midcap 100 = top 100 of Nifty Midcap 150 (ranks 101..250)  -> ranks 101..200
# Nifty Smallcap100= top 100 of Nifty Smallcap 250 (ranks 251..500)-> ranks 251..350
RANK_BANDS = {
    "NIFTY100": (1, 100),
    "MIDCAP100": (101, 200),
    "SMALLCAP100": (251, 350),
}
# Semi-annual review: cut-off 31 Jan / 31 Jul, effective end-Mar / end-Sep.
REVIEW_CUTOFF_MONTHS = (1, 7)
REVIEW_EFFECTIVE_MONTHS = (4, 10)      # membership changes take effect start of these months

# --------------------------------------------------------------------------------------
# Liquidity / tradability filters  [ASSUMPTION]
# --------------------------------------------------------------------------------------
MIN_MEDIAN_TURNOVER = 2.0e7            # INR 2 crore median daily traded value over 60d
MIN_PRICE = 10.0                       # INR; avoid penny-stock artefacts
MIN_HISTORY_DAYS = 252                 # need 1y of history to compute the signals honestly

# --------------------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------------------
SEED = 20260902


def set_seeds(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


set_seeds()

TRADING_DAYS = 252                     # [ASSUMPTION] NSE trading days per year
