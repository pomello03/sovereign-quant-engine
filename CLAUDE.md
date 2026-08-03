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
   │   │   (AST-validates every entry condition; identifier/number guards on every
   │   │    value that becomes source; ast.parse before anything reaches disk)
   │   └─ runner.run_backtest()                  [mcp_executor.py]
   │       ├─ compiles the generated strategy → COMPILATION_ERROR on failure
   │       └─ jesse.research.backtest() in-process, on real 1m candles.
   │          No Jesse, or no candles, or a window they do not cover → NO_DATA
   │          with metrics=None. There is no mock path.
   ▼
   │  QuantValidator.generate_report()           [quant_validator.py]
   │   Monte Carlo (skipped when total_trades == 0) → validation_report.json
   │   Verdict is PASSED / FAILED / NO_TRADES, and PASSED additionally requires
   │   provenance.data_source == 'jesse'.
```

**Two entry points drive this exact flow:**
- `run_simulation.py` — CLI. Exit codes: `0` passed, `1` failed, `2` nothing measured, `3` error.
- `web_dashboard/main.py` — FastAPI server; streams each step over **Server-Sent Events** (`GET /api/run`).

> **⚠️ Execution reality, 2026-08-03.** Real market data now exists (`research/data/`, Bybit spot,
> sha256 recorded). Jesse lives in **`.venv-jesse`, not the project venv** — running the pipeline
> with the project interpreter yields `NO_DATA`, which is correct: no framework, no measurement.
>
> The strategy in `payload_drop/alpha_spec.json` **opens zero positions** on five years of real
> candles: `rsi < 30` and `close > sma` are anti-correlated (r = +0.870) and never co-occur. The
> pipeline previously certified it `PASSED` with `risk_of_ruin: 0.0`. Read
> [research/RESULT_P0-1.md](research/RESULT_P0-1.md) before making any claim about strategy
> performance, and treat that zero-trade spec as a live regression test: if the pipeline ever
> reports PASSED on it again, the pipeline is broken.
>
> Costs are not optional here. The control strategy's 120 real trades produced **+2081 gross,
> −2560 in fees, −478 net** — the venue keeps 123% of the gross edge.

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

### Real backtests and market data

Jesse is installed in a **separate interpreter**, so the project venv stays free of its
`pytest~=6.2.5` pin and of a framework that imports and executes generated code.

```powershell
python -m venv .venv-jesse
.\.venv-jesse\Scripts\python.exe -m pip install jesse jsonschema

# Candles from Bybit's public endpoint (no credentials). ~10 min for the 1m series.
.\.venv-jesse\Scripts\python.exe research\fetch_bybit_candles.py --interval 1 `
    --start 2023-12-01 --end 2026-08-01 --format npy --pause 0.08

# The pipeline, for real
.\.venv-jesse\Scripts\python.exe run_simulation.py --start 2024-01-01 --end 2026-07-01
```

Data files are gitignored; the `.meta.json` beside each **is tracked**, because the sha256 and
window are what make a result checkable later. See [research/README.md](research/README.md).

Jesse requires **1-minute** candles and aggregates upward itself. That is not overhead: with a 2%
stop and a 4% target, a 4h bar spanning both tells you nothing about which was hit first, and
assuming the favourable one is how a losing strategy backtests as a winner.

The old `bin/sqe-audit.sh` gate (ruff + vulture + xenon via a hunted-for `sh.exe`) is gone. It
mapped any non-zero exit to `COMPILATION_ERROR`, so an uninstalled linter was indistinguishable
from broken generated code and sent the bridge into three rounds of regenerating correct code.
`ast.parse` + `compile` answers the only question it actually had.

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

#### `optimizer.py` — **SUSPENDED, do not wire back in**
Nothing calls it: `run_simulation.py` no longer does, and the copy of its loop inside the SSE
endpoint is deleted. `optimize_risk_parameters()` emits a `RuntimeWarning` if invoked.

It shrinks position size until the verdict flips, then reports that verdict — selecting a
parameter on the evaluation set. Against the old mock metrics it was worse than that: drawdown
was literally `-(pos_size * sl * 100 * 3)`, so the loop inverted an equation it had written
itself, and the committed `optimization_history` reproduces exactly. Its premise — that halving
sizing halves drawdown — has never been measured on real candles. See roadmap P0-7 / P1-1.

#### `quant_validator.py`
- **Purpose:** Validates backtest metrics against risk constraints and runs stress tests.
- **Key Class:** `QuantValidator` — `validate_metrics()` (base gates: drawdown, Sharpe, profit factor) + `run_monte_carlo()` + `validate_with_monte_carlo()` + `generate_report()`.
- **Monte Carlo Engine** (two modes):
  - **Non-Parametric Bootstrap** (required to PASS) — Resamples empirical `trade_returns` to preserve real-world fat tails.
  - **Parametric Log-Normal Mixture** (diagnostic only) — Used when no `trade_returns` exist. **Deliberately does NOT scale by realized drawdown** (avoids look-ahead bias) and is **rejected** by `validate_with_monte_carlo`, which demands bootstrap mode with ≥ `MIN_REAL_TRADES` (30) real samples — this blocks the false positive where a near-idle strategy shows ~0% ruin.
- **Output:** `payload_drop/validation_report.json` and the two-file dashboard (see below).

#### `mcp_executor.py`
- **Purpose:** Measure, or say it could not. **There is no mock path, and adding one back is the
  single most damaging change anyone could make to this repo.**
- **Key Class:** `MCPJesseRunner.run_backtest()` — compiles the generated strategy, then runs
  `jesse.research.backtest()` in-process on real 1m candles. `SUCCESS` requires candles;
  everything else returns `NO_DATA` with `metrics=None` (None, not `{}`, so a caller that reads
  a missing metric crashes instead of treating it as acceptable).
- **Provenance on every result:** `data_source`, `data_fingerprint`, exchange/symbol/timeframe,
  fee, `strategy_sha256`, window. `QuantValidator` refuses a positive verdict without it.
- **Why in-process:** the previous version scraped `jesse backtest` stdout with regexes that never
  extracted per-trade returns. Without them `run_monte_carlo` falls to parametric mode, which
  `validate_with_monte_carlo` rejects — so a real backtest could never pass and only the mock
  could. `research.backtest()` returns `trades` directly, which removes the whole class of bug.
- Four tests guard the invariant structurally, including `test_no_mock_metrics_anywhere_in_the_module`.

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
- **Unit test suite (115 tests across 9 files):**
  - `test_supervisor.py` — schema loading, Ruin Bias enforcement, R:R cross-check, blueprint generation.
  - `test_bridge.py` — code generation, AST parsing/rejection, regime switching.
  - `test_rce_regression.py` — the audit's actual RCE payload, refused at each of three layers.
  - `test_validator.py` — Monte Carlo modes, the bootstrap-required PASS gate, the provenance gate.
  - `test_executor.py` — NO_DATA paths, provenance, and structural guards that SUCCESS cannot be
    reached without data. **Do not relax these to make a test pass.**
  - `test_optimizer.py` — closed-loop parameter convergence (module suspended; warns when run).
  - `test_state_io.py` — atomic writes, freshness/`StaleStateError`, file locking.
  - `test_db_pool.py` — pool sizing, transactional commit/rollback, deadlock retry (uses a fake connection factory).
  - `test_edge_cases.py` — cross-cutting boundary/error-path coverage.
- Run with: `pytest -p no:anyio -v`. Tests set `PYTEST_CURRENT_TEST`, which the bridge/executor use to **skip the static audit and ruff formatting** so the suite runs without ruff/vulture/xenon installed.

---

## Security Model

### Everything from alpha_spec.json becomes Python source
That is the threat. A confirmed RCE lived here: `indicators[].params` values were interpolated
into an f-string, so `{"period": "14, __x=open(...).write(...)"}` produced valid Python that ran
on the first indicator access — silently, because `_safe_indicator` catches and returns the
fallback. Three independent layers now stop it (`tests/test_rce_regression.py`, 16 tests):

1. **Schema** — `indicators[].params` values must be **numbers**; names and keys must match
   `^[A-Za-z_][A-Za-z0-9_]*$`; `additionalProperties: false` throughout.
2. **Generator** — `_safe_identifier()` / `_safe_number()` re-check independently of the schema,
   and `_safe_number` emits `repr()` of a validated number, never the caller's own text.
3. **`ast.parse` before writing** — a file that never reaches disk is never imported.

### AST-based condition validation
Entry conditions are parsed and rewritten with a **whitelist**: arithmetic, comparisons, logical
ops, and names that are either Jesse price fields or declared indicators. Calls and attribute
access raise. An unrecognised bare name now raises too — previously it passed through, which is a
blacklist wearing a whitelist's name.

### Regime alignment — currently a no-op
`_generate_params_content` builds `{'default': base_params, regime: base_params}`: the same object
under two keys. Switching regime changes nothing. Worth knowing before trusting the word
"regime-aware" anywhere in this repo.

### Naming collisions with the framework
The generated strategy must not define `hyperparameters` — Jesse's `Strategy` declares it as a
**method** and calls it during route setup. It is named `regime_params` for exactly this reason.
Exit orders go in `on_open_position()`, never `go_long()`: spot rejects the latter.

### Risk Guardrails
- **Ruin Bias Check** (mandatory, Supervisor): `max_drawdown_limit_pct` must be ≤ 2.0% or
  `RuinBiasViolationError` is raised. The JSON schema also caps it at 2.0. It is no longer
  reachable from the dashboard query string.
- **Monte Carlo Risk of Ruin**: ≤ 5% to PASS, bootstrap mode, ≥ 30 real trades. Skipped entirely
  when `total_trades == 0` — resampling an empty sample yields 0% ruin, which is how a strategy
  that cannot trade becomes the safest one on the board.
- **Fail-closed metrics**: `validate_metrics` **raises** `MissingMetricError` on an unmeasured
  metric. It used to wrap every check in `if x is not None`, so all-None metrics passed
  deliberately severe constraints — and a test asserted that was correct.
- **Provenance gate**: `validation_passed` is forced False unless `data_source == 'jesse'`.
- **Sign check**: `stop_loss_value` and `take_profit_value` must be positive. `(-0.04)/(-0.02)`
  is 2.0, so two negatives used to satisfy the risk-to-reward minimum.
- **Unmeasured, and important:** real max drawdown on the control run was **−29%** against this
  2% limit. Either the limit is renegotiated with evidence, or it is demonstrated — not obtained
  by shrinking position size until a window complies.

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

**Required at runtime but NOT in `requirements.txt`:**
- `jesse` — in **`.venv-jesse`**, not the project venv. Without it the pipeline returns `NO_DATA`.
- `fastapi`, `uvicorn` — the web dashboard server (`web_dashboard/main.py`).
- `psycopg2` — only if using `db_pool.py`, which nothing in the pipeline imports.
- `ruff` — optional, only to format generated code. No longer gates anything.

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
