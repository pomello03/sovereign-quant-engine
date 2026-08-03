"""Measure the domain, not a strategy.

Three questions whose answers do not depend on having a good idea:

  1. How far does BTC itself fall? A drawdown limit is only meaningful next to
     the drawdown the instrument produces on its own.
  2. What do the fees cost, relative to the moves actually available? Every
     round trip pays 0.2% on Bybit spot, and that is subtracted from whatever
     edge exists, not from whatever edge is hoped for.
  3. What does entering at random produce? This is the number a strategy has to
     beat. Beating buy-and-hold is not evidence of timing skill; beating random
     entries at the same frequency and holding time is.

Run with the isolated interpreter:

    .venv-jesse/Scripts/python.exe research/measure_domain.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
DATA_1M = HERE / "data" / "bybit_spot_BTCUSDT_1.npy"
DATA_4H = HERE / "data" / "bybit_spot_BTCUSDT_240.json"

FEE = 0.001  # per side
ROUND_TRIP = 1 - (1 - FEE) ** 2  # what a full in-and-out costs, ~0.2%
STOP_PCT, TARGET_PCT = 0.02, 0.04
MAX_HOLD_DAYS = 90
WINDOW = ("2024-01-01", "2026-07-01")

# Column order in both files: timestamp, open, close, high, low, volume
TS, OPEN, CLOSE, HIGH, LOW = 0, 1, 2, 3, 4


def to_ms(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def max_drawdown(equity: np.ndarray) -> float:
    """Largest peak-to-trough fall, in percent."""
    peaks = np.maximum.accumulate(equity)
    return float(np.max((peaks - equity) / peaks) * 100)


def rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ---------------------------------------------------------------- 1.1

def buy_and_hold(candles_4h: np.ndarray) -> dict:
    rule("1.1  How far BTC falls on its own")

    closes = candles_4h[:, CLOSE]
    dd_full = max_drawdown(closes)

    lo, hi = to_ms(WINDOW[0]), to_ms(WINDOW[1])
    mask = (candles_4h[:, TS] >= lo) & (candles_4h[:, TS] < hi)
    win = candles_4h[mask]
    dd_win = max_drawdown(win[:, CLOSE])
    ret_win = (win[-1, CLOSE] / win[0, CLOSE] - 1) * 100

    # How often is the instrument itself more than 2% below its own high?
    peaks = np.maximum.accumulate(win[:, CLOSE])
    underwater = (peaks - win[:, CLOSE]) / peaks * 100
    pct_beyond_2 = float((underwater > 2.0).mean() * 100)
    pct_beyond_10 = float((underwater > 10.0).mean() * 100)

    print(f"full history 2021-07 -> 2026-07   max drawdown  {dd_full:6.2f}%")
    print(f"test window  {WINDOW[0]} -> {WINDOW[1]}   max drawdown  {dd_win:6.2f}%"
          f"   buy & hold return {ret_win:+.1f}%")
    print(f"\nfraction of the window BTC spent more than  2% below its own peak: "
          f"{pct_beyond_2:5.1f}%")
    print(f"fraction of the window BTC spent more than 10% below its own peak: "
          f"{pct_beyond_10:5.1f}%")
    return {"dd_full_history_pct": dd_full, "dd_window_pct": dd_win,
            "buy_hold_return_pct": ret_win, "pct_time_beyond_2pct": pct_beyond_2}


# ---------------------------------------------------------------- 1.2

def fee_floor(candles_4h: np.ndarray) -> dict:
    rule("1.2  What the fees cost, next to the moves available")

    lo, hi = to_ms(WINDOW[0]), to_ms(WINDOW[1])
    win = candles_4h[(candles_4h[:, TS] >= lo) & (candles_4h[:, TS] < hi)]
    closes = win[:, CLOSE]

    print(f"round trip costs {ROUND_TRIP * 100:.3f}% of notional "
          f"({FEE * 100:.1f}% per side, Bybit spot)\n")
    print(f"{'hold':>6} {'median |move|':>14} {'P(|move| > fees)':>18} "
          f"{'median move / fees':>20}")
    rows = {}
    for bars in (1, 3, 6, 12, 30, 60):
        moves = closes[bars:] / closes[:-bars] - 1
        med = float(np.median(np.abs(moves)))
        beats = float((np.abs(moves) > ROUND_TRIP).mean())
        rows[bars] = {"median_abs_move": med, "p_beats_fees": beats}
        print(f"{bars:>4}b  {med * 100:>12.2f}% {beats * 100:>17.1f}% "
              f"{med / ROUND_TRIP:>19.1f}x")

    print("\n'hold' is in 4h bars: 6b = one day, 30b = five days.")
    print("A coin-flip entry captures none of this on average — the column that")
    print("matters is how much room there is above the toll, not how big moves get.")
    return rows


# ---------------------------------------------------------------- 1.3

def outcome_of_every_entry(candles_1m: np.ndarray, candles_4h: np.ndarray) -> np.ndarray:
    """Net return of entering at each 4h close and exiting on stop, target or timeout.

    Walks the real 1m candles so that a bar spanning both levels is resolved by
    which came first, rather than by assuming the convenient one. When a single
    1m candle touches both, the stop is taken: pessimistic, and unfalsifiable
    optimism is the more expensive mistake.
    """
    lo, hi = to_ms(WINDOW[0]), to_ms(WINDOW[1])
    entries = candles_4h[(candles_4h[:, TS] >= lo) & (candles_4h[:, TS] < hi)]

    m_ts = candles_1m[:, TS]
    m_high, m_low, m_close = candles_1m[:, HIGH], candles_1m[:, LOW], candles_1m[:, CLOSE]
    horizon = MAX_HOLD_DAYS * 1440

    results, timeouts = [], 0
    for row in entries:
        entry_ts = row[TS] + 4 * 3_600_000  # enter at the close of the 4h bar
        start = int(np.searchsorted(m_ts, entry_ts))
        if start >= len(m_ts) - 1:
            continue
        end = min(start + horizon, len(m_ts))
        entry = float(row[CLOSE])
        stop, target = entry * (1 - STOP_PCT), entry * (1 + TARGET_PCT)

        seg_low, seg_high = m_low[start:end], m_high[start:end]
        hit_stop = np.argmax(seg_low <= stop) if (seg_low <= stop).any() else -1
        hit_tgt = np.argmax(seg_high >= target) if (seg_high >= target).any() else -1

        if hit_stop == -1 and hit_tgt == -1:
            exit_price, timeouts = float(m_close[end - 1]), timeouts + 1
        elif hit_tgt == -1 or (hit_stop != -1 and hit_stop <= hit_tgt):
            exit_price = stop
        else:
            exit_price = target
        results.append((exit_price / entry) * (1 - FEE) ** 2 - 1)

    print(f"simulated {len(results)} entries, one at every 4h bar in the window "
          f"({timeouts} hit the {MAX_HOLD_DAYS}-day cap)")
    return np.array(results)


def random_baseline(outcomes: np.ndarray, n_trades: int, reps: int, rng) -> dict:
    rule(f"1.3  Baseline B2 — entering at random, {n_trades} trades, {reps} repetitions")

    wins = float((outcomes > 0).mean())
    print(f"entering at a random 4h bar and taking -{STOP_PCT * 100:.0f}% / "
          f"+{TARGET_PCT * 100:.0f}%, net of fees:")
    print(f"  hits target first   {wins * 100:5.1f}%")
    print(f"  mean net return per trade  {outcomes.mean() * 100:+.4f}%")
    print(f"  median                     {np.median(outcomes) * 100:+.4f}%")

    finals, dds = [], []
    for _ in range(reps):
        draw = rng.choice(outcomes, size=n_trades, replace=True)
        equity = np.concatenate([[1.0], np.cumprod(1 + draw)])
        finals.append(equity[-1] - 1)
        dds.append(max_drawdown(equity))
    finals, dds = np.array(finals) * 100, np.array(dds)

    print(f"\ncompounding {n_trades} such trades, full account each time:")
    print(f"  {'':14}{'p5':>9}{'median':>10}{'p95':>9}")
    print(f"  net return   {np.percentile(finals, 5):>8.1f}%"
          f"{np.median(finals):>9.1f}%{np.percentile(finals, 95):>8.1f}%")
    print(f"  max drawdown {np.percentile(dds, 5):>8.1f}%"
          f"{np.median(dds):>9.1f}%{np.percentile(dds, 95):>8.1f}%")
    print(f"\n  P(profitable) = {(finals > 0).mean() * 100:.1f}%")
    print(f"  P(max drawdown stays under 2%) = {(dds < 2.0).mean() * 100:.1f}%")

    return {
        "n_trades": n_trades, "reps": reps,
        "win_rate": wins,
        "mean_net_return_per_trade": float(outcomes.mean()),
        "final_return_pct": {"p5": float(np.percentile(finals, 5)),
                             "median": float(np.median(finals)),
                             "p95": float(np.percentile(finals, 95))},
        "max_drawdown_pct": {"p5": float(np.percentile(dds, 5)),
                             "median": float(np.median(dds)),
                             "p95": float(np.percentile(dds, 95))},
        "p_profitable": float((finals > 0).mean()),
        "p_drawdown_under_2pct": float((dds < 2.0).mean()),
    }


def compare_control_to_baseline(outcomes: np.ndarray, n_trades: int, rng) -> dict:
    """The actual B2 test: does choosing when to enter beat not choosing?

    Beating buy-and-hold is not evidence of timing skill. Beating entries drawn
    at random, at the same frequency and with the same exit rules, is the only
    comparison that isolates the entry decision.
    """
    rule("1.3b  Does ControlStrategy's entry timing beat random?")

    control_path = HERE / "results" / "ControlStrategy_4h.json"
    if not control_path.exists():
        print("no control result to compare")
        return {}
    control = json.loads(control_path.read_text())
    observed = control["trade_summary"]["net_pnl"] / control["starting_balance"] * 100
    observed_wr = control["trade_summary"]["win_rate"]

    finals = np.array([
        np.prod(1 + rng.choice(outcomes, size=n_trades, replace=True)) - 1
        for _ in range(10_000)
    ]) * 100
    percentile = float((finals < observed).mean() * 100)

    # Break-even hit rate for this exit geometry, net of the round trip.
    be = (STOP_PCT + ROUND_TRIP) / (STOP_PCT + TARGET_PCT)

    print(f"ControlStrategy, measured      {observed:+.2f}%  over {n_trades} trades")
    print(f"random entries, median          {np.median(finals):+.2f}%")
    print(f"random entries, 95th percentile {np.percentile(finals, 95):+.2f}%")
    print(f"\nControlStrategy sits at the {percentile:.1f}th percentile of random.")
    print(f"Passing requires the 95th. {'PASSES' if percentile >= 95 else 'DOES NOT PASS'}.")

    print(f"\nwin rate — random {(outcomes > 0).mean() * 100:.2f}%   "
          f"control {observed_wr * 100:.2f}%   break-even {be * 100:.2f}%")
    print("The whole game is those few tenths of a percentage point.")
    print("\nCaveat: this resamples outcomes independently, which discards the")
    print("clustering real returns have. A block bootstrap (roadmap P1-5) would")
    print("widen these bands, not narrow them — so the verdict cannot improve.")

    return {"control_return_pct": observed, "percentile_vs_random": percentile,
            "random_p95_pct": float(np.percentile(finals, 95)),
            "beats_baseline": bool(percentile >= 95),
            "break_even_win_rate": float(be),
            "random_win_rate": float((outcomes > 0).mean()),
            "control_win_rate": observed_wr}


def main() -> int:
    candles_4h = np.array(json.loads(DATA_4H.read_text()), dtype=float)
    candles_1m = np.load(DATA_1M)

    control = HERE / "results" / "ControlStrategy_4h.json"
    n_trades = 120
    if control.exists():
        n_trades = json.loads(control.read_text())["trade_summary"]["n"]

    report = {"window": WINDOW, "fee_per_side": FEE, "round_trip_cost": ROUND_TRIP}
    report["buy_and_hold"] = buy_and_hold(candles_4h)
    report["fee_floor"] = fee_floor(candles_4h)

    rule("1.3  Preparing the random baseline")
    outcomes = outcome_of_every_entry(candles_1m, candles_4h)
    report["random_baseline"] = random_baseline(
        outcomes, n_trades, 1000, np.random.default_rng(20260803)
    )
    report["control_vs_baseline"] = compare_control_to_baseline(
        outcomes, n_trades, np.random.default_rng(20260804)
    )

    out = HERE / "results" / "domain_measurement.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
