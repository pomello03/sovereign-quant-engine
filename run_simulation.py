# run_simulation.py
import argparse
import os
import json
from core_engine.supervisor import Supervisor
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator

# Window A of the two-window protocol: pick parameters here, then confirm them
# once on window B (2024-07-01 -> 2025-12-31), which must stay untouched until
# the parameters are frozen.
DEFAULT_START = "2023-01-01"
DEFAULT_END = "2024-06-30"

def main():
    parser = argparse.ArgumentParser(description="Sovereign Quant Engine - full pipeline run")
    parser.add_argument("--start", default=DEFAULT_START, help=f"backtest start date (default {DEFAULT_START})")
    parser.add_argument("--end", default=DEFAULT_END, help=f"backtest end date (default {DEFAULT_END})")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("=== Sovereign Quant Engine - Start Simulation ===")
    print(f"Backtest window: {args.start} -> {args.end}")
    
    # 1. Initialize Supervisor and generate blueprint
    print("\n[Step 1] Initializing Supervisor & Validating Phase 1 schemas...")
    try:
        supervisor = Supervisor()
        blueprint = supervisor.validate_and_generate()
        print(">> VERDICT: Approved!")
        print(f">> Blueprint successfully generated in: payload_drop/strategy_blueprint.json")
    except Exception as e:
        print(f"Error during validation: {e}")
        return

    # 2. Run Developer Bridge (Closed Loop simulation)
    print("\n[Step 2] Triggering Developer Bridge (Closed-Loop Strategy Generation)...")
    try:
        bridge = DeveloperBridge(
            payload_drop_dir=os.path.join(base_dir, "payload_drop"),
            workspace_path=os.path.join(base_dir, "jesse_workspace")
        )
        print(">> Generating Python strategy code inside jesse_workspace/strategies/SovereignStrategy/...")
        # Run closed loop (will use fallback mock values if Jesse CLI isn't installed locally)
        result = bridge.execute_closed_loop(start_date=args.start, end_date=args.end)
        print(f">> Execution Status: {result['status']}")
        if result['status'] == "SUCCESS":
            if result['metrics'].get("is_mock"):
                print("\n" + "!" * 70)
                print("!! ATTENZIONE: NUMERI FINTI. Jesse non ha eseguito nessun backtest.")
                print("!! Le metriche qui sotto sono calcolate dai parametri di rischio,")
                print("!! non misurate sul mercato. NON usarle per decidere nulla.")
                print("!" * 70 + "\n")
            print(f">> Backtest Metrics Extracted: {result['metrics']}")
        else:
            print(f">> Backtest failed. Logs:")
            print(f"Stdout: {result.get('stdout', '')}")
            print(f"Stderr: {result.get('stderr', '')}")
            return
    except Exception as e:
        print(f"Error during code generation/backtesting: {e}")
        return

    # 3. Validate Metrics & Run Monte Carlo Stress Test
    print("\n[Step 3] Running Quantitative Validation & Monte Carlo Stress Test...")
    try:
        validator = QuantValidator(payload_drop_dir=os.path.join(base_dir, "payload_drop"))
        metrics = result['metrics']
        
        # Load constraints
        with open(os.path.join(base_dir, "payload_drop", "risk_constraints.json"), "r") as f:
            constraints = json.load(f)
            
        # Read the generated strategy code for the dashboard code drawer
        strategy_code = None
        code_path = os.path.join(base_dir, "jesse_workspace", "strategies",
                                 "SovereignStrategy", "__init__.py")
        if os.path.exists(code_path):
            with open(code_path, "r", encoding="utf-8") as f:
                strategy_code = f.read()

        # Unified report generation (calls validation and Monte Carlo internally)
        report = validator.generate_report(metrics, constraints, num_simulations=1000,
                                           blueprint=blueprint, strategy_code=strategy_code)
        
        print(f">> Metrics meet risk constraints? {'YES' if report['validation_passed'] else 'NO'}")
        
        if not report['validation_passed']:
            print("\n[Step 3.5] Triggering Closed-Loop Risk Optimizer to tune parameters...")
            from core_engine.optimizer import RiskOptimizer
            optimizer = RiskOptimizer(
                payload_drop_dir=os.path.join(base_dir, "payload_drop"),
                workspace_path=os.path.join(base_dir, "jesse_workspace")
            )
            report = optimizer.optimize_risk_parameters(max_iterations=10)
            
        mc = report['monte_carlo_results']
        print(f"\n>> Final Estimated Risk of Ruin (Drawdown > {mc['drawdown_limit_used']}%): {mc['risk_of_ruin'] * 100:.2f}%")
        print(f">> Final Simulated Average Max Drawdown: {mc['average_max_drawdown']:.2f}%")
        print(f">> Final Simulated Peak Drawdown: {mc['peak_simulated_drawdown']:.2f}%")
        verdict = 'PASSED' if report['validation_passed'] else 'FAILED'
        if report.get("is_mock"):
            verdict += "  <-- SU DATI FINTI, non significa niente"
        print(f">> Final Validation Verdict: {verdict}")

        print(f">> Quantitative Report written to: payload_drop/validation_report.json")
        print("\n=== Simulation Completed Successfully! ===")
    except Exception as e:
        print(f"Error during validation/stress testing: {e}")

if __name__ == "__main__":
    main();
