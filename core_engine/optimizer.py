import os
import json
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator

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

    def optimize_risk_parameters(self, max_iterations: int = 10) -> dict:
        """
        Runs an optimization loop to adjust strategy parameters until they meet risk constraints.
        
        Varies 'max_position_sizing_pct' and 'stop_loss_value' until 'validation_passed' is True.
        """
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

        for iteration in range(1, max_iterations + 1):
            print(f"\n[Iteration {iteration}] Testing params: Position Size = {pos_size:.3f}%, Stop Loss = {sl*100:.2f}%")

            # 1. Update blueprint in memory
            blueprint["risk"]["max_position_sizing_pct"] = pos_size
            blueprint["risk"]["stop_loss_value"] = sl

            # 2. Write updated blueprint back to disk
            with open(blueprint_path, "w", encoding="utf-8") as f:
                json.dump(blueprint, f, indent=2)

            # 3. Generate strategy code and format it
            self.bridge.generate_strategy_code(blueprint, force_clean=True)

            # 4. Run backtest (which triggers the static audit)
            result = self.bridge.execute_closed_loop(start_date="2026-01-01", end_date="2026-06-01")

            if result["status"] != "SUCCESS":
                print(f">> Backtest failed to run or failed audit: {result['status']}")
                continue

            metrics = result["metrics"]

            # 5. Validate metrics and run Monte Carlo Stress Test
            report = self.validator.generate_report(metrics, constraints, num_simulations=1000)
            best_report = report

            print(f">> Simulated Max Drawdown: {metrics['max_drawdown']:.2f}%")
            print(f">> Simulated Risk of Ruin: {report['monte_carlo_results']['risk_of_ruin']*100:.2f}%")
            print(f">> Validation Passed? {'YES' if report['validation_passed'] else 'NO'}")

            if report["validation_passed"]:
                print(f"\n>> SUCCESS: Found risk-compliant parameters at Iteration {iteration}!")
                print(f">> Final Position Size: {pos_size:.3f}%")
                print(f">> Final Stop Loss: {sl*100:.2f}%")
                return report

            # 6. Adjust parameters heuristically
            # Scale down position sizing first to reduce overall drawdown impact
            if pos_size > 0.1:
                pos_size = max(0.1, pos_size * 0.5)
            else:
                sl = max(0.005, sl * 0.8)

        print(f"\n>> Optimization finished after {max_iterations} iterations without perfect success.")
        return best_report
