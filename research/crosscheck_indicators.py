"""Cross-check the hand-rolled indicators in count_signals.py against Jesse's.

count_signals.py deliberately depends on nothing, which makes its result cheap to
reproduce and impossible to verify from the inside. This script re-runs the same
question through Jesse's own indicator implementations (TA-Lib-compatible) and
reports the maximum divergence.

Must be run with the isolated Jesse interpreter:

    .venv-jesse/Scripts/python.exe research/crosscheck_indicators.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

import jesse.indicators as ta

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from count_signals import rsi as own_rsi, sma as own_sma  # noqa: E402

DATA = HERE / "data" / "bybit_spot_BTCUSDT_240.json"
RSI_PERIOD, SMA_PERIOD, RSI_OVERSOLD = 14, 50, 30


def main() -> int:
    candles = np.array(json.loads(DATA.read_text()), dtype=float)
    closes = [float(c[2]) for c in candles]

    j_rsi = ta.rsi(candles, RSI_PERIOD, sequential=True)
    j_sma = ta.sma(candles, SMA_PERIOD, sequential=True)
    o_rsi, o_sma = own_rsi(closes, RSI_PERIOD), own_sma(closes, SMA_PERIOD)

    # Compare only where both are defined and finite.
    rsi_diffs = [
        abs(j_rsi[i] - o_rsi[i])
        for i in range(len(closes))
        if o_rsi[i] is not None and np.isfinite(j_rsi[i])
    ]
    sma_diffs = [
        abs(j_sma[i] - o_sma[i])
        for i in range(len(closes))
        if o_sma[i] is not None and np.isfinite(j_sma[i])
    ]

    print(f"candles: {len(candles)}")
    print(f"RSI({RSI_PERIOD})  compared on {len(rsi_diffs)} bars  "
          f"max|diff| = {max(rsi_diffs):.3e}")
    print(f"SMA({SMA_PERIOD})  compared on {len(sma_diffs)} bars  "
          f"max|diff| = {max(sma_diffs):.3e}")

    # The headline number, recomputed entirely with Jesse's indicators.
    hits = sum(
        1
        for i in range(len(closes))
        if np.isfinite(j_rsi[i])
        and np.isfinite(j_sma[i])
        and j_rsi[i] < RSI_OVERSOLD
        and closes[i] > j_sma[i]
    )
    defined = sum(1 for i in range(len(closes)) if np.isfinite(j_rsi[i]) and np.isfinite(j_sma[i]))
    lowest_rsi_above_sma = min(
        j_rsi[i]
        for i in range(len(closes))
        if np.isfinite(j_rsi[i]) and np.isfinite(j_sma[i]) and closes[i] > j_sma[i]
    )

    print(f"\nUsing Jesse's indicators only, on {defined} bars:")
    print(f"  rsi < {RSI_OVERSOLD} AND close > sma  ->  {hits} bars")
    print(f"  lowest RSI observed while close > sma ->  {lowest_rsi_above_sma:.2f}")

    ok = max(rsi_diffs) < 1e-6 and max(sma_diffs) < 1e-6 and hits == 0
    print(f"\n{'AGREES' if ok else 'DISAGREES'} with count_signals.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
