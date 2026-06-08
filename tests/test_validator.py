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
        "total_trades": 50
    }
    
    mc_results = validator.run_monte_carlo(metrics, num_simulations=100, drawdown_limit=1.5)
    
    assert "risk_of_ruin" in mc_results
    assert "average_max_drawdown" in mc_results
    assert "peak_simulated_drawdown" in mc_results
    assert mc_results["num_simulations"] == 100
    assert mc_results["drawdown_limit_used"] == 1.5
    assert 0.0 <= mc_results["risk_of_ruin"] <= 1.0
    assert mc_results["average_max_drawdown"] >= 0.0

def test_generate_report(temp_payload_dir):
    validator = QuantValidator(payload_drop_dir=str(temp_payload_dir))
    metrics = {
        "sharpe_ratio": 2.0,
        "max_drawdown": -1.0,
        "profit_factor": 1.8,
        "total_trades": 40
    }
    constraints = {
        "max_drawdown_limit_pct": 1.5,
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
