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
# Run the full pipeline: validation → code generation → backtest → validation → dashboard
python run_simulation.py
```

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
- **Purpose:** Translates strategy blueprints into Jesse-compliant Python code with security hardening.
- **Key Classes:**
  - `DeveloperBridge` — Coordinates code generation and closed-loop backtest execution.
  - **AST Security Parser** — Built into code generation; validates mathematical expressions and rejects unsafe patterns (function calls, imports, attribute access on non-approved indicators).
- **Features:**
  - Regime-aware hyperparameters (market states like `trending_bullish`, `ranging_bearish` map to distinct parameter sets).
  - Fallback mock metrics if Jesse CLI is unavailable.
- **Output:** `jesse_workspace/strategies/SovereignStrategy/__init__.py` and `params.py`

#### `quant_validator.py`
- **Purpose:** Validates backtest metrics against risk constraints and runs stress tests.
- **Key Classes:**
  - `QuantValidator` — Loads metrics and constraints; executes Monte Carlo simulations.
  - **Monte Carlo Engine:**
    - **Non-Parametric Bootstrap** (preferred) — Resamples empirical trade returns to preserve real-world fat tails.
    - **Parametric Log-Normal Mixture** (fallback) — Models asymmetrical distributions when raw trades are unavailable; uses Sharpe, win rate, and trade count.
- **Output:** `payload_drop/validation_report.json` and `payload_drop/validation_dashboard.html`

#### `mcp_executor.py`
- **Purpose:** Interface to Jesse's backtest runner via MCP (or mock execution if Jesse CLI unavailable).
- **Key Classes:**
  - `MCPJesseRunner` — Executes backtest subprocess and extracts performance metrics (Sharpe, max drawdown, win rate, etc.).

### Data Layer (`payload_drop/`)
- **Input specs:**
  - `alpha_spec.json` — Trading signal definitions and regime-based logic.
  - `context_regime.json` — Market regime definitions and regime detection rules.
  - `risk_constraints.json` — Target thresholds (e.g., max drawdown, Sharpe ratio).
- **Intermediate:**
  - `strategy_blueprint.json` — Validated blueprint output from Supervisor.
- **Final outputs:**
  - `validation_report.json` — Structured JSON with metrics, validation verdict, Monte Carlo results.
  - `validation_dashboard.html` — Interactive Chart.js visualization of equity curves, drawdown paths, and risk metrics.

### Jesse Workspace (`jesse_workspace/`)
- Standard Jesse framework directory structure (backtests run here).
- `strategies/SovereignStrategy/` — Auto-generated strategy code placed here.
- `routes.py` — Configured with environment variables (exchange, symbol, timeframe).

### Testing (`tests/`)
- **Unit test suite** (38 tests total):
  - `test_supervisor.py` — Validates schema loading, Ruin Bias enforcement, blueprint generation.
  - `test_bridge.py` — Validates code generation, AST parsing, regime switching.
  - `test_validator.py` — Validates Monte Carlo logic, risk report generation.
  - `test_executor.py` — Validates backtest runner and metric extraction.
- Run with: `pytest -p no:anyio -v`

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
- **Ruin Bias Check** (mandatory): Max drawdown limit must be ≤ 2.0% to ensure compliance with capital preservation.
- **Monte Carlo Risk of Ruin**: Estimated as the percentage of simulated paths that breach the drawdown limit.

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

- **jesse** — Algorithmic trading framework for backtesting.
- **pydantic** (≥ 2.0) — Data validation and settings management.
- **pytest** — Unit testing framework (note: pinned to ~6.2.5 by jesse).
- **jsonschema** — JSON schema validation.

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
