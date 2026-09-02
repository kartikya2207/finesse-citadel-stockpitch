"""Data ingestion: master ticker list, daily prices, corporate actions, shares outstanding.

Design notes (these matter for correctness):

* yfinance `Close` with auto_adjust=False is adjusted for CAPITAL actions (splits, bonuses,
  rights) but NOT for dividends. `Adj Close` is adjusted for both. Verified empirically:
  TCS 2019-12-30 Close=2183.20 (matches the true raw close, no splits since 2018) while
  Adj Close=1844.29.
* Therefore:
    - RETURNS use `Adj Close`  -> total return, dividends reinvested.
    - MARKET CAP uses `Close * cum_split_factor_after_t * shares_reported(t)`, because
      `get_shares_full` returns AS-REPORTED share counts (verified: RELIANCE 5.93bn in 2019
      -> 13.53bn after the Oct-2024 1:1 bonus; IRCTC 160m -> 800m after the 1:5 split).
      Multiplying the capital-adjusted price back up by the future split factor recovers a
      price on the same per-share basis as the contemporaneous share count.
      Residual error: rights issues get a Yahoo price factor that is not in the splits
      column (e.g. RELIANCE 2020 1:15 rights), understating pre-event mcap by a few percent.
      Logged as a known limitation; it cannot move a rank band by more than a place or two.
"""
from __future__ import annotations

import io
import json
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf

from .config import BENCH_TICKERS, CACHE, HISTORY_START, RAW

warnings.filterwarnings("ignore")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/csv,text/html,*/*"}

NIFTY_INDEX_FILES = [
    "ind_nifty50list", "ind_niftynext50list", "ind_nifty100list",
    "ind_nifty200list", "ind_nifty500list",
    "ind_niftymidcap50list", "ind_niftymidcap100list", "ind_niftymidcap150list",
    "ind_niftysmallcap50list", "ind_niftysmallcap100list", "ind_niftysmallcap250list",
    "ind_niftymidsmallcap400list", "ind_niftylargemidcap250list",
    "ind_niftymicrocap250_list", "ind_niftytotalmarket_list",
]

# Names that were in Nifty 100 / Midcap 100 / Smallcap 100 at some point in 2021-2026 but
# are gone from the current lists (merged, delisted, demerged, or demoted out of the Total
# Market 750). Included so the master panel is not survivor-only.
# [ASSUMPTION] compiled from NSE reconstitution history; incomplete by construction.
HISTORICAL_EXTRAS = [
    # merged / delisted
    "HDFC", "SHREECEM", "IBULHSGFIN", "PNBHOUSING", "ADANITRANS", "SRTRANSFIN",
    "MINDTREE", "MPHASIS", "AJANTPHARM", "GUJGASLTD", "RALLIS", "VAKRANGEE",
    "DHFL", "YESBANK", "RCOM", "JETAIRWAYS", "DISHTV", "SINTEX", "JPASSOCIAT",
    "RPOWER", "SUZLON", "GTLINFRA", "IDEA", "VODAFONE", "EDELWEISS",
    "EQUITAS", "UJJIVAN", "SPANDANA", "MAGMA", "RELCAPITAL", "SREINFRA",
    "LTI", "MFSL", "AMARAJABAT", "GMRINFRA", "ADANIGREEN", "IBREALEST",
    "STARCEMENT", "ORIENTCEM", "HEIDELBERG", "INDIACEM", "BIRLACORPN",
    "TATACOFFEE", "RUCHI", "JUBLFOOD", "CADILAHC", "TORNTPOWER", "NAM-INDIA",
    "MOTHERSUMI", "MOTHERSON", "SANOFI", "PFIZER", "ABBOTINDIA", "GLAXO",
    "CRISIL", "THOMASCOOK", "COX&KINGS", "ZEEL", "ZEEMEDIA", "NDTV",
    "HATHWAY", "DEN", "SITICABLE", "TV18BRDCST", "NETWORK18",
    "FCONSUMER", "FRETAIL", "FLFL", "FEL", "SHOPERSTOP",
    "TATASTLLP", "TATAMTRDVR", "ADANIPOWER", "JSWENERGY", "CESC",
    "IIFLWAM", "IIFL", "IIFLSEC", "GRAPHITE", "HEG", "PHILIPCARB",
    "RAJESHEXPO", "TITAGARH", "BEML", "COCHINSHIP", "MAZDOCK",
    "AEGISCHEM", "AEGISLOG", "GNFC", "GSFC", "CHAMBLFERT", "RCF",
    "MMTC", "MOIL", "NBCC", "HUDCO", "IRCON", "RVNL", "RITES",
    "SPICEJET", "INDIGO", "GESHIP", "SCI", "ALLCARGO",
]


# --------------------------------------------------------------------------------------
# Index constituent lists
# --------------------------------------------------------------------------------------
def fetch_index_lists(force: bool = False) -> dict[str, pd.DataFrame]:
    """Download current NSE index constituent CSVs (cached to data/raw)."""
    out: dict[str, pd.DataFrame] = {}
    for name in NIFTY_INDEX_FILES:
        path = RAW / f"{name}.csv"
        if path.exists() and not force:
            out[name] = pd.read_csv(path)
            continue
        try:
            r = requests.get(
                f"https://niftyindices.com/IndexConstituent/{name}.csv",
                headers=HEADERS, timeout=45,
            )
            if r.status_code == 200 and b"Symbol" in r.content:
                path.write_bytes(r.content)
                out[name] = pd.read_csv(io.BytesIO(r.content))
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {name}: {type(exc).__name__} {exc}")
        time.sleep(0.3)
    return out


def fetch_wayback_lists() -> dict[str, pd.DataFrame]:
    """Historical snapshots of the three target constituent CSVs from the Wayback Machine.

    These are the only *published* point-in-time membership lists obtainable without a paid
    vendor. They serve two purposes: (a) validation anchors for the mcap reconstruction,
    (b) recovery of names that have since left the current lists.
    """
    path = RAW / "wayback_lists.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: pd.DataFrame(v) for k, v in raw.items()}

    targets = {
        "NIFTY100": "ind_nifty100list.csv",
        "MIDCAP100": "ind_niftymidcap100list.csv",
        "SMALLCAP100": "ind_niftysmallcap100list.csv",
    }
    bases = [
        "https://niftyindices.com/IndexConstituent/",
        "https://www1.nseindia.com/content/indices/",
        "https://archives.nseindia.com/content/indices/",
    ]
    found: dict[str, pd.DataFrame] = {}
    for idx, fname in targets.items():
        for base in bases:
            cdx = (f"http://web.archive.org/cdx/search/cdx?url={base}{fname}"
                   f"&output=json&fl=timestamp,statuscode&collapse=digest"
                   f"&from=2020&to=2026&limit=200")
            try:
                rows = requests.get(cdx, headers=HEADERS, timeout=60).json()
            except Exception:  # noqa: BLE001
                continue
            for ts, status in rows[1:]:
                if status != "200":
                    continue
                url = f"http://web.archive.org/web/{ts}id_/{base}{fname}"
                try:
                    r = requests.get(url, headers=HEADERS, timeout=60)
                    if r.status_code == 200 and b"Symbol" in r.content:
                        df = pd.read_csv(io.BytesIO(r.content))
                        key = f"{idx}@{ts[:8]}"
                        found[key] = df[["Symbol"]].copy()
                        print(f"  wayback {key}: {len(df)} names")
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.5)
    path.write_text(
        json.dumps({k: v.to_dict("list") for k, v in found.items()}, indent=1),
        encoding="utf-8",
    )
    return found


def build_master_symbols(force: bool = False) -> list[str]:
    """Widest defensible NSE cross-section: current index lists + historical snapshots
    + known departed names. Deliberately over-inclusive; the PIT rank filter narrows it."""
    path = RAW / "master_symbols.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))

    syms: set[str] = set()
    for name, df in fetch_index_lists(force=force).items():
        if "Symbol" in df.columns:
            syms |= {str(s).strip().upper() for s in df["Symbol"]}
    for key, df in fetch_wayback_lists().items():
        syms |= {str(s).strip().upper() for s in df["Symbol"]}
    syms |= {s.strip().upper() for s in HISTORICAL_EXTRAS}
    syms = {s for s in syms if s and s != "NAN"}
    out = sorted(syms)
    path.write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


# --------------------------------------------------------------------------------------
# Prices
# --------------------------------------------------------------------------------------
def _yf(sym: str) -> str:
    return f"{sym}.NS"


def download_prices(symbols: list[str], end: str, force: bool = False,
                    batch: int = 60, cache_key: str | None = None) -> pd.DataFrame:
    """Long-format daily panel: date, symbol, close(capital-adj), adjclose, volume, split."""
    path = CACHE / f"prices_{cache_key or end}.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)

    frames: list[pd.DataFrame] = []
    tickers = [_yf(s) for s in symbols]
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            d = yf.download(chunk, start=HISTORY_START, end=end, auto_adjust=False,
                            actions=True, progress=False, threads=True,
                            group_by="column")
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] batch {i}: {type(exc).__name__} {exc}")
            continue
        if d is None or d.empty:
            continue
        if not isinstance(d.columns, pd.MultiIndex):
            d.columns = pd.MultiIndex.from_product([d.columns, [chunk[0]]])
        for field, col in [("Close", "close"), ("Adj Close", "adjclose"),
                           ("Volume", "volume"), ("Stock Splits", "split")]:
            if field not in d.columns.get_level_values(0):
                continue
            sub = d[field].stack().rename(col)
            frames.append(sub.to_frame())
        print(f"  prices {i + len(chunk)}/{len(tickers)}")

    if not frames:
        raise RuntimeError("no price data downloaded")

    # merge the per-field long frames on (date, ticker)
    merged = frames[0]
    for f in frames[1:]:
        merged = merged.combine_first(f) if set(f.columns) & set(merged.columns) else \
            merged.join(f, how="outer")
    # combine_first above is only hit when duplicate columns appear across batches; the
    # robust path is a groupby concat instead:
    big = pd.concat(frames)
    big = big.groupby(level=[0, 1]).first()
    big.index.names = ["date", "ticker"]
    big = big.reset_index()
    big["symbol"] = big["ticker"].str.replace(".NS", "", regex=False)
    big["date"] = pd.to_datetime(big["date"]).dt.tz_localize(None).dt.normalize()
    big = big.drop(columns=["ticker"])
    big = big.dropna(subset=["adjclose"])
    big.to_parquet(path, index=False)
    return big


def download_shares(symbols: list[str], end: str, force: bool = False,
                    workers: int = 12, cache_key: str | None = None) -> pd.DataFrame:
    """As-reported shares outstanding time series per symbol."""
    path = CACHE / f"shares_{cache_key or end}.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)

    def one(sym: str):
        try:
            s = yf.Ticker(_yf(sym)).get_shares_full(start=HISTORY_START, end=end)
            if s is None or len(s) == 0:
                return None
            s = pd.Series(s)
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            s = s[~s.index.duplicated(keep="last")].sort_index()
            return pd.DataFrame({"date": s.index, "symbol": sym,
                                 "shares": s.to_numpy(dtype="float64")})
        except Exception:  # noqa: BLE001
            return None

    rows: list[pd.DataFrame] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, s): s for s in symbols}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r is not None:
                rows.append(r)
            if done % 100 == 0:
                print(f"  shares {done}/{len(symbols)}  ok={len(rows)}")
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["date", "symbol", "shares"])
    out.to_parquet(path, index=False)
    return out


def download_benchmarks(end: str, force: bool = False) -> pd.DataFrame:
    path = CACHE / f"bench_{end}.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)
    frames = []
    for name, tk in BENCH_TICKERS.items():
        try:
            h = yf.Ticker(tk).history(start=HISTORY_START, end=end, auto_adjust=False)
            if h is None or h.empty:
                print(f"  [warn] benchmark {name} ({tk}) empty")
                continue
            s = h["Close"].copy()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            frames.append(s.rename(name))
            print(f"  benchmark {name}: {len(s)} rows {s.index.min().date()}..{s.index.max().date()}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] benchmark {name}: {type(exc).__name__} {exc}")
    df = pd.concat(frames, axis=1).sort_index()
    df.index.name = "date"
    df.reset_index().to_parquet(path, index=False)
    return df.reset_index()
