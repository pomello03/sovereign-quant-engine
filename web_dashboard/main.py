import os
import sys
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core_engine.supervisor import Supervisor
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator

app = FastAPI(title="Sovereign Quant Engine Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>Sovereign Dashboard</title></head>
        <body style="font-family: sans-serif; background: #0f172a; color: #f1f5f9; text-align: center; padding-top: 100px;">
            <h2>Sovereign Quant Engine Dashboard</h2>
            <p>Dashboard static files are loading. Please check again in a few seconds.</p>
        </body>
    </html>
    """

@app.get("/api/run")
async def run_simulation_stream(request: Request, max_iterations: int = 10, drawdown_limit: float = 1.5):
    async def event_generator():
        payload_drop = os.path.join(project_root, "payload_drop")
        jesse_workspace = os.path.join(project_root, "jesse_workspace")
        
        # 1. Supervisor Step
        yield f"data: {json.dumps({'event': 'step_start', 'step': 'supervisor', 'message': 'Initializing Supervisor & Validating Phase 1 schemas...'})}\n\n"
        await asyncio.sleep(0.5)
        
        try:
            supervisor = Supervisor(payload_drop_dir=payload_drop)
            blueprint = await asyncio.to_thread(supervisor.validate_and_generate)
            yield f"data: {json.dumps({'event': 'step_success', 'step': 'supervisor', 'message': 'Supervisor approved blueprint and generated payload_drop/strategy_blueprint.json', 'data': blueprint})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'step_error', 'step': 'supervisor', 'message': f'Validation failed: {e}'})}\n\n"
            return
            
        await asyncio.sleep(0.5)
        
        # 2. Developer Bridge Step
        yield f"data: {json.dumps({'event': 'step_start', 'step': 'developer_bridge', 'message': 'Triggering Developer Bridge for code generation & backtest execution...'})}\n\n"
        
        try:
            bridge = DeveloperBridge(
                payload_drop_dir=payload_drop,
                workspace_path=jesse_workspace
            )
            # Run closed loop
            result = await asyncio.to_thread(bridge.execute_closed_loop, "2026-01-01", "2026-06-01")
            
            if result['status'] == "SUCCESS":
                yield f"data: {json.dumps({'event': 'step_success', 'step': 'developer_bridge', 'message': 'Developer Bridge generated SovereignStrategy class and successfully completed closed-loop backtest.', 'data': result['metrics']})}\n\n"
            else:
                status_val = result['status']
                yield f"data: {json.dumps({'event': 'step_error', 'step': 'developer_bridge', 'message': f'Developer Bridge backtest/compile failed: {status_val}', 'stdout': result.get('stdout'), 'stderr': result.get('stderr')})}\n\n"
                return
        except Exception as e:
            yield f"data: {json.dumps({'event': 'step_error', 'step': 'developer_bridge', 'message': f'Bridge execution failed: {e}'})}\n\n"
            return
            
        await asyncio.sleep(0.5)
        
        # 3. Quant Validator Step
        yield f"data: {json.dumps({'event': 'step_start', 'step': 'validator', 'message': 'Running Quantitative Validation and Monte Carlo stress test (1000 simulations)...'})}\n\n"
        
        try:
            validator = QuantValidator(payload_drop_dir=payload_drop)
            metrics = result['metrics']
            
            # Load constraints
            constraints_path = os.path.join(payload_drop, "risk_constraints.json")
            if os.path.exists(constraints_path):
                with open(constraints_path, "r") as f:
                    constraints = json.load(f)
            else:
                constraints = {
                    "max_drawdown_limit_pct": drawdown_limit,
                    "sharpe_ratio_minimum": 1.5,
                    "profit_factor_minimum": 1.2
                }
            
            # Update drawdown limit in constraints for custom limits
            constraints["max_drawdown_limit_pct"] = drawdown_limit
            with open(constraints_path, "w") as f:
                json.dump(constraints, f, indent=2)
                
            report = await asyncio.to_thread(validator.generate_report, metrics, constraints, 1000)
            
            yield f"data: {json.dumps({'event': 'validator_verdict', 'passed': report['validation_passed'], 'report': report})}\n\n"
            
            if report['validation_passed']:
                yield f"data: {json.dumps({'event': 'simulation_success', 'message': 'Simulation finished successfully! Strategy meets all risk criteria.', 'report': report})}\n\n"
                return
        except Exception as e:
            yield f"data: {json.dumps({'event': 'step_error', 'step': 'validator', 'message': f'Validation failed: {e}'})}\n\n"
            return
            
        # 4. Closed-loop Optimization Step
        yield f"data: {json.dumps({'event': 'step_start', 'step': 'optimizer', 'message': 'Metrics violated risk constraints. Launching Closed-Loop Risk Parameter Optimizer...'})}\n\n"
        await asyncio.sleep(0.5)
        
        try:
            blueprint_path = os.path.join(payload_drop, "strategy_blueprint.json")
            with open(blueprint_path, "r", encoding="utf-8") as f:
                blueprint = json.load(f)
            
            # Initial values from the current blueprint
            pos_size = blueprint.get("risk", {}).get("max_position_sizing_pct", 2.0)
            sl = blueprint.get("risk", {}).get("stop_loss_value", 0.02)
            
            best_report = report
            
            for iteration in range(1, max_iterations + 1):
                yield f"data: {json.dumps({'event': 'optimizer_iteration_start', 'iteration': iteration, 'pos_size': pos_size, 'sl': sl})}\n\n"
                
                # 1. Update blueprint in memory and file
                blueprint["risk"]["max_position_sizing_pct"] = pos_size
                blueprint["risk"]["stop_loss_value"] = sl
                with open(blueprint_path, "w", encoding="utf-8") as f:
                    json.dump(blueprint, f, indent=2)
                    
                # 2. Generate strategy code
                await asyncio.to_thread(bridge.generate_strategy_code, blueprint, force_clean=True)
                
                # 3. Run backtest
                result = await asyncio.to_thread(bridge.execute_closed_loop, "2026-01-01", "2026-06-01")
                
                if result["status"] != "SUCCESS":
                    status_val = result["status"]
                    yield f"data: {json.dumps({'event': 'optimizer_iteration_fail', 'iteration': iteration, 'message': f'Backtest/Audit failed: status={status_val}'})}\n\n"
                    continue
                    
                iter_metrics = result["metrics"]
                
                # 4. Run validator report
                report = await asyncio.to_thread(validator.generate_report, iter_metrics, constraints, 1000)
                best_report = report
                
                mc = report['monte_carlo_results']
                yield f"data: {json.dumps({
                    'event': 'optimizer_iteration_result',
                    'iteration': iteration,
                    'pos_size': pos_size,
                    'sl': sl,
                    'max_dd': iter_metrics['max_drawdown'],
                    'risk_of_ruin': mc['risk_of_ruin'],
                    'passed': report['validation_passed'],
                    'avg_max_dd': mc['average_max_drawdown'],
                    'peak_dd': mc['peak_simulated_drawdown']
                })}\n\n"
                
                if report["validation_passed"]:
                    yield f"data: {json.dumps({'event': 'simulation_success', 'message': f'Optimization converged successfully at iteration {iteration}!', 'report': report})}\n\n"
                    return
                    
                # Adjust parameters heuristically
                if pos_size > 0.1:
                    pos_size = max(0.1, pos_size * 0.5)
                else:
                    sl = max(0.005, sl * 0.8)
                    
                await asyncio.sleep(0.5)
                
            yield f"data: {json.dumps({'event': 'simulation_failed_opt', 'message': f'Optimization finished after {max_iterations} iterations without finding fully compliant parameters.', 'report': best_report})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'step_error', 'step': 'optimizer', 'message': f'Optimization error: {e}'})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
