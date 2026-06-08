import os
import json
import math
import random
from datetime import datetime, timezone
from typing import Dict, Any

class QuantValidator:
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

    def run_monte_carlo(self, metrics: dict, num_simulations: int = 100, drawdown_limit: float = 2.0) -> dict:
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
            mean_win = profit_factor * 0.01
            sigma_win = 0.005
            mu_win = math.log(mean_win) - 0.5 * sigma_win ** 2
            mean_loss = 0.01
            sigma_loss = 0.003
            mu_loss = math.log(mean_loss) - 0.5 * sigma_loss ** 2
        
        ruin_count = 0
        max_drawdowns = []
        
        # Set random seed for deterministic/testable results
        random.seed(42)
        
        for _ in range(num_simulations):
            equity = 100.0
            peak_equity = 100.0
            sim_max_dd = 0.0
            
            if use_bootstrap:
                # Non-parametric bootstrap: sample from actual trade returns
                sim_returns = random.choices(trade_returns, k=total_trades)
                for trade_return in sim_returns:
                    equity = equity * (1 + trade_return)
                    if equity > peak_equity:
                        peak_equity = equity
                    else:
                        dd = (peak_equity - equity) / peak_equity * 100.0
                        if dd > sim_max_dd:
                            sim_max_dd = dd
            else:
                # Parametric log-normal mixture model
                for _ in range(total_trades):
                    if random.random() < win_rate:
                        trade_return = random.lognormvariate(mu_win, sigma_win)
                    else:
                        trade_return = -random.lognormvariate(mu_loss, sigma_loss)
                        
                    equity = equity * (1 + trade_return)
                    if equity > peak_equity:
                        peak_equity = equity
                    else:
                        dd = (peak_equity - equity) / peak_equity * 100.0
                        if dd > sim_max_dd:
                            sim_max_dd = dd
                        
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
            "simulation_mode": simulation_mode
        }

    def generate_report(self, metrics: dict, constraints: dict, num_simulations: int = 100) -> dict:
        """
        Validates metrics, runs Monte Carlo, and writes the final validation report.
        Also generates a premium HTML validation dashboard.
        
        Args:
            metrics: dict of backtest metrics
            constraints: dict of risk constraints
            num_simulations: number of simulation paths to run
            
        Returns:
            dict containing the full generated report
        """
        drawdown_limit = constraints.get("max_drawdown_limit_pct", 2.0)
        
        validation_passed = self.validate_metrics(metrics, constraints)
        mc_results = self.run_monte_carlo(metrics, num_simulations, drawdown_limit)
        
        report = {
            "metrics": metrics,
            "constraints": constraints,
            "validation_passed": validation_passed,
            "monte_carlo_results": mc_results,
            "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        
        # Write validation report to validation_report.json
        report_path = os.path.join(self.payload_drop_dir, "validation_report.json")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
        # Write HTML dashboard
        self._generate_html_dashboard(report)
            
        return report

    def _generate_html_dashboard(self, report: dict):
        """
        Generates a visually stunning, self-contained HTML dashboard with Outfit font,
        glassmorphism, and Chart.js integration to display backtest and Monte Carlo results.
        """
        metrics = report["metrics"]
        constraints = report["constraints"]
        mc = report["monte_carlo_results"]
        passed = report["validation_passed"]
        
        verdict_class = "from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30" if passed else "from-rose-500/20 to-rose-500/5 text-rose-400 border-rose-500/30"
        verdict_text = "PASSED & APPROVED" if passed else "REJECTED (RISK LIMIT VIOLATION)"
        
        # Formatting floats safely
        sharpe = f"{metrics.get('sharpe_ratio'):.2f}" if metrics.get("sharpe_ratio") is not None else "N/A"
        max_dd = f"{metrics.get('max_drawdown'):.2f}%" if metrics.get("max_drawdown") is not None else "N/A"
        pf = f"{metrics.get('profit_factor'):.2f}" if metrics.get("profit_factor") is not None else "N/A"
        pf_float = metrics.get("profit_factor") or 1.5
        trades = metrics.get("total_trades") or 0
        
        limit_dd = f"{constraints.get('max_drawdown_limit_pct'):.2f}%"
        ruin_rate = f"{mc.get('risk_of_ruin') * 100:.2f}%"
        avg_dd = f"{mc.get('average_max_drawdown'):.2f}%"
        peak_dd = f"{mc.get('peak_simulated_drawdown'):.2f}%"
        
        win_rate = mc.get("win_rate_used", 0.50)
        win_rate_display = f"{win_rate * 100:.1f}%"
        
        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sovereign Quant Engine - Dashboard</title>
    <!-- Google Fonts & Tailwind -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Outfit', 'sans-serif'],
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{
            background: radial-gradient(circle at 50% 0%, #0f172a 0%, #020617 70%);
            min-height: 100vh;
        }}
        .glass-card {{
            background: rgba(15, 23, 42, 0.45);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }}
        .text-glow-violet {{
            text-shadow: 0 0 15px rgba(139, 92, 246, 0.4);
        }}
        .text-glow-cyan {{
            text-shadow: 0 0 15px rgba(6, 182, 212, 0.4);
        }}
    </style>
</head>
<body class="text-slate-100 font-sans p-6 md:p-12">
    <div class="max-w-6xl mx-auto space-y-8">
        
        <!-- Header -->
        <header class="flex flex-col md:flex-row md:items-center md:justify-between border-b border-slate-800 pb-6 gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
                    Sovereign Quant Engine
                </h1>
                <p class="text-sm text-slate-400 mt-1">Closed-Loop Validation & Performance Dashboard</p>
            </div>
            <div class="text-right text-xs text-slate-500">
                <p>Validated At: <span class="text-slate-300">{report["validated_at"]}</span></p>
                <p>System State: <span class="text-emerald-400 font-mono">ONLINE</span></p>
            </div>
        </header>

        <!-- Verdict Banner -->
        <div class="glass-card rounded-2xl p-6 border bg-gradient-to-br {verdict_class}">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <span class="text-xs uppercase font-semibold tracking-widest opacity-80">Supervisor Verdict</span>
                    <h2 class="text-2xl font-bold tracking-tight mt-1">{verdict_text}</h2>
                </div>
                <div class="text-right md:text-right">
                    <p class="text-xs opacity-75">Max Drawdown Limit Allowed</p>
                    <p class="text-2xl font-black font-mono">{limit_dd}</p>
                </div>
            </div>
        </div>

        <!-- Metrics Bento Grid -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
            <!-- Sharpe Ratio -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between hover:border-violet-500/30 transition-all duration-300 group">
                <div class="flex justify-between items-center text-slate-400 text-xs font-semibold tracking-wider uppercase">
                    <span>Sharpe Ratio</span>
                    <svg class="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                </div>
                <div class="mt-4">
                    <h3 class="text-4xl font-extrabold text-glow-violet text-violet-300 font-mono tracking-tight">{sharpe}</h3>
                    <p class="text-[10px] text-slate-500 mt-1">Target: &ge; {constraints.get('risk_to_reward_minimum', 1.5)/1.5:.2f}</p>
                </div>
            </div>

            <!-- Max Drawdown -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between hover:border-rose-500/30 transition-all duration-300 group">
                <div class="flex justify-between items-center text-slate-400 text-xs font-semibold tracking-wider uppercase">
                    <span>Max Drawdown</span>
                    <svg class="h-4 w-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6"/></svg>
                </div>
                <div class="mt-4">
                    <h3 class="text-4xl font-extrabold text-glow-cyan text-rose-400 font-mono tracking-tight">{max_dd}</h3>
                    <p class="text-[10px] text-slate-500 mt-1">Backtest peak drawdown</p>
                </div>
            </div>

            <!-- Profit Factor -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-300 group">
                <div class="flex justify-between items-center text-slate-400 text-xs font-semibold tracking-wider uppercase">
                    <span>Profit Factor</span>
                    <svg class="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                </div>
                <div class="mt-4">
                    <h3 class="text-4xl font-extrabold text-emerald-400 font-mono tracking-tight">{pf}</h3>
                    <p class="text-[10px] text-slate-500 mt-1">Target: &ge; 1.0</p>
                </div>
            </div>

            <!-- Risk of Ruin -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between hover:border-cyan-500/30 transition-all duration-300 group">
                <div class="flex justify-between items-center text-slate-400 text-xs font-semibold tracking-wider uppercase">
                    <span>Risk of Ruin</span>
                    <svg class="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                </div>
                <div class="mt-4">
                    <h3 class="text-4xl font-extrabold text-cyan-300 font-mono tracking-tight">{ruin_rate}</h3>
                    <p class="text-[10px] text-slate-500 mt-1">Drawdown &gt; {limit_dd} in simulations</p>
                </div>
            </div>
        </div>

        <!-- Main Chart & Monte Carlo Summary -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <!-- Chart -->
            <div class="glass-card rounded-2xl p-6 lg:col-span-2 space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold">Monte Carlo Equity Projections</h3>
                    <span class="text-xs text-slate-500">10 Random Sample Paths</span>
                </div>
                <div class="h-80 w-full">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>

            <!-- Stress Test Stats -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between space-y-6">
                <div>
                    <h3 class="text-lg font-bold mb-4">Monte Carlo Metrics</h3>
                    <div class="divide-y divide-slate-800 text-sm">
                        <div class="flex justify-between py-3">
                            <span class="text-slate-400">Total Simulations</span>
                            <span class="font-mono font-medium text-slate-200">{mc.get('num_simulations')}</span>
                        </div>
                        <div class="flex justify-between py-3">
                            <span class="text-slate-400">Average Max Drawdown</span>
                            <span class="font-mono font-medium text-rose-400">{avg_dd}</span>
                        </div>
                        <div class="flex justify-between py-3">
                            <span class="text-slate-400">Peak Simulated Drawdown</span>
                            <span class="font-mono font-medium text-rose-500">{peak_dd}</span>
                        </div>
                        <div class="flex justify-between py-3">
                            <span class="text-slate-400">Total Strategy Trades</span>
                            <span class="font-mono font-medium text-slate-200">{trades}</span>
                        </div>
                        <div class="flex justify-between py-3">
                            <span class="text-slate-400">Simulated Win Rate</span>
                            <span class="font-mono font-medium text-emerald-400">{win_rate_display}</span>
                        </div>
                    </div>
                </div>
                
                <div class="bg-slate-900/50 border border-slate-800 rounded-xl p-4 text-xs text-slate-400 space-y-2">
                    <p class="font-semibold text-slate-300">Methodology:</p>
                    <p>Paths are generated using a Log-Normal Mixture Model under a {win_rate_display} Win Rate and calibrated to a Profit Factor of {pf}. Winning trades follow LN(μ={pf_float * 0.01:.4f}, σ=0.005) and losing trades follow -LN(μ=0.01, σ=0.003).</p>
                </div>
            </div>

        </div>

    </div>

    <!-- Script to Generate Chart Paths -->
    <script>
        const ctx = document.getElementById('equityChart').getContext('2d');
        const numTrades = {trades};
        const profitFactor = parseFloat('{pf}') || 1.5;
        const winRate = parseFloat('{win_rate}') || 0.50;
        
        // Log-Normal Mixture Model parameters
        const meanWin = profitFactor * 0.01;
        const sigmaWin = 0.005;
        const muWin = Math.log(meanWin) - 0.5 * sigmaWin * sigmaWin;
        const meanLoss = 0.01;
        const sigmaLoss = 0.003;
        const muLoss = Math.log(meanLoss) - 0.5 * sigmaLoss * sigmaLoss;
        
        // Box-Muller transform for normal random numbers
        function randn() {{
            let u = 0, v = 0;
            while (u === 0) u = Math.random();
            while (v === 0) v = Math.random();
            return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
        }}

        // Generate 10 sample paths
        const datasets = [];
        const colors = [
            'rgba(139, 92, 246, 0.45)', // Violet
            'rgba(6, 182, 212, 0.45)',  // Cyan
            'rgba(16, 185, 129, 0.45)',  // Emerald
            'rgba(245, 158, 11, 0.45)',  // Amber
            'rgba(239, 68, 68, 0.3)',    // Rose
            'rgba(236, 72, 153, 0.3)',   // Pink
            'rgba(59, 130, 246, 0.3)',   // Blue
            'rgba(14, 165, 233, 0.3)',   // Sky
            'rgba(168, 85, 247, 0.3)',   // Purple
            'rgba(20, 184, 166, 0.3)',   // Teal
        ];

        const labels = Array.from({{ length: numTrades + 1 }}, (_, i) => i);

        // Generate paths using Log-Normal Mixture
        for (let p = 0; p < 10; p++) {{
            let equity = 100.0;
            const data = [equity];
            for (let t = 0; t < numTrades; t++) {{
                const isWin = Math.random() < winRate;
                let tradeReturn;
                if (isWin) {{
                    tradeReturn = Math.exp(muWin + sigmaWin * randn());
                }} else {{
                    tradeReturn = -Math.exp(muLoss + sigmaLoss * randn());
                }}
                equity = equity * (1 + tradeReturn);
                data.push(parseFloat(equity.toFixed(2)));
            }}
            
            datasets.push({{
                label: `Path ${{p+1}}`,
                data: data,
                borderColor: colors[p],
                borderWidth: 2,
                fill: false,
                pointRadius: 0,
                tension: 0.1
            }});
        }}

        // Calculate average path
        const averageData = [];
        for (let t = 0; t <= numTrades; t++) {{
            let sum = 0;
            for (let p = 0; p < 10; p++) {{
                sum += datasets[p].data[t];
            }}
            averageData.push(parseFloat((sum / 10).toFixed(2)));
        }}

        // Add Average Path highlighted
        datasets.push({{
            label: 'Average Path',
            data: averageData,
            borderColor: 'rgba(255, 255, 255, 0.95)',
            borderWidth: 4,
            fill: false,
            pointRadius: 0,
            tension: 0.1
        }});

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: datasets
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.05)'
                        }},
                        ticks: {{
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.05)'
                        }},
                        ticks: {{
                            color: '#64748b'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        html_path = os.path.join(self.payload_drop_dir, "validation_dashboard.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

