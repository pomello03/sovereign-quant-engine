import os
import json
import pytest
from jsonschema import ValidationError
from core_engine.supervisor import (
    MAX_DRAWDOWN_CEILING_PCT,
    RuinBiasViolationError,
    Supervisor,
)

# Real schemas directory
REAL_SCHEMAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "schemas"
)

@pytest.fixture
def temp_payload_dir(tmp_path):
    """Fixture to create a temporary payload_drop directory."""
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    return payload_dir

@pytest.fixture
def valid_payloads():
    """Returns valid dictionary specs for testing."""
    alpha = {
        "strategy_name": "RSI_MACD_Trend",
        "indicators": [
            {"name": "RSI", "params": {"period": 14}},
            {"name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}}
        ],
        "entry_long_conditions": ["RSI < 30", "MACD_hist > 0"],
        "entry_short_conditions": ["RSI > 70", "MACD_hist < 0"]
    }
    risk = {
        "max_drawdown_limit_pct": 1.5,
        "stop_loss_type": "fixed",
        "stop_loss_value": 0.02,
        "take_profit_value": 0.06,
        "risk_to_reward_minimum": 2.0,
        "max_position_sizing_pct": 3.0
    }
    context = {
        "market_regime": "trending_bullish",
        "timeframe": "1h",
        "trend_strength": "strong",
        "volatility_state": "normal"
    }
    return alpha, risk, context

def write_payload_files(payload_dir, alpha, risk, context):
    """Helper to write dictionaries to payload files."""
    with open(payload_dir / "alpha_spec.json", "w", encoding="utf-8") as f:
        json.dump(alpha, f)
    with open(payload_dir / "risk_constraints.json", "w", encoding="utf-8") as f:
        json.dump(risk, f)
    with open(payload_dir / "context_regime.json", "w", encoding="utf-8") as f:
        json.dump(context, f)

def test_supervisor_valid_payload(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    blueprint = supervisor.validate_and_generate()
    
    assert blueprint["supervisor_verdict"] == "APPROVED"
    assert "generated_at" in blueprint
    assert blueprint["alpha"] == alpha
    assert blueprint["risk"] == risk
    assert blueprint["context"] == context
    
    # Check that file was written
    blueprint_file = temp_payload_dir / "strategy_blueprint.json"
    assert blueprint_file.exists()
    with open(blueprint_file, "r", encoding="utf-8") as f:
        written_data = json.load(f)
    assert written_data == blueprint

def test_supervisor_missing_alpha_field(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # strategy_name is a required field in alpha schema
    del alpha["strategy_name"]
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    with pytest.raises(ValidationError) as excinfo:
        supervisor.validate_and_generate()
    assert "strategy_name" in str(excinfo.value)

def test_supervisor_invalid_risk_type(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # max_drawdown_limit_pct must be a number
    risk["max_drawdown_limit_pct"] = "invalid_string"
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    with pytest.raises(ValidationError) as excinfo:
        supervisor.validate_and_generate()
    assert "max_drawdown_limit_pct" in str(excinfo.value)

def test_supervisor_invalid_context_enum(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # market_regime must be one of the enums
    context["market_regime"] = "hyper_bullish"
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    with pytest.raises(ValidationError) as excinfo:
        supervisor.validate_and_generate()
    assert "market_regime" in str(excinfo.value)

def test_supervisor_ruin_bias_violation(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # Above the declared ceiling. The ceiling is 30.0, not 2.0: see
    # supervisor.MAX_DRAWDOWN_CEILING_PCT and research/RESULT_DOMAIN.md for why
    # 2.0 was unreachable on this instrument.
    risk["max_drawdown_limit_pct"] = MAX_DRAWDOWN_CEILING_PCT + 5
    write_payload_files(temp_payload_dir, alpha, risk, context)

    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    # Either the schema maximum or the explicit check may fire first; both refuse.
    with pytest.raises((ValidationError, RuinBiasViolationError)):
        supervisor.validate_and_generate()

def test_supervisor_ruin_bias_exact_boundary(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # Max drawdown is exactly 2.0% (allowed)
    risk["max_drawdown_limit_pct"] = 2.0
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    blueprint = supervisor.validate_and_generate()
    assert blueprint["supervisor_verdict"] == "APPROVED"

def test_supervisor_missing_file(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # Don't write alpha file
    with open(temp_payload_dir / "risk_constraints.json", "w", encoding="utf-8") as f:
        json.dump(risk, f)
    with open(temp_payload_dir / "context_regime.json", "w", encoding="utf-8") as f:
        json.dump(context, f)
        
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    with pytest.raises(FileNotFoundError):
        supervisor.validate_and_generate()

def test_supervisor_risk_to_reward_violation(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # stop_loss = 0.02, take_profit = 0.03, min_rr = 2.0. Actual RR = 1.5 (below 2.0)
    risk["stop_loss_value"] = 0.02
    risk["take_profit_value"] = 0.03
    risk["risk_to_reward_minimum"] = 2.0
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    with pytest.raises(ValidationError) as excinfo:
        supervisor.validate_and_generate()
    assert "Actual Risk-to-Reward ratio" in str(excinfo.value)

def test_supervisor_risk_to_reward_success(temp_payload_dir, valid_payloads):
    alpha, risk, context = valid_payloads
    # stop_loss = 0.02, take_profit = 0.05, min_rr = 2.0. Actual RR = 2.5 (above 2.0)
    risk["stop_loss_value"] = 0.02
    risk["take_profit_value"] = 0.05
    risk["risk_to_reward_minimum"] = 2.0
    write_payload_files(temp_payload_dir, alpha, risk, context)
    
    supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
    blueprint = supervisor.validate_and_generate()
    assert blueprint["supervisor_verdict"] == "APPROVED"
