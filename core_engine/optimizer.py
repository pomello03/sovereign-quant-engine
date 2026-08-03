"""Closed-loop search over risk parameters. Currently suspended.

Nothing in the pipeline invokes this module: `run_simulation.py` no longer calls
it and the copy of its loop that lived inside the SSE endpoint has been removed.
It is kept because the search may become meaningful later, not because it is
usable now.

Two reasons it is not usable now:

  - It selects on the window it reports. Shrinking position size until the
    verdict flips, then presenting that verdict as validation, is choosing a
    parameter on the evaluation set. Against the old mock metrics it was worse
    than that: drawdown was literally `-(pos_size * sl * 100 * 3)`, so the loop
    was inverting an equation it had itself written, and the committed
    `optimization_history` reproduces exactly.
  - Its central assumption is untested. Halving position size halves drawdown
    only if drawdown is linear in sizing. On real candles that has never been
    measured. Until P1-1 measures it, the heuristic has no ground.

See plans/ROADMAP_TO_CONTROLLED_LIVE.md P0-7.
"""

import os
import json
import warnings

from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator
from core_engine.state_io import atomic_write_json


class RiskOptimizer:
    def __init__(self, payload_drop_dir: str = None, workspace_path: str = None):
        """
        RiskOptimizer executes a closed-loop search for risk-compliant trading parameters.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.payload_drop_dir = payload_drop_dir or os.path.join(base_dir, "payload_drop")
        self.workspace_path = workspace_path or os.path.join(base_dir, "jesse_workspace")
        self.bridge = DeveloperBridge(
            payload_drop_dir=self.payload_drop_dir,
            workspace_path=self.workspace_path
        )
        self.validator = QuantValidator(payload_drop_dir=self.payload_drop_dir)
        # Chronological record of every optimization attempt (fed to the dashboard stepper)
        self.optimization_history = []

    def _read_strategy_code(self) -> str:
        """Returns the generated SovereignStrategy source, or None if not present."""
        code_path = os.path.join(
            self.workspace_path, "strategies", "SovereignStrategy", "__init__.py"
        )
        if os.path.exists(code_path):
            with open(code_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def optimize_risk_parameters(self, max_iterations: int = 10) -> dict:
        """
        Runs an optimization loop to adjust strategy parameters until they meet risk constraints.
        
        Varies 'max_position_sizing_pct' and 'stop_loss_value' until 'validation_passed' is True.
        """
        warnings.warn(
            "RiskOptimizer is suspended: it selects parameters on the same window it "
            "then reports them on. See plans/ROADMAP_TO_CONTROLLED_LIVE.md P0-7.",
            RuntimeWarning,
            stacklevel=2,
        )
        blueprint_path = os.path.join(self.payload_drop_dir, "strategy_blueprint.json")
        constraints_path = os.path.join(self.payload_drop_dir, "risk_constraints.json")

        if not os.path.exists(blueprint_path) or not os.path.exists(constraints_path):
            raise FileNotFoundError("Blueprint or risk constraints file not found.")

        with open(blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

        with open(constraints_path, "r", encoding="utf-8") as f:
            constraints = json.load(f)

        print(f"\n--- Starting Closed-Loop Parameter Optimization ---")
        print(f"Target Max Drawdown: < {constraints.get('max_drawdown_limit_pct')}%")

        # Initial values from the current blueprint
        pos_size = blueprint.get("risk", {}).get("max_position_sizing_pct", 2.0)
        sl = blueprint.get("risk", {}).get("stop_loss_value", 0.02)

        best_report = None
        self.optimization_history = []
        drawdown_limit = constraints.get("max_drawdown_limit_pct", 2.0)

        for iteration in range(1, max_iterations + 1):
            print(f"\n[Iteration {iteration}] Testing params: Position Size = {pos_size:.3f}%, Stop Loss = {sl*100:.2f}%")

            # 1. Update blueprint in memory
            blueprint["risk"]["max_position_sizing_pct"] = pos_size
            blueprint["risk"]["stop_loss_value"] = sl

            # 2. Write updated blueprint back to disk.
            # Atomically, so a dashboard reading concurrently never sees half a
            # file — the raw json.dump this replaces also bypassed the
            # Supervisor's Ruin Bias check, letting the loop write a blueprint
            # that would have been rejected had it arrived through the front door.
            if abs(sl) > 1.0 or pos_size <= 0 or sl <= 0:
                raise ValueError(
                    f"optimizer produced out-of-range risk parameters: "
                    f"pos_size={pos_size}, stop_loss={sl}"
                )
            atomic_write_json(blueprint_path, blueprint, indent=2)

            # 3. Generate strategy code and format it
            self.bridge.generate_strategy_code(blueprint, force_clean=True)

            # 4. Run backtest (which triggers the static audit)
            result = self.bridge.execute_closed_loop(start_date="2026-01-01", end_date="2026-06-01")

            if result["status"] != "SUCCESS":
                print(f">> Backtest failed to run or failed audit: {result['status']}")
                continue

            metrics = result["metrics"]

            # 5. Run Monte Carlo once (with trajectories) and record the attempt
            mc_results = self.validator.run_monte_carlo(
                metrics, num_simulations=1000, drawdown_limit=drawdown_limit,
                collect_trajectories=50
            )
            iteration_passed = self.validator.validate_with_monte_carlo(
                metrics, constraints, mc_results
            )
            self.optimization_history.append({
                "iteration": iteration,
                "params": {
                    "max_position_sizing_pct": round(pos_size, 4),
                    "stop_loss_value": round(sl, 4)
                },
                "metrics": {
                    key: metrics.get(key)
                    for key in ("sharpe_ratio", "max_drawdown", "profit_factor",
                                "total_trades", "win_rate")
                },
                "risk_of_ruin": mc_results["risk_of_ruin"],
                "average_max_drawdown": mc_results["average_max_drawdown"],
                "validation_passed": iteration_passed
            })

            # 6. Validate metrics and write report/dashboard (reusing the MC run)
            report = self.validator.generate_report(
                metrics, constraints, num_simulations=1000,
                optimization_history=self.optimization_history,
                strategy_code=self._read_strategy_code(),
                blueprint=blueprint,
                mc_results=mc_results
            )
            best_report = report

            print(f">> Simulated Max Drawdown: {metrics['max_drawdown']:.2f}%")
            print(f">> Simulated Risk of Ruin: {report['monte_carlo_results']['risk_of_ruin']*100:.2f}%")
            print(f">> Validation Passed? {'YES' if report['validation_passed'] else 'NO'}")

            if report["validation_passed"]:
                print(f"\n>> SUCCESS: Found risk-compliant parameters at Iteration {iteration}!")
                print(f">> Final Position Size: {pos_size:.3f}%")
                print(f">> Final Stop Loss: {sl*100:.2f}%")
                return report

            # 7. Adjust parameters heuristically
            # Scale down position sizing first to reduce overall drawdown impact
            if pos_size > 0.1:
                pos_size = max(0.1, pos_size * 0.5)
            else:
                sl = max(0.005, sl * 0.8)

        print(f"\n>> Optimization finished after {max_iterations} iterations without perfect success.")
        return best_report
