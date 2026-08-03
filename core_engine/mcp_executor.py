"""Runs a backtest against real market data, or explains why it cannot.

There is no mock path. The previous version of this module returned
``status: "SUCCESS"`` with fabricated metrics from four separate branches
whenever Jesse was missing, the CLI failed, or the candle database was empty,
and the fabricated numbers were arithmetic on the blueprint's own risk
parameters. Downstream code could not tell those numbers from measured ones,
so every verdict the project ever produced described its own configuration.

Two rules replace it:

1. ``SUCCESS`` requires candles. Anything else is ``NO_DATA`` with
   ``metrics: None``. An absent measurement is reported as absent.
2. Every result carries provenance. A caller that cannot prove where a number
   came from must be able to refuse it.

The backtest runs in-process through ``jesse.research.backtest()``, which
returns structured results including individual trades. The old version shelled
out to the CLI and scraped the report table with regexes that never extracted
per-trade returns — so the validator's bootstrap gate could only ever be
satisfied by the mock, and a real backtest was rejected by construction.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

STATUS_SUCCESS = "SUCCESS"
STATUS_NO_DATA = "NO_DATA"
STATUS_COMPILATION_ERROR = "COMPILATION_ERROR"
STATUS_ERROR = "ERROR"

DEFAULT_EXCHANGE = "Bybit Spot"
DEFAULT_SYMBOL = "BTC-USDT"
DEFAULT_TIMEFRAME = "4h"
DEFAULT_FEE_PER_SIDE = 0.001  # Bybit spot, non-VIP
DEFAULT_STARTING_BALANCE = 10_000
WARMUP_MINUTES = 30 * 1440


class MCPJesseRunner:
    def __init__(
        self,
        workspace_path: str,
        candles_path: Optional[str] = None,
        exchange: str = DEFAULT_EXCHANGE,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: str = DEFAULT_TIMEFRAME,
        fee_per_side: float = DEFAULT_FEE_PER_SIDE,
        starting_balance: float = DEFAULT_STARTING_BALANCE,
    ) -> None:
        self.workspace_path = os.path.abspath(workspace_path)
        self.project_root = os.path.dirname(self.workspace_path)
        self.candles_path = candles_path or os.path.join(
            self.project_root, "research", "data", "bybit_spot_BTCUSDT_1.npy"
        )
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.fee_per_side = fee_per_side
        self.starting_balance = starting_balance

    # ------------------------------------------------------------------ helpers

    def _strategy_file(self) -> str:
        return os.path.join(self.workspace_path, "strategies", "SovereignStrategy", "__init__.py")

    def _no_data(self, reason: str, **extra: Any) -> Dict[str, Any]:
        """The honest answer when no measurement is possible.

        ``metrics`` is None rather than an empty dict: a caller that does
        ``metrics.get('sharpe_ratio')`` should crash here, not silently read a
        missing value as an acceptable one.
        """
        return {
            "status": STATUS_NO_DATA,
            "metrics": None,
            "provenance": self._provenance(data_source=None),
            "reason": reason,
            "stdout": "",
            "stderr": "",
            **extra,
        }

    def _provenance(self, data_source: Optional[str], **extra: Any) -> Dict[str, Any]:
        strategy_file = self._strategy_file()
        strategy_hash = None
        if os.path.exists(strategy_file):
            with open(strategy_file, "rb") as fh:
                strategy_hash = hashlib.sha256(fh.read()).hexdigest()
        meta_path = os.path.splitext(self.candles_path)[0] + ".meta.json"
        data_fingerprint = None
        if data_source and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    data_fingerprint = json.load(fh).get("sha256")
            except (OSError, json.JSONDecodeError):
                data_fingerprint = None
        return {
            "data_source": data_source,
            "data_fingerprint": data_fingerprint,
            "candles_path": self.candles_path if data_source else None,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "fee_per_side": self.fee_per_side,
            "starting_balance": self.starting_balance,
            "strategy_sha256": strategy_hash,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            **extra,
        }

    def _check_strategy_compiles(self) -> Optional[str]:
        """Parse and compile the generated strategy.

        This replaces the old ruff/vulture/xenon subprocess gate, which mapped
        any non-zero exit to COMPILATION_ERROR — so an uninstalled linter was
        indistinguishable from broken generated code, and the bridge would
        regenerate perfectly valid code three times before giving up.
        Compiling the file answers the only question that gate really had.
        """
        path = self._strategy_file()
        if not os.path.exists(path):
            return f"generated strategy not found at {path}"
        try:
            with open(path, "r", encoding="utf-8") as fh:
                source = fh.read()
            ast.parse(source, filename=path)
            compile(source, path, "exec")
        except (SyntaxError, ValueError) as exc:
            return f"{type(exc).__name__}: {exc}"
        return None

    # ------------------------------------------------------------------- public

    def run_backtest(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Backtest the generated strategy over [start_date, end_date).

        Returns a dict with ``status``, ``metrics`` (None unless SUCCESS) and
        ``provenance``. ``SUCCESS`` is returned only when real candles were
        loaded and the simulation ran to completion.
        """
        compile_error = self._check_strategy_compiles()
        if compile_error:
            return {
                "status": STATUS_COMPILATION_ERROR,
                "metrics": None,
                "provenance": self._provenance(data_source=None),
                "reason": compile_error,
                "stdout": "",
                "stderr": compile_error,
            }

        try:
            import numpy as np
            from jesse import research
        except ImportError as exc:
            return self._no_data(
                f"jesse is not importable in this interpreter ({exc}). "
                "Real backtests run under .venv-jesse; see research/README.md."
            )

        if not os.path.exists(self.candles_path):
            return self._no_data(
                f"no candle file at {self.candles_path}. "
                "Fetch it with research/fetch_bybit_candles.py."
            )

        try:
            candles = np.load(self.candles_path)
            warmup, trading = self._split_window(candles, start_date, end_date)
        except (OSError, ValueError) as exc:
            return self._no_data(f"could not load candles: {exc}")

        if trading is None or len(trading) == 0:
            return self._no_data(
                f"candle file does not cover {start_date}..{end_date}"
            )
        if len(warmup) < WARMUP_MINUTES * 0.9:
            return self._no_data(
                f"only {len(warmup)} warm-up candles before {start_date}; "
                f"need about {WARMUP_MINUTES}. Indicators would warm up on the "
                "evaluation window itself."
            )

        try:
            result = self._run_jesse(research, warmup, trading)
        except Exception as exc:  # noqa: BLE001 - surfaced verbatim, never swallowed
            return {
                "status": STATUS_ERROR,
                "metrics": None,
                "provenance": self._provenance(data_source=None),
                "reason": f"{type(exc).__name__}: {exc}",
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
            }

        return result

    # ----------------------------------------------------------------- internal

    @staticmethod
    def _to_ms(date_str: str) -> int:
        return int(
            datetime.strptime(date_str, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .timestamp()
            * 1000
        )

    def _split_window(self, candles, start_date: str, end_date: str):
        start_ms, end_ms = self._to_ms(start_date), self._to_ms(end_date)
        warmup = candles[candles[:, 0] < start_ms]
        trading = candles[(candles[:, 0] >= start_ms) & (candles[:, 0] < end_ms)]
        return warmup, trading

    def _run_jesse(self, research, warmup, trading) -> Dict[str, Any]:
        from jesse_workspace.strategies.SovereignStrategy import SovereignStrategy

        key = f"{self.exchange}-{self.symbol}"
        config = {
            "starting_balance": self.starting_balance,
            "fee": self.fee_per_side,
            "type": "spot",
            "exchange": self.exchange,
            "warm_up_candles": 0,
        }
        routes = [
            {
                "exchange": self.exchange,
                "strategy": SovereignStrategy,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
            }
        ]
        payload = {key: {"exchange": self.exchange, "symbol": self.symbol, "candles": trading}}
        warm = {key: {"exchange": self.exchange, "symbol": self.symbol, "candles": warmup}}

        raw = research.backtest(config, routes, [], payload, warmup_candles=warm)
        jesse_metrics = raw.get("metrics") or {}
        trades = raw.get("trades") or []

        metrics = {
            "sharpe_ratio": jesse_metrics.get("sharpe_ratio"),
            "max_drawdown": jesse_metrics.get("max_drawdown"),
            "total_trades": int(jesse_metrics.get("total") or 0),
            "profit_factor": self._profit_factor(trades),
            "win_rate": jesse_metrics.get("win_rate"),
            # The reason this module exists. Without per-trade returns the
            # validator's bootstrap gate cannot be satisfied by real data at all.
            "trade_returns": [float(t["PNL"]) / self.starting_balance for t in trades],
            "net_profit": jesse_metrics.get("net_profit"),
            "total_fees": round(sum(float(t["fee"]) for t in trades), 2),
            "max_notional_pct_of_equity": (
                round(100 * max(float(t["size"]) for t in trades) / self.starting_balance, 2)
                if trades
                else None
            ),
        }

        return {
            "status": STATUS_SUCCESS,
            "metrics": metrics,
            "provenance": self._provenance(
                data_source="jesse",
                n_candles_1m=int(len(trading)),
                window_first=self._iso(trading[0][0]),
                window_last=self._iso(trading[-1][0]),
            ),
            "reason": None,
            "stdout": "",
            "stderr": "",
        }

    @staticmethod
    def _iso(ms: float) -> str:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()

    @staticmethod
    def _profit_factor(trades: list) -> Optional[float]:
        gross_win = sum(float(t["PNL"]) for t in trades if float(t["PNL"]) > 0)
        gross_loss = abs(sum(float(t["PNL"]) for t in trades if float(t["PNL"]) < 0))
        if not gross_loss:
            return None
        return round(gross_win / gross_loss, 4)
