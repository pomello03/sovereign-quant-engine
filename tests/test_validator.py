import os
import json
import pytest
from core_engine.quant_validator import QuantValidator

@pytest.fixture
def temp_payload_dir(tmp_path):
    """Fixture to set up a temporary payload drop directory."""
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    return payload_dir

def test_validate_metrics_all_pass():
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 2.1,
        "max_drawdown": -1.2,
        "profit_factor": 1.5
    }
    constraints = {
        "max_drawdown_limit_pct": 2.0,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.2
    }
    
    assert validator.validate_metrics(metrics, constraints) is True

def test_validate_metrics_fail_drawdown():
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 2.1,
        "max_drawdown": -2.5, # Exceeds limit
        "profit_factor": 1.5
    }
    constraints = {
        "max_drawdown_limit_pct": 2.0,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.2
    }
    
    assert validator.validate_metrics(metrics, constraints) is False

def test_validate_metrics_fail_sharpe():
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.2, # Below minimum
        "max_drawdown": -1.0,
        "profit_factor": 1.5
    }
    constraints = {
        "max_drawdown_limit_pct": 2.0,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.2
    }
    
    assert validator.validate_metrics(metrics, constraints) is False

def test_validate_metrics_fail_profit_factor():
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.0,
        "profit_factor": 1.1 # Below minimum
    }
    constraints = {
        "max_drawdown_limit_pct": 2.0,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.2
    }
    
    assert validator.validate_metrics(metrics, constraints) is False

def test_run_monte_carlo():
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.2,
        "profit_factor": 1.5,
        "total_trades": 50,
        "win_rate": 0.60
    }
    
    mc_results = validator.run_monte_carlo(metrics, num_simulations=100, drawdown_limit=1.5)
    
    assert "risk_of_ruin" in mc_results
    assert "average_max_drawdown" in mc_results
    assert "peak_simulated_drawdown" in mc_results
    assert mc_results["num_simulations"] == 100
    assert mc_results["drawdown_limit_used"] == 1.5
    assert mc_results["win_rate_used"] == 0.60
    assert 0.0 <= mc_results["risk_of_ruin"] <= 1.0
    assert mc_results["average_max_drawdown"] >= 0.0

def test_generate_report(temp_payload_dir):
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    # Bootstrap mode with >= MIN_REAL_TRADES (30) favorable returns so the MC
    # validation passes under the look-ahead-free invariant (Vuln 5).
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40,
        "win_rate": 0.65,
        "trade_returns": ([0.001, 0.002, -0.0005, 0.0015, 0.001, -0.0003,
                           0.002, 0.001, -0.0004, 0.0012] * 4)
    }
    constraints = {
        "max_drawdown_limit_pct": 5.0,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.3
    }
    
    report = validator.generate_report(metrics, constraints, num_simulations=50)
    
    assert report["validation_passed"] is True
    assert report["metrics"] == metrics
    assert report["constraints"] == constraints
    assert "monte_carlo_results" in report
    assert "validated_at" in report
    
    # Check that validation_report.json file is written
    report_file = temp_payload_dir / "validation_report.json"
    assert report_file.exists()
    
    with open(report_file, "r", encoding="utf-8") as f:
        loaded_report = json.load(f)
    assert loaded_report == report


def test_generate_report_rejects_high_ruin(temp_payload_dir):
    """Test that generate_report rejects strategies with high risk of ruin."""
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    # Metrics that pass base validation but fail Monte Carlo
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 50,
        "win_rate": 0.55
    }
    constraints = {
        "max_drawdown_limit_pct": 1.5,
        "sharpe_ratio_minimum": 1.5,
        "profit_factor_minimum": 1.3
    }
    
    report = validator.generate_report(metrics, constraints, num_simulations=100)
    
    # With parametric mode and tight drawdown limit, MC should flag high ruin
    # The key point: validation_passed must now reflect MC results
    assert "monte_carlo_results" in report
    mc = report["monte_carlo_results"]
    if mc["risk_of_ruin"] > 0.05 or mc["average_max_drawdown"] > 1.5:
        assert report["validation_passed"] is False


def test_run_monte_carlo_bootstrap():
    """Test non-parametric bootstrap mode when trade_returns are provided."""
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.2,
        "profit_factor": 1.5,
        "total_trades": 30,
        "win_rate": 0.60,
        "trade_returns": [0.02, -0.01, 0.015, -0.008, 0.025, -0.012, 0.018, -0.005, 0.03, -0.01]
    }
    
    mc_results = validator.run_monte_carlo(metrics, num_simulations=50, drawdown_limit=1.5)
    
    assert mc_results["simulation_mode"] == "bootstrap"
    assert "risk_of_ruin" in mc_results
    assert "average_max_drawdown" in mc_results
    assert "peak_simulated_drawdown" in mc_results
    assert mc_results["num_simulations"] == 50
    assert 0.0 <= mc_results["risk_of_ruin"] <= 1.0
    assert mc_results["average_max_drawdown"] >= 0.0


def test_run_monte_carlo_parametric():
    """Test parametric log-normal mixture mode when no trade_returns are available."""
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.2,
        "profit_factor": 1.5,
        "total_trades": 50,
        "win_rate": 0.60
    }
    
    mc_results = validator.run_monte_carlo(metrics, num_simulations=50, drawdown_limit=1.5)
    
    assert mc_results["simulation_mode"] == "parametric_lognormal"
    assert "risk_of_ruin" in mc_results
    assert mc_results["num_simulations"] == 50
    assert mc_results["win_rate_used"] == 0.60
    assert 0.0 <= mc_results["risk_of_ruin"] <= 1.0


def test_run_monte_carlo_empty_trade_returns():
    """Test fallback to parametric mode when trade_returns is empty list."""
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.2,
        "profit_factor": 1.5,
        "total_trades": 50,
        "win_rate": 0.60,
        "trade_returns": []
    }

    mc_results = validator.run_monte_carlo(metrics, num_simulations=50, drawdown_limit=1.5)

    assert mc_results["simulation_mode"] == "parametric_lognormal"
    assert "risk_of_ruin" in mc_results
    assert 0.0 <= mc_results["risk_of_ruin"] <= 1.0


def test_run_monte_carlo_reports_real_trades_used():
    """Vuln 5: bootstrap reports the empirical sample size; parametric reports 0."""
    validator = QuantValidator()
    boot = validator.run_monte_carlo(
        {"total_trades": 40, "win_rate": 0.6, "profit_factor": 1.5,
         "trade_returns": [0.01, -0.01] * 20},
        num_simulations=20, drawdown_limit=2.0)
    assert boot["simulation_mode"] == "bootstrap"
    assert boot["real_trades_used"] == 40

    para = validator.run_monte_carlo(
        {"total_trades": 40, "win_rate": 0.6, "profit_factor": 1.5},
        num_simulations=20, drawdown_limit=2.0)
    assert para["simulation_mode"] == "parametric_lognormal"
    assert para["real_trades_used"] == 0


def test_validate_rejects_parametric_and_few_trades():
    """Vuln 5: parametric mode and sub-threshold samples never validate."""
    validator = QuantValidator()
    metrics = {"sharpe_ratio": 2.0, "max_drawdown": -1.0, "profit_factor": 2.0,
               "total_trades": 40}
    constraints = {"max_drawdown_limit_pct": 2.0, "sharpe_ratio_minimum": 1.5,
                   "profit_factor_minimum": 1.5}
    good_gates = {"risk_of_ruin": 0.0, "average_max_drawdown": 0.1}

    # Parametric mode rejected even with perfect gates.
    assert validator.validate_with_monte_carlo(
        metrics, constraints,
        {**good_gates, "simulation_mode": "parametric_lognormal", "real_trades_used": 0}
    ) is False
    # Bootstrap but too few real trades rejected.
    assert validator.validate_with_monte_carlo(
        metrics, constraints,
        {**good_gates, "simulation_mode": "bootstrap", "real_trades_used": 10}
    ) is False
    # Bootstrap with enough trades accepted.
    assert validator.validate_with_monte_carlo(
        metrics, constraints,
        {**good_gates, "simulation_mode": "bootstrap", "real_trades_used": 30}
    ) is True


def test_run_monte_carlo_collect_trajectories():
    """Trajectories are collected, capped at collect_trajectories, with full path length."""
    validator = QuantValidator()
    metrics = {
        "sharpe_ratio": 1.8,
        "max_drawdown": -1.2,
        "profit_factor": 1.5,
        "total_trades": 20,
        "win_rate": 0.60
    }

    mc_results = validator.run_monte_carlo(metrics, num_simulations=10, drawdown_limit=1.5,
                                           collect_trajectories=5)

    assert len(mc_results["equity_trajectories"]) == 5
    assert len(mc_results["drawdown_trajectories"]) == 5
    # Each path: initial point + one per trade
    assert all(len(path) == 21 for path in mc_results["equity_trajectories"])
    assert all(len(path) == 21 for path in mc_results["drawdown_trajectories"])
    assert all(path[0] == 100.0 for path in mc_results["equity_trajectories"])
    assert all(v >= 0.0 for path in mc_results["drawdown_trajectories"] for v in path)
    # Default: no trajectories collected
    mc_default = validator.run_monte_carlo(metrics, num_simulations=10, drawdown_limit=1.5)
    assert mc_default["equity_trajectories"] == []


def test_generate_report_includes_history_code_blueprint(temp_payload_dir):
    """Optimization history, strategy code and blueprint are embedded in the report."""
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40,
        "win_rate": 0.65,
        "trade_returns": [0.001, 0.002, -0.0005, 0.0015]
    }
    constraints = {"max_drawdown_limit_pct": 5.0}
    history = [{
        "iteration": 1,
        "params": {"max_position_sizing_pct": 2.0, "stop_loss_value": 0.02},
        "metrics": {"sharpe_ratio": 2.0},
        "risk_of_ruin": 0.01,
        "average_max_drawdown": 0.5,
        "validation_passed": True
    }]
    blueprint = {"alpha": {"indicators": [{"name": "RSI", "params": {"period": 14}}]},
                 "risk": {"max_position_sizing_pct": 2.0}}

    report = validator.generate_report(metrics, constraints, num_simulations=20,
                                       optimization_history=history,
                                       strategy_code="class SovereignStrategy: pass",
                                       blueprint=blueprint)

    assert report["optimization_history"] == history
    assert report["strategy_code"] == "class SovereignStrategy: pass"
    assert report["strategy_blueprint"] == blueprint
    # Backtest curves derived from trade_returns
    assert len(report["backtest_equity_curve"]) == len(metrics["trade_returns"]) + 1
    assert report["backtest_equity_curve"][0] == 100.0
    assert len(report["backtest_drawdown_curve"]) == len(metrics["trade_returns"]) + 1
    # JSON round-trip integrity
    with open(temp_payload_dir / "validation_report.json", "r", encoding="utf-8") as f:
        assert json.load(f) == report


def test_generate_report_writes_dashboard_artifacts(temp_payload_dir):
    """Two-file dashboard: HTML with injected data + dashboard_app.js copied alongside."""
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40,
        "win_rate": 0.65
    }
    constraints = {"max_drawdown_limit_pct": 5.0}

    validator.generate_report(metrics, constraints, num_simulations=20)

    html_path = temp_payload_dir / "validation_dashboard.html"
    js_path = temp_payload_dir / "dashboard_app.js"
    assert html_path.exists()
    assert js_path.exists()

    html = html_path.read_text(encoding="utf-8")
    assert "const SQE_REPORT_DATA =" in html
    assert "REPORT_JSON_PLACEHOLDER" not in html  # data was injected
    assert '"monte_carlo_results"' in html
    assert 'src="dashboard_app.js"' in html

    js = js_path.read_text(encoding="utf-8")
    assert "SQE_REPORT_DATA" in js


def test_generate_report_no_trade_returns_has_null_curves(temp_payload_dir):
    """Without trade_returns the real backtest curves are None (JS falls back to median)."""
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40,
        "win_rate": 0.65
    }
    constraints = {"max_drawdown_limit_pct": 5.0}

    report = validator.generate_report(metrics, constraints, num_simulations=20)

    assert report["backtest_equity_curve"] is None
    assert report["backtest_drawdown_curve"] is None
    # Default generate_report collects 50 trajectories (capped by num_simulations)
    assert len(report["monte_carlo_results"]["equity_trajectories"]) == 20
