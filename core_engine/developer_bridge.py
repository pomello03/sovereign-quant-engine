import os
import json
import ast
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
        params_content = self._generate_params_content(blueprint)
        params_path = os.path.join(strategy_dir, "params.py")
        with open(params_path, "w", encoding="utf-8") as f:
            f.write(params_content)
            
        # 2. Generate __init__.py
        init_content = self._generate_init_content(blueprint, inject_error)
        init_path = os.path.join(strategy_dir, "__init__.py")
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)

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
        formatted_params = pprint.pformat(params_dict, indent=4)
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
                if name_lower == 'close':
                    return ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='price',
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
            params_str = ", ".join(f"{k}={v}" for k, v in ind.get("params", {}).items())
            indicators_properties.append(f"""    @property
    def {name}(self) -> float:
        return ta.{name}(self.candles, {params_str})
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
from jesse.strategies import Strategy
import jesse.indicators as ta
from .params import params

class SovereignStrategy(Strategy):
    @property
    def current_regime(self) -> str:
        return '{regime_value}'

    @property
    def hyperparameters(self):
        if isinstance(params, dict) and 'default' in params:
            return params.get(self.current_regime, params.get('default', params))
        return params
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
        return True

    def go_long(self):
        qty = 1.0
        self.buy = qty, self.price

    def go_short(self):
        qty = 1.0
        self.sell = qty, self.price

    def update_position(self):
        pass
"""
