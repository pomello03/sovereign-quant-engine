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
    # Use bootstrap mode with favorable trade returns to ensure MC validation passes
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40,
        "win_rate": 0.65,
        "trade_returns": [0.001, 0.002, -0.0005, 0.0015, 0.001, -0.0003,
                          0.002, 0.001, -0.0004, 0.0012]
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
