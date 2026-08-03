"""Count how often the alpha_spec entry conditions actually fire.

No framework, no simulator, no position sizing: just the raw question of whether
the signal exists in five years of real candles. If it fires fewer than ~30
times there is nothing for a validation pipeline to validate, and that is a
result worth having before installing anything.

    python research/count_signals.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data" / "bybit_spot_BTCUSDT_240.json"


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Wilder's RSI, the definition Jesse and TradingView both use."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def main() -> int:
    candles = json.loads(DATA.read_text())
    ts = [c[0] for c in candles]
    closes = [c[2] for c in candles]  # column order: timestamp, open, close, high, low, volume

    r = rsi(closes, 14)
    s = sma(closes, 50)

    long_bars, short_bars = [], []
    c_rsi_lo = c_rsi_hi = c_above = c_below = 0

    for i in range(len(closes)):
        if r[i] is None or s[i] is None:
            continue
        rsi_lo, rsi_hi = r[i] < 30, r[i] > 70
        above, below = closes[i] > s[i], closes[i] < s[i]
        c_rsi_lo += rsi_lo
        c_rsi_hi += rsi_hi
        c_above += above
        c_below += below
        if rsi_lo and above:
            long_bars.append(i)
        if rsi_hi and below:
            short_bars.append(i)

    usable = sum(1 for i in range(len(closes)) if r[i] is not None and s[i] is not None)

    def when(i: int) -> str:
        return datetime.fromtimestamp(ts[i] / 1000, timezone.utc).strftime("%Y-%m-%d")

    print(f"Bybit spot BTCUSDT 4h — {usable} usable bars "
          f"({when(0)} -> {when(len(closes) - 1)})\n")
    print("Each condition on its own:")
    print(f"  rsi(14) < 30    {c_rsi_lo:>6} bars  ({100*c_rsi_lo/usable:.2f}%)")
    print(f"  rsi(14) > 70    {c_rsi_hi:>6} bars  ({100*c_rsi_hi/usable:.2f}%)")
    print(f"  close > sma(50) {c_above:>6} bars  ({100*c_above/usable:.2f}%)")
    print(f"  close < sma(50) {c_below:>6} bars  ({100*c_below/usable:.2f}%)\n")

    print("Both together (the actual entry condition):")
    print(f"  LONG   rsi<30 AND close>sma  ->  {len(long_bars)} bars")
    print(f"  SHORT  rsi>70 AND close<sma  ->  {len(short_bars)} bars   [not tradeable on spot]\n")

    # Consecutive signal bars collapse into one trade: a position opened on the
    # first bar is still open on the next. Counting bars would overstate trades.
    def episodes(bars: list[int]) -> list[int]:
        eps: list[int] = []
        for b in bars:
            if not eps or b != prev + 1:
                eps.append(b)
            prev = b
        return eps

    long_eps, short_eps = episodes(long_bars), episodes(short_bars)
    print(f"  distinct LONG episodes (upper bound on trades):  {len(long_eps)}")
    print(f"  distinct SHORT episodes:                         {len(short_eps)}")

    if long_eps:
        print("\n  LONG episode dates:")
        for i in long_eps:
            print(f"    {when(i)}  rsi={r[i]:.1f}  close={closes[i]:.0f}  sma={s[i]:.0f}")

    print()
    if len(long_eps) < 30:
        print(f"VERDICT: {len(long_eps)} long entries in {usable/6/365:.1f} years is below the "
              "30-sample floor.\n         The strategy as specified is not statistically testable.")
    else:
        print(f"VERDICT: {len(long_eps)} long entries clears the 30-sample floor. Proceed to backtest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
