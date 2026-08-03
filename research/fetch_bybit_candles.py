"""Fetch real spot candles from Bybit's public market-data API.

Standalone by design: imports nothing from core_engine. Its only job is to turn
public market data into a file on disk, together with enough provenance that a
later reader can tell exactly what was measured and re-fetch the same window.

Public endpoint, no credentials, read-only.

    python research/fetch_bybit_candles.py --symbol BTCUSDT --interval 240 \
        --start 2021-01-01 --end 2026-08-01
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
MAX_LIMIT = 1000
DATA_DIR = Path(__file__).parent / "data"

# Bybit interval code -> milliseconds. Only the codes we actually use.
INTERVAL_MS = {
    "1": 60_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "120": 7_200_000,
    "240": 14_400_000,
    "360": 21_600_000,
    "720": 43_200_000,
    "D": 86_400_000,
}


def _to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _get(url: str, params: dict, retries: int = 5) -> dict:
    """GET with bounded exponential backoff. Raises on persistent failure.

    Never returns a partial or synthetic result: a caller that gets a value back
    knows it came from the exchange.
    """
    query = urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{url}?{query}", headers={"User-Agent": "sqe-research/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
            if payload.get("retCode") != 0:
                raise RuntimeError(f"Bybit retCode={payload.get('retCode')} {payload.get('retMsg')}")
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Bybit request failed after {retries} attempts: {last_error}")


def fetch_candles(
    symbol: str, interval: str, start_ms: int, end_ms: int, pause: float = 0.15
) -> list[list[float]]:
    """Page backwards from end_ms to start_ms.

    Returns candles in Jesse's column order: [timestamp, open, close, high, low, volume].
    Ascending by timestamp, deduplicated.
    """
    step = INTERVAL_MS[interval]
    collected: dict[int, list[float]] = {}
    cursor = end_ms
    empty_pages = 0

    while cursor > start_ms:
        payload = _get(
            BYBIT_KLINE_URL,
            {
                "category": "spot",
                "symbol": symbol,
                "interval": interval,
                "start": start_ms,
                "end": cursor,
                "limit": MAX_LIMIT,
            },
        )
        rows = payload["result"]["list"]  # newest first
        if not rows:
            empty_pages += 1
            if empty_pages >= 2:
                break
            cursor -= step * MAX_LIMIT
            continue
        empty_pages = 0

        for r in rows:
            ts = int(r[0])
            if ts < start_ms or ts > end_ms:
                continue
            # Bybit: startTime, open, high, low, close, volume, turnover
            # Jesse: timestamp, open, close, high, low, volume
            collected[ts] = [
                float(ts),
                float(r[1]),
                float(r[4]),
                float(r[2]),
                float(r[3]),
                float(r[5]),
            ]

        oldest = min(int(r[0]) for r in rows)
        if oldest <= start_ms:
            break
        cursor = oldest - 1
        if len(collected) % 50_000 < MAX_LIMIT:
            print(
                f"  {len(collected):>8} candles  <- "
                f"{datetime.fromtimestamp(oldest / 1000, timezone.utc):%Y-%m-%d %H:%M}",
                flush=True,
            )
        time.sleep(pause)  # stay well inside the public rate limit

    return [collected[k] for k in sorted(collected)]


def check_integrity(candles: list[list[float]], interval: str) -> dict:
    """Report gaps and anomalies instead of silently interpolating them.

    A gap is information about the data, not a defect to be smoothed away: a
    backtest run across a hidden gap produces plausible numbers from candles
    that were never adjacent.
    """
    step = INTERVAL_MS[interval]
    gaps, non_monotonic, bad_ohlc = [], 0, 0

    for i in range(1, len(candles)):
        delta = candles[i][0] - candles[i - 1][0]
        if delta <= 0:
            non_monotonic += 1
        elif delta != step:
            gaps.append(
                {
                    "after": datetime.fromtimestamp(
                        candles[i - 1][0] / 1000, timezone.utc
                    ).isoformat(),
                    "missing_candles": int(delta / step) - 1,
                }
            )

    for ts, o, c, h, low, v in candles:
        if not (h >= max(o, c) and low <= min(o, c) and low > 0 and v >= 0):
            bad_ohlc += 1

    return {
        "gap_count": len(gaps),
        "missing_candles_total": sum(g["missing_candles"] for g in gaps),
        "largest_gaps": sorted(gaps, key=lambda g: -g["missing_candles"])[:5],
        "non_monotonic_timestamps": non_monotonic,
        "invalid_ohlc_rows": bad_ohlc,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--interval", default="240", choices=sorted(INTERVAL_MS))
    p.add_argument("--start", default="2021-01-01")
    p.add_argument("--end", default="2026-08-01")
    p.add_argument("--pause", type=float, default=0.15, help="seconds between requests")
    p.add_argument(
        "--format",
        default="json",
        choices=("json", "npy"),
        help="npy for 1m datasets — JSON of a million candles is slow to parse and large on disk",
    )
    args = p.parse_args()

    start_ms, end_ms = _to_ms(args.start), _to_ms(args.end)
    step = INTERVAL_MS[args.interval]

    print(f"Bybit spot {args.symbol} {args.interval}m  {args.start} -> {args.end}")
    candles = fetch_candles(args.symbol, args.interval, start_ms, end_ms, args.pause)

    # The final candle is dropped unconditionally: if the window ends in the
    # present it is still forming, and a partially-formed candle has a close
    # price that has not happened yet.
    if candles:
        candles = candles[:-1]
    if not candles:
        print("No candles returned.")
        return 1

    integrity = check_integrity(candles, args.interval)
    expected = int((candles[-1][0] - candles[0][0]) / step) + 1

    digest = hashlib.sha256(
        b"".join(f"{c[0]:.0f}|{c[1]}|{c[2]}|{c[3]}|{c[4]}|{c[5]}".encode() for c in candles)
    ).hexdigest()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"bybit_spot_{args.symbol}_{args.interval}"
    if args.format == "npy":
        import numpy as np  # only needed for the large 1m datasets

        np.save(DATA_DIR / f"{stem}.npy", np.array(candles, dtype=np.float64))
    else:
        (DATA_DIR / f"{stem}.json").write_text(json.dumps(candles), encoding="utf-8")

    meta = {
        "source": "bybit",
        "endpoint": BYBIT_KLINE_URL,
        "category": "spot",
        "symbol": args.symbol,
        "interval_code": args.interval,
        "interval_ms": step,
        "column_order": ["timestamp", "open", "close", "high", "low", "volume"],
        "requested_start": args.start,
        "requested_end": args.end,
        "first_candle": datetime.fromtimestamp(candles[0][0] / 1000, timezone.utc).isoformat(),
        "last_candle": datetime.fromtimestamp(candles[-1][0] / 1000, timezone.utc).isoformat(),
        "n_candles": len(candles),
        "n_candles_expected": expected,
        "completeness_pct": round(100 * len(candles) / expected, 4),
        "integrity": integrity,
        "sha256": digest,
        "format": args.format,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA_DIR / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\n{len(candles)} candles  {meta['first_candle'][:10]} -> {meta['last_candle'][:10]}")
    print(f"completeness {meta['completeness_pct']}%   gaps {integrity['gap_count']}"
          f" ({integrity['missing_candles_total']} missing candles)")
    print(f"invalid OHLC rows {integrity['invalid_ohlc_rows']}   sha256 {digest[:16]}")
    print(f"-> {DATA_DIR / stem}.{args.format}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
