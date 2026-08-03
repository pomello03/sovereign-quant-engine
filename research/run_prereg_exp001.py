"""EXP-001: the single pre-registered test. Rules fixed in EXPERIMENT_REGISTER.md.

Method: the outcome of entering at *every* 4h bar is computed once, by walking the
real 1m candles. A signal is then just a subset of those bars. This makes the
comparison exact — the baseline and every candidate share the same exits, the
same fees and the same intrabar resolution, so the only thing that differs is
when you decide to enter, which is the thing being tested.

Overlapping entries are skipped: a signal that fires while a position is open is
ignored, as it would be in practice.

    .venv-jesse/Scripts/python.exe research/run_prereg_exp001.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import jesse.indicators as ta

HERE = Path(__file__).parent
DATA_1M = HERE / "data" / "bybit_spot_BTCUSDT_1.npy"
DATA_4H = HERE / "data" / "bybit_spot_BTCUSDT_240.json"

FEE = 0.001
STOP_PCT, TARGET_PCT = 0.02, 0.04
MAX_HOLD_DAYS = 90
WINDOW = ("2024-01-01", "2026-07-01")

MIN_ENTRIES = 30
N_CANDIDATES = 6
ALPHA = 0.05
PASS_PERCENTILE = 100 * (1 - ALPHA / N_CANDIDATES)  # Bonferroni: 99.1667

TS, OPEN, CLOSE, HIGH, LOW = 0, 1, 2, 3, 4


def to_ms(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def max_drawdown(equity: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity)
    return float(np.max((peaks - equity) / peaks) * 100)


def entry_outcomes(candles_1m, window_4h):
    """For each 4h bar in the window: net return and holding time in 4h bars."""
    m_ts, m_high, m_low, m_close = (
        candles_1m[:, TS], candles_1m[:, HIGH], candles_1m[:, LOW], candles_1m[:, CLOSE]
    )
    horizon = MAX_HOLD_DAYS * 1440
    rets = np.full(len(window_4h), np.nan)
    holds = np.zeros(len(window_4h), dtype=int)

    for i, row in enumerate(window_4h):
        start = int(np.searchsorted(m_ts, row[TS] + 4 * 3_600_000))
        if start >= len(m_ts) - 1:
            continue
        end = min(start + horizon, len(m_ts))
        entry = float(row[CLOSE])
        stop, target = entry * (1 - STOP_PCT), entry * (1 + TARGET_PCT)

        seg_low, seg_high = m_low[start:end], m_high[start:end]
        s_mask, t_mask = seg_low <= stop, seg_high >= target
        hit_s = int(np.argmax(s_mask)) if s_mask.any() else -1
        hit_t = int(np.argmax(t_mask)) if t_mask.any() else -1

        if hit_s == -1 and hit_t == -1:
            exit_price, minutes = float(m_close[end - 1]), end - start
        elif hit_t == -1 or (hit_s != -1 and hit_s <= hit_t):
            exit_price, minutes = stop, hit_s + 1
        else:
            exit_price, minutes = target, hit_t + 1

        rets[i] = (exit_price / entry) * (1 - FEE) ** 2 - 1
        holds[i] = max(1, int(np.ceil(minutes / 240)))
    return rets, holds


def sequential(signal_bars: np.ndarray, rets: np.ndarray, holds: np.ndarray):
    """Take signals in order, skipping any that fire while a position is open."""
    taken, i, n = [], 0, len(rets)
    while i < n:
        if signal_bars[i] and not np.isnan(rets[i]):
            taken.append(i)
            i += holds[i]
        else:
            i += 1
    return np.array(taken, dtype=int)


def build_signals(candles_4h: np.ndarray, window_mask: np.ndarray) -> dict:
    """Indicators on the full series, then sliced — so warm-up is real history."""
    closes = candles_4h[:, CLOSE]
    highs = candles_4h[:, HIGH]

    rsi14 = ta.rsi(candles_4h, 14, sequential=True)
    sma20 = ta.sma(candles_4h, 20, sequential=True)
    sma50 = ta.sma(candles_4h, 50, sequential=True)
    sma200 = ta.sma(candles_4h, 200, sequential=True)
    ema20 = ta.ema(candles_4h, 20, sequential=True)
    ema50 = ta.ema(candles_4h, 50, sequential=True)

    std20 = np.full(len(closes), np.nan)
    for i in range(19, len(closes)):
        std20[i] = closes[i - 19: i + 1].std()

    donch20 = np.full(len(closes), np.nan)
    for i in range(20, len(closes)):
        donch20[i] = highs[i - 20: i].max()

    prev = np.roll(closes, 1)
    prev30 = np.roll(closes, 30)

    sig = {
        "S1 donchian20 breakout": closes > donch20,
        "S2 rsi(14) < 30": rsi14 < 30,
        "S3 bollinger lower": closes < (sma20 - 2 * std20),
        "S4 ema20 x ema50 up": (ema20 > ema50) & (np.roll(ema20, 1) <= np.roll(ema50, 1)),
        "S5 momentum 30 bars": closes > prev30,
        "S6 pullback in uptrend": (closes > sma200) & (rsi14 < 40),
        "C0 sma(50) cross up [reference]": (closes > sma50) & (prev <= np.roll(sma50, 1)),
    }
    return {k: np.nan_to_num(v, nan=False)[window_mask] for k, v in sig.items()}


def main() -> int:
    candles_4h = np.array(json.loads(DATA_4H.read_text()), dtype=float)
    candles_1m = np.load(DATA_1M)

    lo, hi = to_ms(WINDOW[0]), to_ms(WINDOW[1])
    window_mask = (candles_4h[:, TS] >= lo) & (candles_4h[:, TS] < hi)
    window_4h = candles_4h[window_mask]

    print(f"EXP-001 · Bybit spot BTC-USDT 4h · {WINDOW[0]} -> {WINDOW[1]}")
    print(f"pass bar: > {PASS_PERCENTILE:.2f}th percentile of matched random baseline")
    print(f"          (Bonferroni, {N_CANDIDATES} candidates, alpha={ALPHA})")
    print(f"          AND >= {MIN_ENTRIES} entries AND positive net return\n")
    print(f"computing the outcome of entering at each of {len(window_4h)} bars...")

    rets, holds = entry_outcomes(candles_1m, window_4h)
    pool = rets[~np.isnan(rets)]
    signals = build_signals(candles_4h, window_mask)
    rng = np.random.default_rng(20260803)

    print(f"\n{'signal':<34}{'n':>5}{'net':>9}{'maxDD':>8}{'win%':>7}"
          f"{'pctile':>9}  verdict")
    print("-" * 80)

    results = {}
    for name, fires in signals.items():
        idx = sequential(fires, rets, holds)
        n = len(idx)
        if n == 0:
            print(f"{name:<34}{0:>5}{'—':>9}{'—':>8}{'—':>7}{'—':>9}  no entries")
            results[name] = {"n": 0}
            continue

        taken = rets[idx]
        equity = np.concatenate([[1.0], np.cumprod(1 + taken)])
        net = (equity[-1] - 1) * 100
        dd = max_drawdown(equity)
        win = (taken > 0).mean() * 100

        # Baseline matched on trade count: the only difference is entry timing.
        draws = rng.choice(pool, size=(10_000, n), replace=True)
        finals = (np.prod(1 + draws, axis=1) - 1) * 100
        pct = float((finals < net).mean() * 100)

        reference = name.startswith("C0")
        passes = (not reference) and n >= MIN_ENTRIES and pct > PASS_PERCENTILE and net > 0
        verdict = ("reference" if reference
                   else "PASS" if passes
                   else "fail")
        print(f"{name:<34}{n:>5}{net:>8.1f}%{dd:>7.1f}%{win:>6.1f}%{pct:>8.1f}%  {verdict}")

        results[name] = {
            "n_trades": n, "net_return_pct": net, "max_drawdown_pct": dd,
            "win_rate_pct": win, "percentile_vs_random": pct,
            "baseline_p95": float(np.percentile(finals, 95)),
            "baseline_pass_bar": float(np.percentile(finals, PASS_PERCENTILE)),
            "passes": bool(passes), "is_reference": reference,
        }

    passed = [k for k, v in results.items() if v.get("passes")]
    print("-" * 80)
    print(f"\n{len(passed)} of {N_CANDIDATES} candidates passed.")
    if passed:
        print("  " + "\n  ".join(passed))
        print("\nPassing is not a promotion. It is permission to begin the full protocol")
        print("in docs/VALIDATION_AND_LIVE_GATES.md, on a window never opened.")
    else:
        print("\nNo signal cleared the bar. Per the register, the project stops at research:")
        print("no capital, no execution layer. The honest engine is the deliverable.")

    out = HERE / "results" / "exp001.json"
    out.write_text(json.dumps({
        "experiment": "EXP-001", "window": WINDOW,
        "pass_percentile": PASS_PERCENTILE, "min_entries": MIN_ENTRIES,
        "n_candidates": N_CANDIDATES, "results": results,
        "n_passed": len(passed), "passed": passed,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
