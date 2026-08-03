"""Fetch daily candles for every Bybit spot USDT pair.

Cross-sectional strategies need many assets, not one. This pulls the whole
listed universe at daily resolution — enough for a monthly rebalance, and small
enough to keep on disk.

Survivorship: the exchange's instrument list contains only pairs that are still
listed today. Coins that were delisted, collapsed, or quietly stopped trading are
absent, and their absence flatters every result computed on what remains. That
cannot be fixed from this endpoint. It is recorded in the metadata and carried
into the experiment's conclusions rather than hidden.

    python research/fetch_bybit_universe.py --start 2021-01-01 --end 2026-08-01
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fetch_bybit_candles import INTERVAL_MS, _get, fetch_candles

BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"
DATA_DIR = Path(__file__).parent / "data"
INTERVAL = "D"


def to_ms(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def list_usdt_spot_symbols() -> list[str]:
    payload = _get(BYBIT_INSTRUMENTS_URL, {"category": "spot", "limit": 1000})
    rows = payload["result"]["list"]
    symbols = sorted(
        r["symbol"] for r in rows
        if r.get("quoteCoin") == "USDT" and r.get("status") == "Trading"
    )
    # Leveraged tokens (BTC3L, ETH3S...) are derivatives dressed as spot pairs:
    # they decay by construction and would be measured as if they were coins.
    return [s for s in symbols if not s[:-4].endswith(("3L", "3S", "2L", "2S"))]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2021-01-01")
    p.add_argument("--end", default="2026-08-01")
    p.add_argument("--pause", type=float, default=0.12)
    args = p.parse_args()

    start_ms, end_ms = to_ms(args.start), to_ms(args.end)
    symbols = list_usdt_spot_symbols()
    print(f"{len(symbols)} USDT spot pairs currently listed on Bybit")
    print(f"fetching daily candles {args.start} -> {args.end}\n")

    series, failures = {}, []
    for i, sym in enumerate(symbols, 1):
        try:
            candles = fetch_candles(sym, INTERVAL, start_ms, end_ms, args.pause)
            if candles:
                candles = candles[:-1]  # drop the still-forming last bar
        except Exception as exc:  # noqa: BLE001 - one bad pair must not stop the sweep
            failures.append({"symbol": sym, "error": str(exc)})
            continue
        if len(candles) < 30:
            continue
        series[sym] = candles
        if i % 25 == 0 or i == len(symbols):
            print(f"  {i:>4}/{len(symbols)}  kept {len(series)}", flush=True)

    if not series:
        print("nothing fetched")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stem = "bybit_spot_universe_D"
    (DATA_DIR / f"{stem}.json").write_text(json.dumps(series), encoding="utf-8")

    digest = hashlib.sha256(
        "".join(
            f"{s}|" + "|".join(f"{c[0]:.0f}:{c[2]}" for c in series[s])
            for s in sorted(series)
        ).encode()
    ).hexdigest()

    def iso(ms: float) -> str:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")

    coverage = {
        s: {"first": iso(c[0][0]), "last": iso(c[-1][0]), "n": len(c)}
        for s, c in series.items()
    }
    meta = {
        "source": "bybit",
        "category": "spot",
        "quote": "USDT",
        "interval_code": INTERVAL,
        "interval_ms": INTERVAL_MS[INTERVAL],
        "column_order": ["timestamp", "open", "close", "high", "low", "volume"],
        "requested_start": args.start,
        "requested_end": args.end,
        "n_symbols_listed": len(symbols),
        "n_symbols_kept": len(series),
        "failures": failures,
        "survivorship_warning": (
            "Only pairs still listed and trading at fetch time are present. "
            "Delisted and dead coins are absent, which flatters any result "
            "computed on this universe. A random-selection baseline drawn from "
            "the same universe inherits the same bias, so relative comparisons "
            "remain meaningful while absolute returns do not."
        ),
        "sha256": digest,
        "coverage": coverage,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA_DIR / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nkept {len(series)} pairs, {len(failures)} failures")
    print(f"sha256 {digest[:16]}")
    print(f"-> {DATA_DIR / stem}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
