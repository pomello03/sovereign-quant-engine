import os
import json
import ast
import shutil
from typing import Dict, Any, List
from core_engine.supervisor import Supervisor
from core_engine.mcp_executor import MCPJesseRunner

class DeveloperBridge:
    def __init__(
        self, 
        supervisor: Supervisor = None, 
        runner: MCPJesseRunner = None, 
        workspace_path: str = None, 
        payload_drop_dir: str = None
    ):
        """
        DeveloperBridge coordinates code generation and backtest execution.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.payload_drop_dir = payload_drop_dir or os.path.join(base_dir, "payload_drop")
        self.workspace_path = workspace_path or os.path.join(base_dir, "jesse_workspace")
        
        self.supervisor = supervisor or Supervisor(payload_drop_dir=self.payload_drop_dir)
        self.runner = runner or MCPJesseRunner(workspace_path=self.workspace_path)
        
        # Internal state for testing and error simulation
        self.simulate_compilation_error_on_first_try = False

    def load_blueprint(self) -> dict:
        """
        Loads the approved strategy blueprint from the payload_drop directory.
        """
        blueprint_path = os.path.join(self.payload_drop_dir, "strategy_blueprint.json")
        if not os.path.exists(blueprint_path):
            raise FileNotFoundError(f"Strategy blueprint not found at {blueprint_path}")
        with open(blueprint_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_strategy_code(self, blueprint: dict, force_clean: bool = False):
        """
        Writes a Python base strategy class (Jesse-compliant) and its params.py
        to jesse_workspace/strategies/SovereignStrategy/
        
        Args:
            blueprint: Dict containing the strategy blueprint
            force_clean: If True, ignores self.simulate_compilation_error_on_first_try
        """
        strategy_dir = os.path.join(self.workspace_path, "strategies", "SovereignStrategy")
        os.makedirs(strategy_dir, exist_ok=True)
        
        inject_error = self.simulate_compilation_error_on_first_try and not force_clean
        
        # 1. Generate params.py
        params_content = self._strip_trailing_whitespace(self._generate_params_content(blueprint))
        params_path = os.path.join(strategy_dir, "params.py")
        with open(params_path, "w", encoding="utf-8") as f:
            f.write(params_content)

        # 2. Generate __init__.py
        init_content = self._strip_trailing_whitespace(
            self._generate_init_content(blueprint, inject_error)
        )
        init_path = os.path.join(strategy_dir, "__init__.py")
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)

        # 3. Format and clean generated code using Ruff if installed.
        # Prefer the `ruff` on PATH over `python -m ruff`: ruff is commonly
        # installed globally rather than in the project venv, in which case
        # `sys.executable -m ruff` fails silently and the generated code ships
        # unformatted. This mirrors run_tool() in bin/sqe-audit.sh.
        if "PYTEST_CURRENT_TEST" not in os.environ:
            try:
                import subprocess
                import sys
                ruff_exe = shutil.which("ruff")
                ruff_cmd = [ruff_exe] if ruff_exe else [sys.executable, "-m", "ruff"]
                subprocess.run(ruff_cmd + ["check", "--select", "F,E,W,I,U", "--fix", strategy_dir], capture_output=True)
                subprocess.run(ruff_cmd + ["format", strategy_dir], capture_output=True)
            except Exception:
                pass

    def execute_closed_loop(self, start_date: str, end_date: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Executes the backtest; in case of COMPILATION_ERROR, corrects the code and retries.
        
        Args:
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            max_retries: Maximum attempts to execute and correct
            
        Returns:
            Dict containing the final backtest result and details of attempts.
        """
        blueprint = self.load_blueprint()
        self.generate_strategy_code(blueprint)
        
        attempts_log = []
        final_res = {}
        
        for attempt in range(1, max_retries + 1):
            res = self.runner.run_backtest(start_date, end_date)
            attempts_log.append({
                "attempt": attempt,
                "status": res["status"],
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", "")
            })
            
            final_res = res
            
            if res["status"] == "COMPILATION_ERROR":
                if attempt < max_retries:
                    # Corrective action: regenerate clean code (fixing simulation or template)
                    self.generate_strategy_code(blueprint, force_clean=True)
                    # Turn off simulation error for future retries
                    self.simulate_compilation_error_on_first_try = False
                    continue
                else:
                    break
            else:
                break
                
        return {
            "status": final_res.get("status", "ERROR"),
            "metrics": final_res.get("metrics"),
            "attempts": attempts_log,
            "stdout": final_res.get("stdout", ""),
            "stderr": final_res.get("stderr", "")
        }

    @staticmethod
    def _strip_trailing_whitespace(source: str) -> str:
        """Removes trailing whitespace per line so generated code passes ruff W291/W293."""
        return "\n".join(line.rstrip() for line in source.split("\n"))

    @staticmethod
    def _min_candles_for(params: dict) -> int:
        """Minimum candle history a getter needs before its indicator is valid."""
        periods = [v for v in params.values() if isinstance(v, (int, float))]
        return int(max(periods)) + 1 if periods else 20

    @staticmethod
    def _fallback_for(name: str) -> str:
        """Safe cold-start fallback expression for an indicator getter by family."""
        if "rsi" in name:
            return "50.0"  # neutral oscillator midpoint
        if name in ("atr", "natr", "tr") or name.startswith("atr"):
            return "(self.price * 0.01)"  # small positive value, avoids div-by-zero in sizing
        return "self.price"  # price-tracking indicators (sma, ema, ...)

    def _generate_params_content(self, blueprint: dict) -> str:
        alpha = blueprint.get("alpha", {})
        risk = blueprint.get("risk", {})
        context = blueprint.get("context", {})
        regime = context.get("market_regime")
        
        indicators_params = {}
        for ind in alpha.get("indicators", []):
            indicators_params[ind["name"]] = ind.get("params", {})
            
        base_params = {
            "indicators": indicators_params,
            "risk": {
                "max_drawdown_limit_pct": risk.get("max_drawdown_limit_pct"),
                "stop_loss_type": risk.get("stop_loss_type"),
                "stop_loss_value": risk.get("stop_loss_value"),
                "max_position_sizing_pct": risk.get("max_position_sizing_pct"),
            }
        }
        
        if regime:
            params_dict = {
                "default": base_params,
                regime: base_params,
            }
        else:
            params_dict = base_params
        
        import pprint
        # width=70 keeps every wrapped line within the ruff E501 limit (88)
        # even after the "params = " prefix is prepended to the first line
        formatted_params = pprint.pformat(params_dict, indent=4, width=70)
        return (
            "# Automatically generated by Sovereign Quant Engine\n"
            f"params = {formatted_params}\n"
        )

    def _translate_condition(self, condition: str, indicators: list) -> str:
        """Translates a human-readable condition to Python code using AST parsing.
        
        Safely rewrites indicator names and 'close' to self.attribute references.
        Rejects function calls and attribute access to prevent code injection.
        
        Args:
            condition: A string expression like 'rsi < 30'
            indicators: List of indicator dicts with 'name' keys
            
        Returns:
            Translated Python expression string
            
        Raises:
            ValueError: If the condition contains invalid syntax or unsafe constructs
        """
        indicator_names = {ind["name"].lower() for ind in indicators}
        
        try:
            tree = ast.parse(condition, mode='eval')
        except SyntaxError as e:
            raise ValueError(f"Invalid condition syntax: {condition}") from e
        
        class _ConditionTransformer(ast.NodeTransformer):
            def visit_Name(self, node):
                name_lower = node.id.lower()
                # Known Jesse price fields -> self.attribute
                jesse_price_fields = {'open': 'open', 'high': 'high', 'low': 'low', 'close': 'price', 'volume': 'volume'}
                if name_lower in jesse_price_fields:
                    return ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr=jesse_price_fields[name_lower],
                        ctx=ast.Load()
                    )
                if name_lower in indicator_names:
                    return ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr=name_lower,
                        ctx=ast.Load()
                    )
                return node
            
            def visit_Call(self, node):
                raise ValueError(f"Function calls are not allowed in conditions: {ast.dump(node)}")
            
            def visit_Attribute(self, node):
                raise ValueError(f"Attribute access is not allowed in conditions: {ast.dump(node)}")
        
        transformer = _ConditionTransformer()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        
        return ast.unparse(new_tree)

    def _generate_init_content(self, blueprint: dict, inject_error: bool = False) -> str:
        if inject_error:
            # Intentionally miss the colon in the class definition to cause a SyntaxError / COMPILATION_ERROR
            return (
                "# Automatically generated strategy with intentional syntax error\n"
                "from jesse.strategies import Strategy\n\n"
                "class SovereignStrategy(Strategy)\n"
                "    def should_long(self) -> bool:\n"
                "        return True\n"
            )
            
        alpha = blueprint.get("alpha", {})
        context = blueprint.get("context", {})
        strategy_name = alpha.get("strategy_name", "SovereignStrategy")
        long_conditions = alpha.get("entry_long_conditions", [])
        short_conditions = alpha.get("entry_short_conditions", [])
        regime_value = context.get("market_regime", "default")

        long_conds_str = "\n        # ".join(long_conditions)
        short_conds_str = "\n        # ".join(short_conditions)

        indicators_properties = []
        for ind in alpha.get("indicators", []):
            name = ind["name"].lower()
            params = ind.get("params", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            call = f"ta.{name}(self.candles, {params_str})" if params_str else f"ta.{name}(self.candles)"
            min_candles = self._min_candles_for(params)
            fallback_expr = self._fallback_for(name)
            # Robust getter: validates candle history length and rejects NaN/None,
            # falling back to a safe constant during cold start (Vuln 2).
            indicators_properties.append(f"""    @property
    def {name}(self) -> float:
        return self._safe_indicator(
            lambda: {call},
            min_candles={min_candles}, fallback={fallback_expr},
        )
""")
        properties_str = "\n".join(indicators_properties)

        translated_long = [self._translate_condition(c, alpha.get("indicators", [])) for c in long_conditions]
        translated_short = [self._translate_condition(c, alpha.get("indicators", [])) for c in short_conditions]
        
        if translated_long:
            should_long_body = "return " + " and ".join(translated_long)
        else:
            should_long_body = "return True"
            
        if translated_short:
            should_short_body = "return " + " and ".join(translated_short)
        else:
            should_short_body = "return False"
        
        return f"""# Automatically generated by Sovereign Quant Engine
# Strategy Name: {strategy_name}
import jesse.indicators as ta
from jesse.strategies import Strategy

from .params import params


class SovereignStrategy(Strategy):
    # Minimum exchange-API move (fraction of price) before re-sending a stop
    # order, to avoid order-modification spamming and HTTP 429 bans (Vuln 4).
    TRAIL_MIN_MOVE_PCT = 0.002

    def __init__(self):
        super().__init__()
        # Historical price extreme tracked for a unidirectional trailing stop.
        self._trail_peak = None
        self._last_sent_sl = None

    @property
    def current_regime(self) -> str:
        return '{regime_value}'

    @property
    def hyperparameters(self):
        if isinstance(params, dict) and 'default' in params:
            return params.get(self.current_regime, params.get('default', params))
        return params

    @staticmethod
    def _is_valid_number(value) -> bool:
        # Rejects None, NaN (value != value) and +/-inf.
        return (
            isinstance(value, (int, float))
            and value == value
            and value not in (float('inf'), float('-inf'))
        )

    def _safe_indicator(self, calc, min_candles: int, fallback: float) -> float:
        # Guards indicator getters against cold-start NaN/None propagation (Vuln 2).
        if self.candles is None or len(self.candles) < min_candles:
            return fallback
        try:
            value = calc()
        except Exception:
            return fallback
        return self._coerce_number(value, fallback)

    def _coerce_number(self, value, fallback: float) -> float:
        # Reduces a possible series to its last element, then validates it.
        if hasattr(value, '__len__'):
            value = value[-1] if len(value) else fallback
        return value if self._is_valid_number(value) else fallback
{properties_str}
    def should_long(self) -> bool:
        # Long entry conditions:
        # {long_conds_str}
        {should_long_body}

    def should_short(self) -> bool:
        # Short entry conditions:
        # {short_conds_str}
        {should_short_body}

    def should_cancel_entry(self) -> bool:
        return False

    @property
    def atr(self) -> float:
        # Robust ATR getter: positive fallback avoids div-by-zero in sizing.
        return self._safe_indicator(
            lambda: ta.atr(self.candles),
            min_candles=20, fallback=(self.price * 0.01),
        )

    def _stop_distance(self, ref_price: float = None) -> float:
        # Single source of truth for how far the stop sits from entry. Sizing and
        # the stop order MUST read the same number: if sizing assumes ATR*2 while
        # the stop is placed at a fixed percentage, the risk actually taken per
        # trade is not max_position_sizing_pct but an arbitrary function of
        # volatility.
        ref = ref_price if self._is_valid_number(ref_price) else self.price
        risk = self.hyperparameters['risk']
        if risk.get('stop_loss_type', 'fixed') == 'atr':
            return self.atr * 2
        return ref * risk['stop_loss_value']

    def _position_qty(self) -> float:
        # Risk-based sizing with a NaN/zero-safe fallback (Vuln 2):
        # risk amount = capital * max_position_sizing_pct / 100, and that amount
        # is what is lost if the stop is hit, so qty = risk / stop distance.
        try:
            risk_pct = self.hyperparameters['risk']['max_position_sizing_pct'] / 100.0
            qty = (self.capital * risk_pct) / self._stop_distance()
        except Exception:
            qty = None
        if not self._is_valid_number(qty) or qty <= 0:
            # Fallback to default sizing if indicators/candles aren't fully loaded.
            qty = self.capital / self.price
        return qty

    def go_long(self):
        qty = self._position_qty()
        self.buy = qty, self.price
        sl_value = self.hyperparameters['risk']['stop_loss_value']
        tp_value = self.hyperparameters['risk'].get('take_profit_value', sl_value * 2)
        self.stop_loss = qty, self.price - self._stop_distance()
        self.take_profit = qty, self.price * (1 + tp_value)

    def go_short(self):
        qty = self._position_qty()
        self.sell = qty, self.price
        sl_value = self.hyperparameters['risk']['stop_loss_value']
        tp_value = self.hyperparameters['risk'].get('take_profit_value', sl_value * 2)
        self.stop_loss = qty, self.price + self._stop_distance()
        self.take_profit = qty, self.price * (1 - tp_value)

    def _update_trailing_stop(self):
        # Trailing stop hardened against API spamming and direction violation (Vuln 4):
        # track the historical price extreme, derive the stop from it (so it only
        # moves favourably), and re-send only past TRAIL_MIN_MOVE_PCT. Logic is
        # split into small helpers to keep cyclomatic complexity low.
        if self.is_long:
            self._trail_side(is_long=True)
        elif self.is_short:
            self._trail_side(is_long=False)
        else:
            self._trail_peak = None      # flat: reset state for the next position
            self._last_sent_sl = None

    def _trail_side(self, is_long: bool):
        self._update_peak(is_long)
        new_sl = self._trailing_sl(is_long)
        # Unidirectional + throttled: never move against the position, and only
        # re-send the order past TRAIL_MIN_MOVE_PCT.
        favorable = self._is_favorable_move(new_sl, is_long)
        if favorable and self._should_resend_stop(new_sl):
            self.stop_loss = self.position.qty, new_sl
            self._last_sent_sl = new_sl

    def _update_peak(self, is_long: bool):
        if self._trail_peak is None or self._is_new_extreme(is_long):
            self._trail_peak = self.price

    def _trailing_sl(self, is_long: bool) -> float:
        # Same stop distance as entry sizing, measured from the price extreme.
        distance = self._stop_distance(self._trail_peak)
        return self._trail_peak - distance if is_long else self._trail_peak + distance

    def _is_new_extreme(self, is_long: bool) -> bool:
        peak = self._trail_peak
        return self.price > peak if is_long else self.price < peak

    def _is_favorable_move(self, new_sl: float, is_long: bool) -> bool:
        if self._last_sent_sl is None:
            return True
        return new_sl > self._last_sent_sl if is_long else new_sl < self._last_sent_sl

    def _should_resend_stop(self, new_sl: float) -> bool:
        # Throttles exchange order modifications to avoid HTTP 429 bans.
        if self._last_sent_sl is None:
            return True
        return abs(new_sl - self._last_sent_sl) / self.price >= self.TRAIL_MIN_MOVE_PCT

    def _update_atr_stop(self):
        distance = self._stop_distance()
        if self.is_long:
            self.stop_loss = self.position.qty, self.price - distance
        elif self.is_short:
            self.stop_loss = self.position.qty, self.price + distance

    def update_position(self):
        # Dynamic stop-loss management based on stop_loss_type
        sl_type = self.hyperparameters['risk'].get('stop_loss_type', 'fixed')
        if sl_type == 'trailing':
            self._update_trailing_stop()
        elif sl_type == 'atr':
            self._update_atr_stop()
"""
