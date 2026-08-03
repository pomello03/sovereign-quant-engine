"""Run a strategy against real candles via jesse.research.backtest().

Everything the old pipeline lacked is here by construction:

  - the candles are real, and the report says which ones (sha256, window, source);
  - there is no mock path, so "no data" cannot be mistaken for "no problem";
  - individual trade PnLs are extracted, not just the summary table, because the
    summary alone cannot tell a lucky run from a repeatable one;
  - fees are charged at the venue's real rate and every metric is reported net;
  - zero trades is reported as NO_TRADES, never as a pass.

Run with the isolated interpreter:

    .venv-jesse/Scripts/python.exe research/run_backtest.py --strategy SpecStrategy
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from jesse import research  # noqa: E402
from strategies.ControlStrategy import ControlStrategy  # noqa: E402
from strategies.SpecStrategy import SpecStrategy  # noqa: E402

STRATEGIES = {"SpecStrategy": SpecStrategy, "ControlStrategy": ControlStrategy}

EXCHANGE = "Bybit Spot"
SYMBOL = "BTC-USDT"
FEE = 0.001  # Bybit spot, non-VIP, per side. exchange_info agrees.
STARTING_BALANCE = 10_000

DATA_1M = HERE / "data" / "bybit_spot_BTCUSDT_1.npy"
META_1M = HERE / "data" / "bybit_spot_BTCUSDT_1.meta.json"
OUT_DIR = HERE / "results"


def load_candles(warmup_days: int, start: str | None, end: str | None):
    """Split the 1m series into an explicit warm-up block and a trading block.

    The split is explicit rather than implicit so that a reader can tell which
    candles were allowed to influence indicator state and which ones the
    strategy actually traded. An indicator that silently warms up on the first
    bars of the evaluation window has already seen part of its own test set.
    """
    if not DATA_1M.exists():
        raise SystemExit(
            f"missing {DATA_1M}\nrun: python research/fetch_bybit_candles.py "
            "--interval 1 --format npy --start 2023-12-01 --end 2026-08-01"
        )
    candles = np.load(DATA_1M)

    def to_ms(d: str) -> int:
        return int(
            datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
        )

    trade_start = to_ms(start) if start else int(candles[0][0]) + warmup_days * 86_400_000
    trade_end = to_ms(end) if end else int(candles[-1][0]) + 1

    warmup = candles[(candles[:, 0] < trade_start)]
    trading = candles[(candles[:, 0] >= trade_start) & (candles[:, 0] < trade_end)]

    if len(warmup) < warmup_days * 1440 * 0.9:
        raise SystemExit(f"not enough warm-up candles: {len(warmup)}")
    if len(trading) == 0:
        raise SystemExit("empty trading window")
    return warmup, trading


def summarize_trades(trades: list[dict], starting_balance: float) -> dict:
    """Per-trade returns, expressed as a fraction of the balance at risk.

    These are the samples a bootstrap needs. The old pipeline never produced
    them, which is why its statistical gate could only ever be satisfied by
    fabricated data.
    """
    if not trades:
        return {"n": 0}
    pnls = [float(t["PNL"]) for t in trades]
    returns = [p / starting_balance for p in pnls]
    fees = [float(t["fee"]) for t in trades]
    sizes = [float(t["size"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    total_fees = sum(fees)
    gross_pnl = sum(pnls) + total_fees
    return {
        "n": len(trades),
        "net_pnl": round(sum(pnls), 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_fees": round(total_fees, 2),
        # How much of the edge the venue keeps. Above 1.0 the strategy is
        # profitable before costs and unprofitable after them.
        "fees_over_gross_pnl": round(total_fees / abs(gross_pnl), 4) if gross_pnl else None,
        "win_rate": round(len(wins) / len(trades), 4),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else None,
        "avg_return_per_trade": round(sum(returns) / len(returns), 6),
        "expectancy_pct_of_equity": round(100 * sum(returns) / len(returns), 4),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        # Position size relative to starting equity. risk_constraints.json pairs a
        # 2% stop with 2% risk per trade, which arithmetically implies deploying
        # the whole account on every entry.
        "max_notional_pct_of_equity": round(100 * max(sizes) / starting_balance, 2),
        "avg_notional_pct_of_equity": round(100 * (sum(sizes) / len(sizes)) / starting_balance, 2),
        "returns": [round(r, 8) for r in returns],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strategy", default="SpecStrategy", choices=sorted(STRATEGIES))
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--warmup-days", type=int, default=30)
    p.add_argument("--start", default=None, help="trading window start, YYYY-MM-DD")
    p.add_argument("--end", default=None, help="trading window end, YYYY-MM-DD")
    p.add_argument("--inspect", action="store_true", help="dump the raw result structure")
    args = p.parse_args()

    warmup, trading = load_candles(args.warmup_days, args.start, args.end)
    meta = json.loads(META_1M.read_text()) if META_1M.exists() else {}

    def when(ms: float) -> str:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")

    print(f"strategy   {args.strategy}   {EXCHANGE} {SYMBOL} {args.timeframe}")
    print(f"warm-up    {len(warmup):>9} 1m candles  {when(warmup[0][0])} -> {when(warmup[-1][0])}")
    print(f"trading    {len(trading):>9} 1m candles  {when(trading[0][0])} -> {when(trading[-1][0])}")
    print(f"fee        {FEE} per side   balance {STARTING_BALANCE}\n")

    key = f"{EXCHANGE}-{SYMBOL}"
    config = {
        "starting_balance": STARTING_BALANCE,
        "fee": FEE,
        "type": "spot",
        "exchange": EXCHANGE,
        "warm_up_candles": 0,  # supplied explicitly below
    }
    routes = [
        {
            "exchange": EXCHANGE,
            "strategy": STRATEGIES[args.strategy],
            "symbol": SYMBOL,
            "timeframe": args.timeframe,
        }
    ]
    candles = {key: {"exchange": EXCHANGE, "symbol": SYMBOL, "candles": trading}}
    warmup_candles = {key: {"exchange": EXCHANGE, "symbol": SYMBOL, "candles": warmup}}

    result = research.backtest(
        config, routes, [], candles, warmup_candles=warmup_candles, generate_equity_curve=True
    )

    if args.inspect:
        print("=== raw result keys ===")
        for k, v in result.items():
            print(f"  {k}: {type(v).__name__}"
                  + (f" len={len(v)}" if hasattr(v, "__len__") else ""))
        print("\n=== metrics ===")
        print(json.dumps(result.get("metrics", {}), indent=2, default=str))

    metrics = result.get("metrics") or {}
    trades = result.get("trades") or []
    n_trades = int(metrics.get("total") or 0)

    print("=" * 62)
    if n_trades == 0:
        print("VERDICT: NO_TRADES")
        print("The strategy never opened a position on this window.")
        print("There is nothing to validate. This is not a pass and not a failure —")
        print("it is the absence of a measurement.")
    summary = summarize_trades(trades, STARTING_BALANCE)
    if n_trades:
        print(f"trades              {n_trades}")
        print(f"net profit          {metrics.get('net_profit'):.2f} "
              f"({metrics.get('net_profit_percentage'):.2f}%)")
        print(f"gross / net PnL     {summary['gross_pnl']:.2f} / {summary['net_pnl']:.2f}")
        print(f"fees paid           {summary['total_fees']:.2f}  "
              f"({summary['fees_over_gross_pnl']} x gross PnL)")
        print(f"max drawdown        {metrics.get('max_drawdown'):.2f}%")
        print(f"sharpe              {metrics.get('sharpe_ratio')}")
        print(f"win rate            {metrics.get('win_rate')}")
        print(f"expectancy/trade    {summary['expectancy_pct_of_equity']}% of equity")
        print(f"max notional        {summary['max_notional_pct_of_equity']}% of equity")
    print("=" * 62)

    report = {
        "verdict": "NO_TRADES" if n_trades == 0 else "MEASURED",
        "data_source": "bybit-public-api",
        "data_sha256": meta.get("sha256"),
        "data_window": {"first": when(trading[0][0]), "last": when(trading[-1][0])},
        "warmup_window": {"first": when(warmup[0][0]), "last": when(warmup[-1][0])},
        "n_candles_1m": int(len(trading)),
        "exchange": EXCHANGE,
        "symbol": SYMBOL,
        "timeframe": args.timeframe,
        "fee_per_side": FEE,
        "starting_balance": STARTING_BALANCE,
        "strategy": args.strategy,
        "strategy_sha256": hashlib.sha256(
            (HERE / "strategies" / f"{args.strategy}.py").read_bytes()
        ).hexdigest(),
        "jesse_version": __import__("importlib.metadata", fromlist=["version"]).version("jesse"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": {k: v for k, v in metrics.items() if not isinstance(v, (list, dict))},
        "trade_summary": summary,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.strategy}_{args.timeframe}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
