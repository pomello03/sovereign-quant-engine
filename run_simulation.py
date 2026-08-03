"""CLI entry point: blueprint -> strategy code -> backtest -> validation.

Exit codes are meaningful, because a caller that cannot distinguish "passed"
from "never measured" will eventually treat them the same:

    0  measured, and the result satisfies the constraints
    1  measured, and the result does not satisfy the constraints
    2  no measurement was possible (no data, no framework, bad window)
    3  the run itself failed

The previous version returned 0 in all four cases.
"""

import argparse
import json
import os
import sys

from core_engine.developer_bridge import DeveloperBridge
from core_engine.mcp_executor import STATUS_NO_DATA, STATUS_SUCCESS
from core_engine.quant_validator import QuantValidator
from core_engine.supervisor import Supervisor

EXIT_PASSED, EXIT_FAILED, EXIT_NO_DATA, EXIT_ERROR = 0, 1, 2, 3


def main() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2024-01-01", help="backtest window start (YYYY-MM-DD)")
    p.add_argument("--end", default="2026-07-01", help="backtest window end (YYYY-MM-DD)")
    args = p.parse_args()

    print("=== Sovereign Quant Engine ===")

    print("\n[1] Supervisor: schema validation and blueprint generation")
    try:
        blueprint = Supervisor().validate_and_generate()
        print(">> approved; wrote payload_drop/strategy_blueprint.json")
    except Exception as exc:
        print(f">> validation failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    print(f"\n[2] Developer Bridge: code generation and backtest {args.start} -> {args.end}")
    try:
        bridge = DeveloperBridge(
            payload_drop_dir=os.path.join(base_dir, "payload_drop"),
            workspace_path=os.path.join(base_dir, "jesse_workspace"),
        )
        result = bridge.execute_closed_loop(start_date=args.start, end_date=args.end)
    except Exception as exc:
        print(f">> bridge failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    print(f">> status: {result['status']}")
    if result["status"] != STATUS_SUCCESS:
        if result.get("reason"):
            print(f">> reason: {result['reason']}")
        for stream in ("stdout", "stderr"):
            if result.get(stream):
                print(f">> {stream}: {result[stream]}")
        if result["status"] == STATUS_NO_DATA:
            print(
                "\nNo measurement was taken, so there is no verdict to give.\n"
                "This is not a failed strategy — it is an absent experiment."
            )
            return EXIT_NO_DATA
        return EXIT_ERROR

    prov = result.get("provenance") or {}
    print(f">> data: {prov.get('data_source')} {prov.get('exchange')} {prov.get('symbol')} "
          f"{prov.get('timeframe')} fingerprint={str(prov.get('data_fingerprint'))[:16]}")
    print(f">> trades: {result['metrics'].get('total_trades')}")

    print("\n[3] Quantitative validation and Monte Carlo")
    try:
        validator = QuantValidator(payload_drop_dir=os.path.join(base_dir, "payload_drop"))
        with open(os.path.join(base_dir, "payload_drop", "risk_constraints.json")) as fh:
            constraints = json.load(fh)

        code_path = os.path.join(
            base_dir, "jesse_workspace", "strategies", "SovereignStrategy", "__init__.py"
        )
        strategy_code = None
        if os.path.exists(code_path):
            with open(code_path, encoding="utf-8") as fh:
                strategy_code = fh.read()

        report = validator.generate_report(
            result["metrics"],
            constraints,
            num_simulations=1000,
            blueprint=blueprint,
            strategy_code=strategy_code,
            provenance=prov,
        )
    except Exception as exc:
        print(f">> validation failed: {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    mc = report["monte_carlo_results"]
    if report["verdict"] == "NO_TRADES":
        print(">> the strategy opened no positions on this window")
        print(">> no stress test was run: there is nothing to resample")
        print(">> report: payload_drop/validation_report.json")
        print(
            "\nThis is a definite answer, not a bad score. The entry conditions\n"
            "never occurred together on real candles — see research/RESULT_P0-1.md."
        )
        return EXIT_NO_DATA

    print(f">> risk of ruin (DD > {mc['drawdown_limit_used']}%): {mc['risk_of_ruin'] * 100:.2f}%")
    print(f">> average simulated max drawdown: {mc['average_max_drawdown']:.2f}%")
    print(f">> peak simulated drawdown:        {mc['peak_simulated_drawdown']:.2f}%")
    print(f">> verdict: {report['verdict']}")
    print(">> report: payload_drop/validation_report.json")

    if not report["validation_passed"]:
        # The optimizer is deliberately not invoked. It shrinks position size
        # until the verdict flips, selecting parameters on the same window it
        # then evaluates them on. Against the old mock metrics that was solving
        # an equation it had written itself; against real data it is overfitting
        # with extra steps. See plans/ROADMAP_TO_CONTROLLED_LIVE.md P0-7.
        print(
            "\nThe risk optimizer is suspended. Tuning position size until a window\n"
            "passes is selection on the evaluation set, not risk management."
        )
    return EXIT_PASSED if report["validation_passed"] else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
