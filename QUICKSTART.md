# Sovereign Quant Engine - Quickstart Guide

This guide describes how to set up, test, and run the **Sovereign Quant Engine** on your local machine.

---

## 1. Prerequisites
Ensure you have the following installed:
*   **Python 3.10 to 3.12**
*   **pip** (Python package installer)
*   **Docker & Docker-Compose** (if planning to run services or deploy to production)

---

## 2. Installation & Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/pomello03/sovereign-quant-engine.git
    cd sovereign-quant-engine
    ```

2.  **Install Dependencies**:
    It is recommended to use a virtual environment:
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On Unix/macOS:
    source venv/bin/activate

    pip install -r requirements.txt
    ```

---

## 3. Verify the Installation
Run the complete unit testing suite. Note that because `jesse` requires `pytest~=6.2.5`, which conflicts with the global entrypoint of the modern `anyio` plugin, you must run pytest disabling the `anyio` plugin:
```bash
pytest -p no:anyio -v
```
All 38 tests should pass successfully.

---

## 4. Run the End-to-End Simulation
To run the full pipeline (schema validation -> code generation -> backtest run -> risk metrics check -> Monte Carlo simulation -> dashboard generation):
```bash
python run_simulation.py
```

### Expected Output Summary:
1.  **Supervisor Node**: Reads `payload_drop/alpha_spec.json`, `context_regime.json`, and `risk_constraints.json`, performs a **Ruin Bias** validation (ensuring max drawdown limit $\le$ 2.0%), and outputs `payload_drop/strategy_blueprint.json`.
2.  **Developer Bridge**: Translates the blueprint into Jesse-compatible code (`__init__.py` and `params.py` in `jesse_workspace/strategies/SovereignStrategy/`), running the conditions through a secure **AST Parser**.
3.  **MCP Jesse Executor**: Executes the backtest (falling back to mock metrics if Jesse CLI is not installed or historical candles are missing).
4.  **Quant Validator**: Analyzes backtest results against the risk constraints. It runs a **Monte Carlo stress test** (1,000 simulations) using a **Log-Normal Mixture** (or **Non-Parametric Bootstrap** if raw trade return lists are available) to calculate the **Risk of Ruin**.
5.  **Artifact Generation**: Writes `payload_drop/validation_report.json` and a visually rich `payload_drop/validation_dashboard.html`.

---

## 5. Visualizing the Results
Open the generated HTML dashboard directly in your web browser to view the interactive Chart.js equity curve simulations and final verdict:
*   **Windows (PowerShell)**:
    ```powershell
    Start-Process .\payload_drop\validation_dashboard.html
    ```
*   **Mac/Linux**:
    ```bash
    open payload_drop/validation_dashboard.html
    ```

---

## 6. Live Deployment (IRL) Strategy
For real-life execution, follow the detailed guides in the `docs/` folder:
1.  **Server Hosting**: Deploy the bot on a dedicated **Hetzner Cloud VPS** (Ubuntu 22.04 LTS) for 99.99% uptime.
2.  **Broker Connection**: Set up a **Bybit API Key** with **Read-Write** permissions but **Withdrawals strictly disabled** and restricted to the fixed IP of your VPS.
3.  **Deployment Steps**:
    *   *Step 1 (Testnet)*: Run on Bybit Testnet for 1 week to confirm networking.
    *   *Step 2 (Micro-Sizing)*: Run live with $50 capital and 1x leverage for 2 weeks to measure real slippage.
    *   *Step 3 (Scaling)*: Gradually increase capital and configure Telegram notifications for live monitoring.
