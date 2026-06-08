import os
import json
import pytest
from unittest.mock import patch, MagicMock
from core_engine.developer_bridge import DeveloperBridge
from core_engine.supervisor import Supervisor
from core_engine.mcp_executor import MCPJesseRunner

@pytest.fixture
def temp_dirs(tmp_path):
    """Fixture to set up temporary directories for testing."""
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    workspace_dir = tmp_path / "jesse_workspace"
    workspace_dir.mkdir()
    return payload_dir, workspace_dir

@pytest.fixture
def dummy_blueprint():
    return {
        "alpha": {
            "strategy_name": "TestSovereignStrategy",
            "indicators": [
                {"name": "RSI", "params": {"period": 14}}
            ],
            "entry_long_conditions": ["RSI < 30"],
            "entry_short_conditions": ["RSI > 70"]
        },
        "risk": {
            "max_drawdown_limit_pct": 1.5,
            "stop_loss_type": "fixed",
            "stop_loss_value": 0.02,
            "take_profit_value": 0.06,
            "risk_to_reward_minimum": 2.0,
            "max_position_sizing_pct": 3.0
        },
        "context": {
            "market_regime": "trending_bullish",
            "timeframe": "1h",
            "trend_strength": "strong",
            "volatility_state": "normal"
        },
        "generated_at": "2026-06-08T12:00:00Z",
        "supervisor_verdict": "APPROVED"
    }

def write_blueprint_file(payload_dir, blueprint):
    with open(payload_dir / "strategy_blueprint.json", "w", encoding="utf-8") as f:
        json.dump(blueprint, f)

def test_generate_strategy_code(temp_dirs, dummy_blueprint):
    payload_dir, workspace_dir = temp_dirs
    bridge = DeveloperBridge(
        payload_drop_dir=str(payload_dir), 
        workspace_path=str(workspace_dir)
    )
    
    bridge.generate_strategy_code(dummy_blueprint)
    
    # Check that paths exist
    strategy_dir = workspace_dir / "strategies" / "SovereignStrategy"
    assert strategy_dir.exists()
    assert (strategy_dir / "params.py").exists()
    assert (strategy_dir / "__init__.py").exists()
    
    # Verify __init__.py content
    with open(strategy_dir / "__init__.py", "r", encoding="utf-8") as f:
        init_content = f.read()
    assert "class SovereignStrategy(Strategy):" in init_content
    assert "TestSovereignStrategy" in init_content
    assert "@property" in init_content
    assert "def rsi(self)" in init_content
    assert "ta.rsi(self.candles, period=14)" in init_content
    assert "return self.rsi < 30" in init_content
    assert "return self.rsi > 70" in init_content
    
    # Verify params.py content
    with open(strategy_dir / "params.py", "r", encoding="utf-8") as f:
        params_content = f.read()
    assert "params =" in params_content
    assert "RSI" in params_content

def test_generate_strategy_code_with_syntax_error(temp_dirs, dummy_blueprint):
    payload_dir, workspace_dir = temp_dirs
    bridge = DeveloperBridge(
        payload_drop_dir=str(payload_dir), 
        workspace_path=str(workspace_dir)
    )
    
    bridge.simulate_compilation_error_on_first_try = True
    bridge.generate_strategy_code(dummy_blueprint)
    
    strategy_dir = workspace_dir / "strategies" / "SovereignStrategy"
    with open(strategy_dir / "__init__.py", "r", encoding="utf-8") as f:
        init_content = f.read()
        
    # Check that intentional syntax error was written (e.g. missing colon after class name)
    assert "class SovereignStrategy(Strategy)\n" in init_content

def test_execute_closed_loop_success_first_try(temp_dirs, dummy_blueprint):
    payload_dir, workspace_dir = temp_dirs
    write_blueprint_file(payload_dir, dummy_blueprint)
    
    mock_runner = MagicMock(spec=MCPJesseRunner)
    mock_runner.run_backtest.return_value = {
        "status": "SUCCESS",
        "metrics": {"sharpe_ratio": 1.9, "max_drawdown": -1.1, "total_trades": 15, "profit_factor": 1.6},
        "stdout": "Jesse run succeeded",
        "stderr": ""
    }
    
    bridge = DeveloperBridge(
        runner=mock_runner,
        payload_drop_dir=str(payload_dir),
        workspace_path=str(workspace_dir)
    )
    
    result = bridge.execute_closed_loop("2021-01-01", "2021-02-01")
    
    assert result["status"] == "SUCCESS"
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["status"] == "SUCCESS"
    assert result["metrics"]["sharpe_ratio"] == 1.9
    mock_runner.run_backtest.assert_called_once_with("2021-01-01", "2021-02-01")

def test_execute_closed_loop_self_correcting(temp_dirs, dummy_blueprint):
    payload_dir, workspace_dir = temp_dirs
    write_blueprint_file(payload_dir, dummy_blueprint)
    
    mock_runner = MagicMock(spec=MCPJesseRunner)
    # 1st call: compilation error. 2nd call: success.
    mock_runner.run_backtest.side_effect = [
        {
            "status": "COMPILATION_ERROR",
            "stdout": "",
            "stderr": "SyntaxError: invalid syntax"
        },
        {
            "status": "SUCCESS",
            "metrics": {"sharpe_ratio": 2.2, "max_drawdown": -0.8, "total_trades": 25, "profit_factor": 1.9},
            "stdout": "Jesse run succeeded after fix",
            "stderr": ""
        }
    ]
    
    bridge = DeveloperBridge(
        runner=mock_runner,
        payload_drop_dir=str(payload_dir),
        workspace_path=str(workspace_dir)
    )
    # Set error simulation true to trigger the first compile error mock sequence
    bridge.simulate_compilation_error_on_first_try = True
    
    result = bridge.execute_closed_loop("2021-01-01", "2021-02-01", max_retries=3)
    
    assert result["status"] == "SUCCESS"
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["status"] == "COMPILATION_ERROR"
    assert result["attempts"][1]["status"] == "SUCCESS"
    assert result["metrics"]["sharpe_ratio"] == 2.2
    assert mock_runner.run_backtest.call_count == 2

def test_execute_closed_loop_max_retries_reached(temp_dirs, dummy_blueprint):
    payload_dir, workspace_dir = temp_dirs
    write_blueprint_file(payload_dir, dummy_blueprint)
    
    mock_runner = MagicMock(spec=MCPJesseRunner)
    # Always returns compilation error
    mock_runner.run_backtest.return_value = {
        "status": "COMPILATION_ERROR",
        "stdout": "",
        "stderr": "SyntaxError: invalid syntax"
    }
    
    bridge = DeveloperBridge(
        runner=mock_runner,
        payload_drop_dir=str(payload_dir),
        workspace_path=str(workspace_dir)
    )
    bridge.simulate_compilation_error_on_first_try = True
    
    result = bridge.execute_closed_loop("2021-01-01", "2021-02-01", max_retries=3)
    
    assert result["status"] == "COMPILATION_ERROR"
    assert len(result["attempts"]) == 3
    assert result["attempts"][0]["status"] == "COMPILATION_ERROR"
    assert result["attempts"][1]["status"] == "COMPILATION_ERROR"
    assert result["attempts"][2]["status"] == "COMPILATION_ERROR"
    assert mock_runner.run_backtest.call_count == 3
