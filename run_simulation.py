# run_simulation.py
import os
import json
from core_engine.supervisor import Supervisor
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("=== Sovereign Quant Engine - Start Simulation ===")
    
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
        result = bridge.execute_closed_loop(start_date="2026-01-01", end_date="2026-06-01")
        print(f">> Execution Status: {result['status']}")
        if result['status'] == "SUCCESS":
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
            
        # Unified report generation (calls validation and Monte Carlo internally)
        report = validator.generate_report(metrics, constraints, num_simulations=1000)
        
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
        print(f">> Final Validation Verdict: {'PASSED' if report['validation_passed'] else 'FAILED'}")
        
        print(f">> Quantitative Report written to: payload_drop/validation_report.json")
        print("\n=== Simulation Completed Successfully! ===")
    except Exception as e:
        print(f"Error during validation/stress testing: {e}")

if __name__ == "__main__":
    main();
