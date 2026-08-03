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

# `allow_origins=["*"]` with `allow_credentials=True` makes Starlette echo back
# whatever Origin it is given, so any page the operator had open could read this
# stream. The dashboard is a local operator console; it has no reason to be
# reachable cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET"],
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
async def run_simulation_stream(request: Request,
                                start_date: str = "2024-01-01",
                                end_date: str = "2026-07-01"):
    """Stream a pipeline run as Server-Sent Events.

    There is deliberately no `drawdown_limit` parameter. It used to be accepted
    unbounded from the query string and written into risk_constraints.json
    *after* the Supervisor had already enforced the Ruin Bias check, so
    `?drawdown_limit=99` passed a strategy with 73.86% simulated drawdown. A
    risk limit is not a display preference and does not travel over HTTP; it
    lives in the file, under review.
    """
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
            result = await asyncio.to_thread(bridge.execute_closed_loop, start_date, end_date)

            if result['status'] == "SUCCESS":
                yield f"data: {json.dumps({'event': 'step_success', 'step': 'developer_bridge', 'message': 'Developer Bridge generated SovereignStrategy class and completed the backtest.', 'data': result['metrics'], 'provenance': result.get('provenance')})}\n\n"
            elif result['status'] == "NO_DATA":
                # Distinct from an error: nothing broke, nothing was measured.
                # The UI must not be able to render this as a neutral failure.
                yield f"data: {json.dumps({'event': 'no_data', 'step': 'developer_bridge', 'message': 'No measurement was possible, so there is no verdict.', 'reason': result.get('reason')})}\n\n"
                return
            else:
                status_val = result['status']
                yield f"data: {json.dumps({'event': 'step_error', 'step': 'developer_bridge', 'message': f'Developer Bridge backtest/compile failed: {status_val}', 'reason': result.get('reason'), 'stdout': result.get('stdout'), 'stderr': result.get('stderr')})}\n\n"
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
            
            # Constraints are read, never written. This endpoint has no
            # authority to change a risk limit.
            constraints_path = os.path.join(payload_drop, "risk_constraints.json")
            with open(constraints_path, "r") as f:
                constraints = json.load(f)

            report = await asyncio.to_thread(
                validator.generate_report, metrics, constraints, 1000,
                None, None, blueprint, None, result.get("provenance"),
            )

            yield f"data: {json.dumps({'event': 'validator_verdict', 'passed': report['validation_passed'], 'report': report})}\n\n"

            if report['validation_passed']:
                yield f"data: {json.dumps({'event': 'simulation_success', 'message': 'The strategy meets the risk criteria on this window.', 'report': report})}\n\n"
            else:
                # The optimizer loop that used to live here shrank position size
                # until the verdict flipped, on the same window it then reported.
                # See plans/ROADMAP_TO_CONTROLLED_LIVE.md P0-7.
                yield f"data: {json.dumps({'event': 'simulation_failed', 'message': 'The strategy does not meet the risk criteria on this window. The risk optimizer is suspended: tuning position size until a window passes is selection on the evaluation set.', 'report': report})}\n\n"
            return
        except Exception as e:
            yield f"data: {json.dumps({'event': 'step_error', 'step': 'validator', 'message': f'Validation failed: {e}'})}\n\n"
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
