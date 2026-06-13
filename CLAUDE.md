# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

The **Sovereign Quant Engine** is an automated, closed-loop pipeline that bridges generative AI-based trading strategy design with secure code generation, backtesting, and quantitative validation. It targets the [Jesse Algorithmic Trading Framework](https://jesse.trade/) and operates via three core layers:

1. **Supervisor Node** — Validates input schemas and enforces risk guardrails (Ruin Bias, max drawdown ≤ 2.0%)
2. **Developer Bridge** — Generates Jesse-compliant Python strategy code with AST-based security parsing
3. **Quantitative Validator** — Runs Monte Carlo stress tests and generates validation reports

The engine outputs: strategy blueprint, executable code, backtest metrics, Monte Carlo simulations, and an interactive HTML dashboard.

---

## Big Picture: Pipeline Flow

Understanding the system requires reading several modules together. The full closed loop is:

```
alpha_spec + risk_constraints + context_regime (payload_drop/*.json)
   │
   ▼  Supervisor.validate_and_generate()        [supervisor.py]
   │   schema-validates inputs, enforces Ruin Bias (≤ 2.0%), cross-checks R:R,
   │   writes strategy_blueprint.json (atomically, via state_io)
   ▼
   │  DeveloperBridge.execute_closed_loop()      [developer_bridge.py]
   │   ├─ generate_strategy_code(): blueprint → SovereignStrategy/__init__.py + params.py
   │   │   (AST-validates every entry condition; ruff-formats the output)
   │   └─ runner.run_backtest()                  [mcp_executor.py]
   │       ├─ runs bin/sqe-audit.sh static gate FIRST (ruff + vulture + xenon).
   │       │   Audit failure → COMPILATION_ERROR → bridge regenerates & retries (≤3x)
   │       └─ runs `jesse backtest` IF Jesse CLI is on PATH, ELSE returns MOCK metrics
   ▼
   │  QuantValidator.generate_report()           [quant_validator.py]
   │   Monte Carlo stress test → validation_report.json + validation_dashboard.html
   ▼
   IF validation fails → RiskOptimizer.optimize_risk_parameters()  [optimizer.py]
       loops: shrink position size, then stop-loss → regenerate → re-backtest →
       re-validate, up to max_iterations, until risk_of_ruin ≤ 5% and DD within limit.
```

**Two entry points drive this exact flow:**
- `run_simulation.py` — CLI; runs once, then triggers `RiskOptimizer` only if validation fails.
- `web_dashboard/main.py` — FastAPI server; streams each step to the browser over **Server-Sent Events** (`GET /api/run`), with the optimizer loop inlined into the stream rather than calling `RiskOptimizer`.

> **⚠️ Current execution reality:** Jesse is **not installed** in this environment, so `run_backtest()` falls through to its **mock path** ([mcp_executor.py](core_engine/mcp_executor.py) `mock_metrics`). Drawdown/Sharpe are then **deterministic functions of the blueprint's risk params** (e.g. `simulated_drawdown = -(pos_sizing * sl * 100 * 3)`), not measured market outcomes. Every "PASSED" verdict and dashboard chart you see today is built on synthetic numbers. Installing Jesse + loading real candle data is what turns this from a self-simulating demo into a real backtester — treat that as the prerequisite for any claim about strategy performance.

---

## Development Setup

### Prerequisites
- **Python 3.10–3.12** (required by Jesse framework)
- **pip** and virtual environment (venv)
- **Git** for version control

### Installation
```powershell
# Clone and navigate to project
git clone https://github.com/pomello03/sovereign-quant-engine.git
cd sovereign-quant-engine

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Common Commands

### Running Tests
```powershell
# Full test suite (pytest has a conflict with jesse via anyio plugin)
pytest -p no:anyio -v

# Run a specific test file
pytest -p no:anyio -v tests/test_supervisor.py

# Run a single test
pytest -p no:anyio -v tests/test_supervisor.py::TestSupervisor::test_validate_and_generate
```

**Note:** The `-p no:anyio` flag is mandatory because jesse pins `pytest~=6.2.5`, which conflicts with the modern anyio plugin's entrypoint.

### End-to-End Simulation
```powershell
# CLI: full pipeline — validation → code generation → (audit + backtest) → validation → dashboard
python run_simulation.py
```

### Interactive Web Dashboard (live SSE stream)
```powershell
# Starts FastAPI server on http://127.0.0.1:8000 ; the browser drives /api/run
python web_dashboard\main.py
# (or) uvicorn web_dashboard.main:app --reload
```

### Static Audit Gate
The Developer Bridge runs `bin/sqe-audit.sh` against generated strategies **before every backtest**.
It chains three tools and fails the build (→ `COMPILATION_ERROR`) if any returns non-zero:
```powershell
# These must be installed for non-mock audit runs (they are NOT in requirements.txt):
pip install ruff vulture xenon

# What the gate runs (mirrors bin/sqe-audit.sh):
ruff check jesse_workspace/strategies/ --select F,E,W,I,U
vulture jesse_workspace/strategies/ --min-confidence 80
xenon --max-absolute A --max-modules A --max-average B jesse_workspace/strategies/
```
On Windows the bridge locates a POSIX `sh.exe` (Git for Windows) to run the script; if none is found it falls back to invoking the three tools directly via `python -m`. The audit is **skipped under pytest** (`PYTEST_CURRENT_TEST` env var).

### View Results
```powershell
# Open the validation dashboard in your default browser
Start-Process .\payload_drop\validation_dashboard.html
```

---

## Architecture & Key Modules

### Core Engine Modules (`core_engine/`)

#### `supervisor.py`
- **Purpose:** System initialization, schema validation, and blueprint generation.
- **Key Classes:**
  - `Supervisor` — Loads alpha specs, risk constraints, and regime contexts from JSON. Validates inputs against JSON schemas. Enforces **Ruin Bias** check (max drawdown must be ≤ 2.0%).
  - `RuinBiasViolationError` — Custom exception when drawdown safety threshold is breached.
- **Output:** `payload_drop/strategy_blueprint.json`

#### `developer_bridge.py`
- **Purpose:** Translates strategy blueprints into Jesse-compliant Python code with security hardening, and runs the closed-loop backtest with automatic retry on compile errors.
- **Key Classes:**
  - `DeveloperBridge` — `generate_strategy_code()` emits `__init__.py` (strategy class) + `params.py` (regime-keyed hyperparameters); `execute_closed_loop()` backtests and, on `COMPILATION_ERROR`, regenerates clean code and retries up to `max_retries` (default 3).
  - **AST Security Parser** (`_translate_condition`) — Parses each entry condition with `ast`, rewriting bare names (`close`, `rsi`) into `self.*` attribute access, and **raising on any function call or attribute access** to block code injection.
- **Generated-strategy hardening** (referenced in comments as "Vuln 2/4"): indicator getters go through `_safe_indicator()` (cold-start NaN/None guards with safe fallbacks), ATR-based position sizing, and a unidirectional + throttled trailing stop (`TRAIL_MIN_MOVE_PCT`) to avoid exchange order-spam / HTTP 429.
- **Output:** `jesse_workspace/strategies/SovereignStrategy/__init__.py` and `params.py` (ruff-formatted unless under pytest).

#### `optimizer.py`
- **Purpose:** Closed-loop risk-parameter search invoked when validation fails.
- **Key Class:** `RiskOptimizer.optimize_risk_parameters()` — heuristically **halves `max_position_sizing_pct` first, then scales down `stop_loss_value`**, regenerating code and re-backtesting each iteration until `validate_with_monte_carlo` passes (risk_of_ruin ≤ 5%, avg DD within limit) or `max_iterations` is hit. Records every attempt in `optimization_history` (fed to the dashboard stepper). The web dashboard reimplements this same loop inline as an SSE stream.

#### `quant_validator.py`
- **Purpose:** Validates backtest metrics against risk constraints and runs stress tests.
- **Key Class:** `QuantValidator` — `validate_metrics()` (base gates: drawdown, Sharpe, profit factor) + `run_monte_carlo()` + `validate_with_monte_carlo()` + `generate_report()`.
- **Monte Carlo Engine** (two modes):
  - **Non-Parametric Bootstrap** (required to PASS) — Resamples empirical `trade_returns` to preserve real-world fat tails.
  - **Parametric Log-Normal Mixture** (diagnostic only) — Used when no `trade_returns` exist. **Deliberately does NOT scale by realized drawdown** (avoids look-ahead bias) and is **rejected** by `validate_with_monte_carlo`, which demands bootstrap mode with ≥ `MIN_REAL_TRADES` (30) real samples — this blocks the false positive where a near-idle strategy shows ~0% ruin.
- **Output:** `payload_drop/validation_report.json` and the two-file dashboard (see below).

#### `mcp_executor.py`
- **Purpose:** Runs the Jesse backtest subprocess and parses its stdout into metrics; falls back to **mock metrics when Jesse CLI is absent or data is missing**.
- **Key Class:** `MCPJesseRunner` — `run_backtest()` first runs the static audit gate, then shells out to `jesse backtest`. `_parse_jesse_output()` extracts Sharpe / max drawdown / total trades / profit factor / win rate from the report table. See the ⚠️ note in **Big Picture** — mock metrics are synthetic and parameter-derived.

#### `state_io.py` & `db_pool.py` (shared-state / persistence hardening)
- `state_io.py` — `atomic_write_json()` (write-temp-then-`os.replace`, so readers never see a partial file), `read_json_fresh()` (rejects stale signal files past a max age → `StaleStateError`, guarding against a silently-failed upstream agent), and a cross-platform `file_lock()` (fcntl on POSIX, msvcrt on Windows). The Supervisor and Validator write all state through these.
- `db_pool.py` — `PostgresConnectionPool`: bounded thread-safe pool with transactional `connection()` context manager, deadlock/serialization retry with exponential backoff, and an injectable `connection_factory` so psycopg2 stays optional and the pool is unit-testable without a live DB. Mirrors `jesse_workspace/config.py` `DB_*` env vars.

### Web Dashboard (`web_dashboard/`)
- `main.py` — FastAPI app. `GET /api/run?max_iterations=&drawdown_limit=` runs the whole pipeline and streams `step_start` / `step_success` / `optimizer_iteration_result` / `simulation_success` events as SSE. `GET /` serves `static/index.html`. **Note:** it can rewrite `payload_drop/risk_constraints.json` with the `drawdown_limit` query param. Distinct from `core_engine/templates/` — that's the report dashboard; this is the live run UI.

### Data Layer (`payload_drop/`)
- **Input specs:**
  - `alpha_spec.json` — Trading signal definitions and regime-based logic.
  - `context_regime.json` — Market regime definitions and regime detection rules.
  - `risk_constraints.json` — Target thresholds (e.g., max drawdown, Sharpe ratio).
- **Intermediate:**
  - `strategy_blueprint.json` — Validated blueprint output from Supervisor.
- **Final outputs:**
  - `validation_report.json` — Structured JSON with metrics, validation verdict, Monte Carlo results, optimization history, and the generated strategy code.
  - `validation_dashboard.html` + `dashboard_app.js` — **two-file** Chart.js dashboard. The validator reads templates from `core_engine/templates/` (`dashboard.html` shell + `dashboard_app.js`), injects the report JSON at the `/* REPORT_JSON_PLACEHOLDER */` marker (escaping `</` so the JSON can't close the `<script>` tag), and writes both files here. **Edit the templates in `core_engine/templates/`, never the generated files in `payload_drop/`** — the latter are overwritten on every run.

### Jesse Workspace (`jesse_workspace/`)
- Standard Jesse framework directory structure (backtests run here).
- `strategies/SovereignStrategy/` — Auto-generated strategy code placed here.
- `routes.py` — Configured with environment variables (exchange, symbol, timeframe).

### Testing (`tests/`)
- **Unit test suite (~91 tests across 8 files):**
  - `test_supervisor.py` — schema loading, Ruin Bias enforcement, R:R cross-check, blueprint generation.
  - `test_bridge.py` — code generation, AST parsing/rejection, regime switching.
  - `test_validator.py` — Monte Carlo modes, the bootstrap-required PASS gate, report generation.
  - `test_executor.py` — backtest runner, mock fallback, metric parsing.
  - `test_optimizer.py` — closed-loop parameter convergence.
  - `test_state_io.py` — atomic writes, freshness/`StaleStateError`, file locking.
  - `test_db_pool.py` — pool sizing, transactional commit/rollback, deadlock retry (uses a fake connection factory).
  - `test_edge_cases.py` — cross-cutting boundary/error-path coverage.
- Run with: `pytest -p no:anyio -v`. Tests set `PYTEST_CURRENT_TEST`, which the bridge/executor use to **skip the static audit and ruff formatting** so the suite runs without ruff/vulture/xenon installed.

---

## Security Model

### AST-Based Code Validation
The Developer Bridge uses Python's AST (Abstract Syntax Tree) to parse and validate mathematical expressions in strategy conditions. The parser enforces a **whitelist model**:
- ✓ Allowed: arithmetic operators (`+`, `-`, `*`, `/`), comparisons (`>`, `<`, `==`), logical ops (`and`, `or`)
- ✓ Allowed: approved indicator names (e.g., `rsi`, `sma`) passed as variables
- ✗ Rejected: function calls (prevents arbitrary code execution), imports, attribute access (outside pre-approved indicators)

### Regime Alignment
Strategy hyperparameters are keyed by market regime. This prevents overfitting to a single market state and ensures generalization across bull, bear, and ranging conditions.

### Risk Guardrails
- **Ruin Bias Check** (mandatory, Supervisor): `max_drawdown_limit_pct` must be ≤ 2.0% or `RuinBiasViolationError` is raised. The JSON schema also caps it at 2.0.
- **Monte Carlo Risk of Ruin**: % of simulated paths breaching the drawdown limit; must be ≤ 5% to PASS, **and** the run must be bootstrap mode with ≥ 30 real trades (see `quant_validator.py`).

### State & Concurrency Hardening
The code comments track five hardening themes ("Vuln 1–5") worth preserving when editing:
1. **Silent state propagation** — `read_json_fresh()` rejects stale upstream signal files (`StaleStateError`).
2. **Cold-start NaN/None** — generated `_safe_indicator()` guards every indicator getter.
3. **Race conditions on shared state** — `atomic_write_json()` + `file_lock()` (state_io) and `PostgresConnectionPool` (db_pool).
4. **Trailing-stop order spam** — unidirectional, throttled stop in the generated strategy.
5. **Monte Carlo look-ahead bias** — parametric mode never scales by realized drawdown and cannot, by itself, validate a strategy.

---

## Common Development Tasks

### Adding a New Module
1. Create file in `core_engine/` with a descriptive name.
2. Import in relevant test files and `run_simulation.py`.
3. Add corresponding unit test in `tests/` following the naming pattern `test_<module_name>.py`.
4. Run `pytest -p no:anyio -v` to verify.

### Modifying Schema Validation
- Update JSON schemas in `schemas/` (e.g., `alpha_spec.json`, `risk_constraints.json`).
- Update `Supervisor` in `core_engine/supervisor.py` to handle new fields.
- Add test cases in `tests/test_supervisor.py`.

### Debugging Backtest Failures
1. Check `jesse_workspace/` for generated strategy files and logs.
2. Run `pytest -p no:anyio -v tests/test_executor.py` to isolate MCP executor issues.
3. Check for missing or malformed `payload_drop/strategy_blueprint.json`.

### Extending Monte Carlo Simulation
- Modify `QuantValidator` in `core_engine/quant_validator.py`.
- Adjust `num_simulations` parameter in `run_simulation.py` (default: 1000).
- Verify statistical properties with additional test cases in `tests/test_validator.py`.

---

## Deployment & Real-World Operation

For live trading deployment, refer to the detailed guides in `docs/`:
- `Pipeline Deploy IRL Bybit Hetzner.md` — Hetzner Cloud VPS setup and Docker deployment.
- `Guida al Deploy IRL Sicuro.md` — Security best practices for API keys and exchange connections.

**Phased rollout:**
1. **Testnet (Week 1)** — Verify network connectivity and order placement.
2. **Micro-sizing (Week 2–3)** — Run with $50 capital and 1x leverage to measure real slippage.
3. **Scaling** — Gradually increase capital and add monitoring (e.g., Telegram notifications).

---

## Key Dependencies

**In `requirements.txt`:** `jesse` (backtesting framework; pins `pytest~=6.2.5`), `jsonschema` (≥4.0), `pydantic` (≥2.0), `pytest`.

**Required at runtime but NOT in `requirements.txt`** (install manually for non-mock runs):
- `ruff`, `vulture`, `xenon` — the static audit gate (`bin/sqe-audit.sh`).
- `fastapi`, `uvicorn` — the web dashboard server (`web_dashboard/main.py`).
- `psycopg2` — only if using `db_pool.py` against a live Postgres (Jesse's DB).

The core CLI pipeline (`run_simulation.py`) runs without Jesse installed (mock path) but still expects ruff/vulture/xenon for the audit unless run under pytest.

---

## File Organization Tips

- **Schemas** (`schemas/`) contain JSON schema definitions; keep them in sync with code validators.
- **Payload drop** (`payload_drop/`) is the I/O boundary; all inputs and outputs pass through here.
- **Core engine** (`core_engine/`) is the logic hub; modules are independent and testable.
- **Tests** mirror core_engine structure for clarity.

---

## Performance Notes

- **Monte Carlo speed:** Default 1,000 simulations takes ~2–5 seconds. Non-parametric bootstrap is faster than log-normal mixture.
- **Backtest execution:** Depends on Jesse framework and data availability. Mock execution (fallback) is instant.
- **Dashboard generation:** HTML rendering is fast; consider chart.js performance if simulating >5,000 paths.

---

## Questions or Issues?

Refer to:
- `README.md` for project overview and architecture diagram.
- `QUICKSTART.md` for installation and setup troubleshooting.
- `docs/` folder for advanced deployment and integration guides.
- Test files (`tests/`) for usage examples of each module.
