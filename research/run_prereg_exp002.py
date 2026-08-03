"""EXP-002: cross-sectional momentum. Rules fixed in EXPERIMENT_REGISTER.md.

A different question from EXP-001. That one asked "when should I buy Bitcoin",
and the answer was that the timing edge in classic signals is the same size as
the fee. This one asks "which coins should I hold", rebalanced monthly, where
the dispersion between assets over a month is two orders of magnitude larger
than the round trip that captures it.

The baseline is picking K coins at random from the same eligible set at each
rebalance — not buy-and-hold, and not BTC. Beating BTC would only prove that
altcoins went up.

    .venv-jesse/Scripts/python.exe research/run_prereg_exp002.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
DATA = HERE / "data" / "bybit_spot_universe_D.json"
META = HERE / "data" / "bybit_spot_universe_D.meta.json"

# --- primary hypothesis: one configuration, fixed before running -------------
LOOKBACK_DAYS = 90
HOLD_K = 5
REBALANCE_DAYS = 28
MIN_TURNOVER_USD = 100_000  # median daily, over the lookback
FEE = 0.001                 # per side

WINDOW = ("2023-01-01", "2026-07-01")
MIN_PERIODS = 20
PASS_PERCENTILE = 95.0
N_REPS = 10_000

# Reported for information only. A cell of this grid clearing the bar is not a
# pass; if the primary fails and scattered cells succeed, that is evidence of
# parameter sensitivity, which is what noise looks like.
SENSITIVITY = [(l, k) for l in (30, 60, 90, 120) for k in (3, 5, 10)]

DAY_MS = 86_400_000


def to_ms(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def load_matrices():
    """Dates x symbols matrices of close price and USD turnover. NaN = not listed."""
    series = json.loads(DATA.read_text())
    symbols = sorted(series)
    all_ts = sorted({int(c[0]) for s in symbols for c in series[s]})
    ts_index = {t: i for i, t in enumerate(all_ts)}

    close = np.full((len(all_ts), len(symbols)), np.nan)
    turnover = np.full((len(all_ts), len(symbols)), np.nan)
    for j, s in enumerate(symbols):
        for c in series[s]:
            i = ts_index[int(c[0])]
            close[i, j] = c[2]
            turnover[i, j] = c[2] * c[5]  # close * base volume
    return np.array(all_ts, dtype=np.int64), np.array(symbols), close, turnover


def rebalance_dates(dates: np.ndarray, lookback: int) -> list[int]:
    lo, hi = to_ms(WINDOW[0]), to_ms(WINDOW[1])
    idx = [i for i, t in enumerate(dates) if lo <= t < hi]
    if not idx:
        return []
    start = idx[0]
    # Need `lookback` days of history before the first decision.
    while start < len(dates) and dates[start] - dates[0] < lookback * DAY_MS:
        start += 1
    out, i = [], start
    while i < len(dates) and dates[i] < hi:
        out.append(i)
        i += REBALANCE_DAYS
    return out


def eligible_at(i: int, close, turnover, lookback: int) -> np.ndarray:
    """Symbols tradeable at bar i: enough history, and enough liquidity."""
    j0 = i - lookback
    if j0 < 0:
        return np.array([], dtype=int)
    has_ends = np.isfinite(close[j0]) & np.isfinite(close[i]) & (close[j0] > 0)
    window = close[j0: i + 1]
    coverage = np.isfinite(window).mean(axis=0) > 0.9
    med_turnover = np.nanmedian(turnover[j0: i + 1], axis=0)
    liquid = np.nan_to_num(med_turnover, nan=0.0) >= MIN_TURNOVER_USD
    return np.where(has_ends & coverage & liquid)[0]


def forward_return(i: int, j: int, close, dates) -> float:
    """Return of symbol j from bar i to the next rebalance, last price if it stops."""
    end = min(i + REBALANCE_DAYS, len(dates) - 1)
    p0 = close[i, j]
    seg = close[i: end + 1, j]
    finite = seg[np.isfinite(seg)]
    if not np.isfinite(p0) or p0 <= 0 or finite.size == 0:
        return 0.0
    return float(finite[-1] / p0 - 1)


def run_portfolio(picks_per_period: list[np.ndarray], rebal: list[int], close, dates) -> np.ndarray:
    """Net period returns, charging fees only on the fraction of the book replaced."""
    rets, held = [], set()
    for period, (i, picks) in enumerate(zip(rebal, picks_per_period)):
        if len(picks) == 0:
            rets.append(0.0)
            continue
        gross = float(np.mean([forward_return(i, j, close, dates) for j in picks]))
        new = set(picks.tolist())
        replaced = 1.0 if period == 0 else len(new - held) / len(new)
        cost = replaced * 2 * FEE
        rets.append((1 + gross) * (1 - cost) - 1)
        held = new
    return np.array(rets)


def max_drawdown(equity: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity)
    return float(np.max((peaks - equity) / peaks) * 100)


def momentum_picks(rebal, close, turnover, dates, lookback, k):
    picks, sizes = [], []
    for i in rebal:
        elig = eligible_at(i, close, turnover, lookback)
        sizes.append(len(elig))
        if len(elig) < k:
            picks.append(np.array([], dtype=int))
            continue
        mom = close[i, elig] / close[i - lookback, elig] - 1
        picks.append(elig[np.argsort(mom)[::-1][:k]])
    return picks, sizes


def main() -> int:
    dates, symbols, close, turnover = load_matrices()
    meta = json.loads(META.read_text()) if META.exists() else {}
    rebal = rebalance_dates(dates, LOOKBACK_DAYS)

    def iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")

    print(f"EXP-002 · Bybit spot USDT universe · daily · {WINDOW[0]} -> {WINDOW[1]}")
    print(f"{len(symbols)} pairs in file, {len(rebal)} rebalance dates "
          f"({iso(dates[rebal[0]])} -> {iso(dates[rebal[-1]])})")
    print(f"primary: lookback {LOOKBACK_DAYS}d, hold top {HOLD_K}, "
          f"rebalance {REBALANCE_DAYS}d, min median turnover ${MIN_TURNOVER_USD:,}")
    print(f"pass bar: > {PASS_PERCENTILE}th percentile of random selection, "
          f"positive, and above equal-weight\n")

    if len(rebal) < MIN_PERIODS:
        print(f"only {len(rebal)} periods, need {MIN_PERIODS}. Cannot conclude.")
        return 1

    picks, elig_sizes = momentum_picks(rebal, close, turnover, dates, LOOKBACK_DAYS, HOLD_K)
    strat = run_portfolio(picks, rebal, close, dates)
    strat_eq = np.concatenate([[1.0], np.cumprod(1 + strat)])
    strat_net = (strat_eq[-1] - 1) * 100

    print(f"eligible universe per rebalance: min {min(elig_sizes)}, "
          f"median {int(np.median(elig_sizes))}, max {max(elig_sizes)}")

    # Baseline 1 — random K from the same eligible set. This is the bar.
    rng = np.random.default_rng(20260803)
    finals = np.empty(N_REPS)
    elig_cache = [eligible_at(i, close, turnover, LOOKBACK_DAYS) for i in rebal]
    fwd_cache = [
        {int(j): forward_return(i, int(j), close, dates) for j in e}
        for i, e in zip(rebal, elig_cache)
    ]
    for r in range(N_REPS):
        eq, held = 1.0, set()
        for period, (e, fwd) in enumerate(zip(elig_cache, fwd_cache)):
            if len(e) < HOLD_K:
                continue
            sel = rng.choice(e, size=HOLD_K, replace=False)
            gross = float(np.mean([fwd[int(j)] for j in sel]))
            new = set(int(j) for j in sel)
            replaced = 1.0 if period == 0 else len(new - held) / len(new)
            eq *= (1 + gross) * (1 - replaced * 2 * FEE)
            held = new
        finals[r] = (eq - 1) * 100
    percentile = float((finals < strat_net).mean() * 100)

    # Baseline 2 — hold the whole eligible universe, equal weight.
    ew = run_portfolio([e for e in elig_cache], rebal, close, dates)
    ew_net = (np.prod(1 + ew) - 1) * 100

    # Baseline 3 — BTC, bought and held.
    btc = int(np.where(symbols == "BTCUSDT")[0][0])
    btc_net = (close[rebal[-1], btc] / close[rebal[0], btc] - 1) * 100

    print(f"\n{'':26}{'net':>10}{'maxDD':>9}")
    print(f"{'cross-sectional momentum':<26}{strat_net:>9.1f}%{max_drawdown(strat_eq):>8.1f}%")
    print(f"{'random K, median':<26}{np.median(finals):>9.1f}%")
    print(f"{'random K, 95th pct':<26}{np.percentile(finals, 95):>9.1f}%")
    print(f"{'equal-weight universe':<26}{ew_net:>9.1f}%")
    print(f"{'BTC buy & hold':<26}{btc_net:>9.1f}%")

    beats_random = percentile > PASS_PERCENTILE
    passes = beats_random and strat_net > 0 and strat_net > ew_net
    print(f"\nstrategy sits at the {percentile:.1f}th percentile of random selection")
    print(f"  above {PASS_PERCENTILE}th percentile of random : {'yes' if beats_random else 'no'}")
    print(f"  positive net return                : {'yes' if strat_net > 0 else 'no'}")
    print(f"  above equal-weight universe        : {'yes' if strat_net > ew_net else 'no'}")
    print(f"\nVERDICT: {'PASS' if passes else 'FAIL'}")

    # Sensitivity — descriptive only, never a pass.
    print("\nsensitivity (information only, cannot constitute a pass)")
    print(f"  {'lookback':>9}{'K':>5}{'net':>10}{'pctile':>9}")
    grid = {}
    for lb, k in SENSITIVITY:
        rb = rebalance_dates(dates, lb)
        if len(rb) < MIN_PERIODS:
            continue
        pk, _ = momentum_picks(rb, close, turnover, dates, lb, k)
        r = run_portfolio(pk, rb, close, dates)
        net = (np.prod(1 + r) - 1) * 100
        grid[f"L{lb}_K{k}"] = round(net, 2)
        mark = "  <- primary" if (lb, k) == (LOOKBACK_DAYS, HOLD_K) else ""
        print(f"  {lb:>9}{k:>5}{net:>9.1f}%{'':>9}{mark}")

    out = HERE / "results" / "exp002.json"
    out.write_text(json.dumps({
        "experiment": "EXP-002", "window": WINDOW,
        "primary": {"lookback_days": LOOKBACK_DAYS, "hold_k": HOLD_K,
                    "rebalance_days": REBALANCE_DAYS,
                    "min_turnover_usd": MIN_TURNOVER_USD, "fee_per_side": FEE},
        "n_periods": len(rebal), "n_symbols_in_file": len(symbols),
        "eligible_per_rebalance": {"min": int(min(elig_sizes)),
                                   "median": int(np.median(elig_sizes)),
                                   "max": int(max(elig_sizes))},
        "strategy_net_pct": strat_net,
        "strategy_max_drawdown_pct": max_drawdown(strat_eq),
        "random_median_pct": float(np.median(finals)),
        "random_p95_pct": float(np.percentile(finals, 95)),
        "percentile_vs_random": percentile,
        "equal_weight_net_pct": ew_net, "btc_buy_hold_net_pct": btc_net,
        "passes": bool(passes),
        "sensitivity_net_pct": grid,
        "data_sha256": meta.get("sha256"),
        "survivorship_warning": meta.get("survivorship_warning"),
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
