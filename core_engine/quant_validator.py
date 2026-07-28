import os
import json
import math
import random
from datetime import datetime, timezone
from typing import Dict, Any
from core_engine.state_io import atomic_write_json

class QuantValidator:
    # Minimum number of real, per-trade returns required for an unbiased
    # Monte Carlo stress test. Below this, results are statistically
    # meaningless and an inactive strategy (0 trades -> 0% ruin) would
    # otherwise be validated as a false positive (Vuln 5).
    MIN_REAL_TRADES = 30

    def __init__(self, payload_drop_dir: str = None):
        """
        QuantValidator evaluates backtest metrics and runs Monte Carlo simulations.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.payload_drop_dir = payload_drop_dir or os.path.join(base_dir, "payload_drop")

    def validate_metrics(self, metrics: dict, constraints: dict) -> bool:
        """
        Validates the extracted backtest metrics against risk constraints.
        
        Args:
            metrics: dict of backtest metrics (sharpe_ratio, max_drawdown, profit_factor)
            constraints: dict of risk constraints (max_drawdown_limit_pct, etc.)
            
        Returns:
            bool: True if the metrics meet the constraints, False otherwise.
        """
        # 1. Max Drawdown Check (Drawdown is often negative in Jesse output, so abs() is used)
        max_dd = metrics.get("max_drawdown")
        limit_pct = constraints.get("max_drawdown_limit_pct")
        if max_dd is not None and limit_pct is not None:
            if abs(max_dd) > limit_pct:
                return False

        # 2. Sharpe Ratio Check
        sharpe = metrics.get("sharpe_ratio")
        min_sharpe = constraints.get("sharpe_ratio_minimum", constraints.get("min_sharpe", 1.0))
        if sharpe is not None and min_sharpe is not None:
            if sharpe < min_sharpe:
                return False

        # 3. Profit Factor Check
        pf = metrics.get("profit_factor")
        min_pf = constraints.get("profit_factor_minimum", constraints.get("min_profit_factor", 1.0))
        if pf is not None and min_pf is not None:
            if pf < min_pf:
                return False

        return True

    def validate_with_monte_carlo(self, metrics: dict, constraints: dict,
                                  mc_results: dict,
                                  max_risk_of_ruin: float = 0.05) -> bool:
        """
        Full validation: base metric checks + Monte Carlo stress test results.

        A strategy must pass all base metric constraints AND the Monte Carlo
        stress test must show acceptable risk of ruin and average drawdown.

        Args:
            metrics: dict of backtest metrics
            constraints: dict of risk constraints
            mc_results: dict returned by run_monte_carlo()
            max_risk_of_ruin: maximum acceptable probability of ruin (default 5%)

        Returns:
            bool: True only if both base metrics and MC stress test pass.
        """
        if not self.validate_metrics(metrics, constraints):
            return False

        # Empty/inactive-trades bypass guard (Vuln 5): a strategy that barely
        # trades has ~0% drawdown and would sail through with 0% risk of ruin.
        # An unbiased stress test requires a sufficient sample of REAL per-trade
        # returns, so we demand bootstrap mode with >= MIN_REAL_TRADES samples.
        if mc_results.get("simulation_mode") != "bootstrap":
            return False
        if mc_results.get("real_trades_used", 0) < self.MIN_REAL_TRADES:
            return False

        # Monte Carlo Risk of Ruin gate
        if mc_results.get("risk_of_ruin", 1.0) > max_risk_of_ruin:
            return False

        # Monte Carlo Average Max Drawdown gate
        dd_limit = constraints.get("max_drawdown_limit_pct", 2.0)
        if mc_results.get("average_max_drawdown", float("inf")) > dd_limit:
            return False

        return True

    def run_monte_carlo(self, metrics: dict, num_simulations: int = 100, drawdown_limit: float = 2.0, seed: int = None,
                        collect_trajectories: int = 0) -> dict:
        """
        Runs a Monte Carlo simulation of trade returns based on metrics to estimate
        the probability of drawdown exceeding the limit (Risk of Ruin).

        Supports two modes:
        - Non-Parametric Bootstrap: when metrics contains a non-empty 'trade_returns' list,
          samples from actual trade returns with replacement.
        - Parametric Log-Normal Mixture: when no trade_returns are available, generates
          synthetic returns using separate log-normal distributions for wins and losses,
          calibrated from the strategy's profit factor and win rate.

        Args:
            metrics: dict of backtest metrics
            num_simulations: number of simulation paths to run
            drawdown_limit: drawdown limit in percent (e.g. 2.0 for 2.0%)
            seed: optional random seed for reproducible results (default None = stochastic)
            collect_trajectories: number of representative equity/drawdown paths to keep
                in the result (keys 'equity_trajectories' / 'drawdown_trajectories'),
                used by the dashboard to plot the stochastic dispersion

        Returns:
            dict with simulation results (risk_of_ruin, average_max_drawdown, etc.)
        """
        total_trades = metrics.get("total_trades") or 100
        # Ensure total_trades is at least 10 for simulation
        total_trades = max(total_trades, 10)
        
        profit_factor = metrics.get("profit_factor") or 1.5
        if profit_factor <= 0:
            profit_factor = 1.5
            
        win_rate = metrics.get("win_rate")
        if win_rate is None or not (0.0 < win_rate < 1.0):
            win_rate = 0.50
        
        # Determine simulation mode
        trade_returns = metrics.get("trade_returns")
        use_bootstrap = isinstance(trade_returns, list) and len(trade_returns) > 0
        simulation_mode = "bootstrap" if use_bootstrap else "parametric_lognormal"
        
        # Pre-compute log-normal parameters for parametric mode
        if not use_bootstrap:
            # NOTE: no scaling by the backtest's aggregate max_drawdown. Doing so
            # would leak the realized outcome into the simulation (look-ahead
            # bias, Vuln 5). Parametric mode is a diagnostic/visualization
            # fallback only and is rejected by validate_with_monte_carlo, which
            # requires empirical per-trade returns (bootstrap mode).
            mean_win = profit_factor * 0.01
            sigma_win = 0.005
            mu_win = math.log(mean_win) - 0.5 * sigma_win ** 2
            mean_loss = 0.01
            sigma_loss = 0.003
            mu_loss = math.log(mean_loss) - 0.5 * sigma_loss ** 2
        
        ruin_count = 0
        max_drawdowns = []
        equity_trajectories = []
        drawdown_trajectories = []

        # Set random seed if provided (for deterministic/testable results)
        if seed is not None:
            random.seed(seed)

        for sim_index in range(num_simulations):
            equity = 100.0
            peak_equity = 100.0
            sim_max_dd = 0.0

            collect = sim_index < collect_trajectories
            if collect:
                equity_path = [100.0]
                drawdown_path = [0.0]

            if use_bootstrap:
                # Non-parametric bootstrap: sample from actual trade returns
                sim_returns = random.choices(trade_returns, k=total_trades)
            else:
                # Parametric log-normal mixture model
                sim_returns = [
                    random.lognormvariate(mu_win, sigma_win)
                    if random.random() < win_rate
                    else -random.lognormvariate(mu_loss, sigma_loss)
                    for _ in range(total_trades)
                ]

            for trade_return in sim_returns:
                equity = max(0.0, equity * (1 + trade_return))
                if equity > peak_equity:
                    peak_equity = equity
                    dd = 0.0
                else:
                    dd = (peak_equity - equity) / peak_equity * 100.0
                    if dd > sim_max_dd:
                        sim_max_dd = dd
                if collect:
                    equity_path.append(round(equity, 2))
                    drawdown_path.append(round(dd, 3))

            if collect:
                equity_trajectories.append(equity_path)
                drawdown_trajectories.append(drawdown_path)

            max_drawdowns.append(sim_max_dd)
            if sim_max_dd > drawdown_limit:
                ruin_count += 1

        risk_of_ruin = ruin_count / num_simulations
        avg_max_dd = sum(max_drawdowns) / num_simulations
        peak_simulated_dd = max(max_drawdowns)

        return {
            "risk_of_ruin": risk_of_ruin,
            "average_max_drawdown": avg_max_dd,
            "peak_simulated_drawdown": peak_simulated_dd,
            "num_simulations": num_simulations,
            "drawdown_limit_used": drawdown_limit,
            "win_rate_used": win_rate,
            "simulation_mode": simulation_mode,
            "real_trades_used": len(trade_returns) if use_bootstrap else 0,
            "equity_trajectories": equity_trajectories,
            "drawdown_trajectories": drawdown_trajectories
        }

    def _build_backtest_curves(self, trade_returns):
        """
        Builds the real backtest equity and drawdown curves from the raw trade
        returns list. Returns (None, None) when no trade returns are available.
        """
        if not isinstance(trade_returns, list) or len(trade_returns) == 0:
            return None, None

        equity = 100.0
        peak_equity = 100.0
        equity_curve = [100.0]
        drawdown_curve = [0.0]
        for trade_return in trade_returns:
            equity = max(0.0, equity * (1 + trade_return))
            if equity > peak_equity:
                peak_equity = equity
                dd = 0.0
            else:
                dd = (peak_equity - equity) / peak_equity * 100.0
            equity_curve.append(round(equity, 2))
            drawdown_curve.append(round(dd, 3))
        return equity_curve, drawdown_curve

    def generate_report(self, metrics: dict, constraints: dict, num_simulations: int = 100,
                        optimization_history: list = None, strategy_code: str = None,
                        blueprint: dict = None, mc_results: dict = None) -> dict:
        """
        Validates metrics, runs Monte Carlo, and writes the final validation report.
        Also generates the premium HTML validation dashboard (two-file architecture:
        validation_dashboard.html shell + dashboard_app.js logic).

        Args:
            metrics: dict of backtest metrics
            constraints: dict of risk constraints
            num_simulations: number of simulation paths to run
            optimization_history: list of RiskOptimizer iteration records
            strategy_code: generated Python strategy source (shown in the code drawer)
            blueprint: approved strategy blueprint (sidebar parameters)
            mc_results: precomputed run_monte_carlo() output; when provided the
                simulation is not re-run (used by RiskOptimizer to avoid double work)

        Returns:
            dict containing the full generated report
        """
        drawdown_limit = constraints.get("max_drawdown_limit_pct", 2.0)

        if mc_results is None:
            mc_results = self.run_monte_carlo(metrics, num_simulations, drawdown_limit,
                                              collect_trajectories=50)
        # Full validation: base metrics + Monte Carlo stress test
        validation_passed = self.validate_with_monte_carlo(
            metrics, constraints, mc_results
        )

        backtest_equity_curve, backtest_drawdown_curve = self._build_backtest_curves(
            metrics.get("trade_returns")
        )

        report = {
            "metrics": metrics,
            "constraints": constraints,
            "validation_passed": validation_passed,
            # True when the metrics came from the mock path (Jesse absent or no
            # candles), i.e. every number in this report is fabricated.
            "is_mock": bool(metrics.get("is_mock", False)),
            "monte_carlo_results": mc_results,
            "optimization_history": optimization_history or [],
            "strategy_blueprint": blueprint,
            "strategy_code": strategy_code,
            "backtest_equity_curve": backtest_equity_curve,
            "backtest_drawdown_curve": backtest_drawdown_curve,
            "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        # Write validation report atomically (Vuln 1/3): a concurrent dashboard
        # or monitor reader never sees a half-written report.
        report_path = os.path.join(self.payload_drop_dir, "validation_report.json")
        atomic_write_json(report_path, report, indent=2)

        # Write HTML dashboard
        self._generate_html_dashboard(report)

        return report

    def _generate_html_dashboard(self, report: dict):
        """
        Generates the two-file premium glassmorphic dashboard in payload_drop/:
        - validation_dashboard.html: static HTML shell (from core_engine/templates/dashboard.html)
          with the report JSON injected on the REPORT_JSON_PLACEHOLDER marker.
        - dashboard_app.js: JS/Chart.js logic, copied verbatim from
          core_engine/templates/dashboard_app.js.
        """
        templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

        with open(os.path.join(templates_dir, "dashboard.html"), "r", encoding="utf-8") as f:
            html_template = f.read()

        # `</` is escaped so the embedded JSON can never close the <script> tag early
        report_json = json.dumps(report).replace("</", "<\\/")
        html_content = html_template.replace("/* REPORT_JSON_PLACEHOLDER */", report_json)

        os.makedirs(self.payload_drop_dir, exist_ok=True)
        html_path = os.path.join(self.payload_drop_dir, "validation_dashboard.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        with open(os.path.join(templates_dir, "dashboard_app.js"), "r", encoding="utf-8") as f:
            app_js = f.read()
        js_path = os.path.join(self.payload_drop_dir, "dashboard_app.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(app_js)
