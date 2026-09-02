"""Stress-window seal.

The stress window (2026-01-01 .. 2026-06-30) must not influence the in-sample design.
Today's date makes that data physically downloadable, so the seal has to be enforced in
code rather than by the calendar.

Rules enforced here:
  * `assert_sealed(dates)` raises if any date > BACKTEST_END is used while the seal holds.
  * The seal is broken ONLY by `freeze_design()`, which writes FROZEN.json containing the
    frozen parameters, a SHA-256 of every strategy-relevant source file, and a UTC timestamp.
  * Every unseal attempt is appended to logs/seal.log, so a post-hoc parameter tweak is
    visible in the audit trail.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import BACKTEST_END, LOGS, ROOT

FROZEN_PATH = ROOT / "FROZEN.json"
SEAL_LOG = LOGS / "seal.log"

_STRATEGY_FILES = [
    "src/config.py",
    "src/signals.py",
    "src/backtest.py",
    "src/strategies.py",
]


class SealBroken(RuntimeError):
    """Raised when out-of-sample data is touched before the design is frozen."""


def _log(msg: str) -> None:
    SEAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SEAL_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()}  {msg}\n")


def is_frozen() -> bool:
    return FROZEN_PATH.exists()


def source_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in _STRATEGY_FILES:
        p = ROOT / rel
        if p.exists():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def assert_sealed(dates, context: str = "") -> None:
    """Raise unless every date is in-sample, or the design has been frozen."""
    if is_frozen():
        return
    if dates is None or len(dates) == 0:
        return
    last = pd.Timestamp(pd.DatetimeIndex(dates).max())
    if last > pd.Timestamp(BACKTEST_END):
        _log(f"BLOCKED  context={context!r} max_date={last.date()}")
        raise SealBroken(
            f"Attempt to use data after {BACKTEST_END} (max={last.date()}) in "
            f"context={context!r} while the stress window is sealed. "
            "Call seal.freeze_design(...) first."
        )


def clip_to_sample(df: pd.DataFrame, context: str = "") -> pd.DataFrame:
    """Defensive helper: truncate a date-indexed frame to the in-sample window."""
    if is_frozen():
        return df
    return df.loc[: pd.Timestamp(BACKTEST_END)]


def freeze_design(name: str, params: dict, rationale: str) -> dict:
    """Freeze the in-sample design and unseal the stress window. One-way door."""
    if is_frozen():
        existing = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
        _log(f"RE-FREEZE ATTEMPT strategy={name!r} (ignored; already frozen)")
        return existing
    payload = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_name": name,
        "parameters": params,
        "rationale": rationale,
        "source_sha256": source_hashes(),
        "in_sample_window": ["2021-01-01", BACKTEST_END],
        "note": (
            "Written before any 2026 result was computed. Any parameter differing from "
            "this file in the final submission is a post-hoc change and must be treated "
            "as invalid."
        ),
    }
    FROZEN_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _log(f"FROZEN strategy={name!r} params={json.dumps(params, sort_keys=True)}")
    _log("UNSEALED stress window 2026-01-01..2026-06-30")
    return payload


def verify_no_drift() -> dict:
    """After freezing, confirm strategy sources have not changed."""
    if not is_frozen():
        return {"frozen": False}
    payload = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    now = source_hashes()
    drift = {
        k: {"frozen": v, "now": now.get(k)}
        for k, v in payload["source_sha256"].items()
        if now.get(k) != v
    }
    return {"frozen": True, "drift": drift, "clean": not drift}
