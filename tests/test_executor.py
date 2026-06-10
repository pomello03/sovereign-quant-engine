import pytest
from unittest.mock import patch, MagicMock
from core_engine.mcp_executor import MCPJesseRunner

def test_parse_jesse_output_table():
    runner = MCPJesseRunner("./jesse_workspace")
    stdout_text = """
    --------------------------------------------------
    exchange                 | Bitfinex
    symbol                   | BTC-USD
    timeframe                | 4h
    strategy                 | MyStrategy
    start date               | 2021-01-01
    end date                 | 2021-02-01
    --------------------------------------------------
    total trades             | 24
    total profit             | $1,250.00 (12.50%)
    sharpe ratio             | 1.84
    profit factor            | 1.56
    max drawdown             | -4.50%
    win rate                 | 55.0%
    --------------------------------------------------
    """
    metrics = runner._parse_jesse_output(stdout_text)
    assert metrics["sharpe_ratio"] == 1.84
    assert metrics["max_drawdown"] == -4.50
    assert metrics["total_trades"] == 24
    assert metrics["profit_factor"] == 1.56
    assert metrics["win_rate"] == 0.55

def test_parse_jesse_output_colon():
    runner = MCPJesseRunner("./jesse_workspace")
    stdout_text = """
    exchange: Bitfinex
    symbol: BTC-USD
    total trades: 15
    sharpe ratio: 2.1
    profit factor: 1.8
    max drawdown: -3.2
    win rate: 0.60
    """
    metrics = runner._parse_jesse_output(stdout_text)
    assert metrics["sharpe_ratio"] == 2.1
    assert metrics["max_drawdown"] == -3.2
    assert metrics["total_trades"] == 15
    assert metrics["profit_factor"] == 1.8
    assert metrics["win_rate"] == 0.60

def test_parse_jesse_output_regex_fallback():
    runner = MCPJesseRunner("./jesse_workspace")
    stdout_text = """
    We finished the backtest.
    Sharpe Ratio is 2.5.
    Total trades completed: 100.
    Maximum drawdown was calculated as -8.5%.
    Profit factor is 2.0.
    Win rate achieved: 58%.
    """
    metrics = runner._parse_jesse_output(stdout_text)
    assert metrics["sharpe_ratio"] == 2.5
    assert metrics["max_drawdown"] == -8.5
    assert metrics["total_trades"] == 100
    assert metrics["profit_factor"] == 2.0
    assert metrics["win_rate"] == 0.58

@patch("shutil.which", return_value=None)
def test_run_backtest_jesse_not_installed(mock_which):
    runner = MCPJesseRunner("./jesse_workspace")
    result = runner.run_backtest("2021-01-01", "2021-02-01")
    assert result["status"] == "SUCCESS"
    assert result["metrics"]["sharpe_ratio"] == 1.85
    assert result["metrics"]["total_trades"] == 40
    # Mock now ships a real per-trade returns sample for unbiased bootstrap MC (Vuln 5)
    assert len(result["metrics"]["trade_returns"]) >= 30
    assert "Mock execution" in result["stdout"]

@patch("shutil.which", return_value="/usr/local/bin/jesse")
@patch("subprocess.run")
def test_run_backtest_success(mock_run, mock_which):
    mock_response = MagicMock()
    mock_response.returncode = 0
    mock_response.stdout = """
    total trades             | 30
    sharpe ratio             | 2.0
    profit factor            | 1.5
    max drawdown             | -5.0%
    """
    mock_response.stderr = ""
    mock_run.return_value = mock_response

    runner = MCPJesseRunner("./jesse_workspace")
    result = runner.run_backtest("2021-01-01", "2021-02-01")
    assert result["status"] == "SUCCESS"
    assert result["metrics"]["sharpe_ratio"] == 2.0
    assert result["metrics"]["total_trades"] == 30
    assert result["metrics"]["profit_factor"] == 1.5
    assert result["metrics"]["max_drawdown"] == -5.0

@patch("shutil.which", return_value="/usr/local/bin/jesse")
@patch("subprocess.run")
def test_run_backtest_missing_candles_mock_fallback(mock_run, mock_which):
    mock_response = MagicMock()
    mock_response.returncode = 1
    mock_response.stdout = ""
    mock_response.stderr = "jesse.exceptions.CandleNotFoundInDatabase: No candles found for Bitfinex BTC-USD"
    mock_run.return_value = mock_response

    runner = MCPJesseRunner("./jesse_workspace")
    result = runner.run_backtest("2021-01-01", "2021-02-01")
    assert result["status"] == "SUCCESS"
    assert result["metrics"]["sharpe_ratio"] == 1.85
    assert "Mocked due to missing historical data" in result["stdout"]

@patch("shutil.which", return_value="/usr/local/bin/jesse")
@patch("subprocess.run")
def test_run_backtest_syntax_error(mock_run, mock_which):
    mock_response = MagicMock()
    mock_response.returncode = 1
    mock_response.stdout = ""
    mock_response.stderr = "File \"strategy.py\", line 10\n    def go_long(self)\n                    ^\nSyntaxError: invalid syntax"
    mock_run.return_value = mock_response

    runner = MCPJesseRunner("./jesse_workspace")
    result = runner.run_backtest("2021-01-01", "2021-02-01")
    assert result["status"] == "COMPILATION_ERROR"
    assert "SyntaxError" in result["stderr"]

@patch("shutil.which", return_value="/usr/local/bin/jesse")
@patch("subprocess.run")
def test_run_backtest_general_error(mock_run, mock_which):
    mock_response = MagicMock()
    mock_response.returncode = 1
    mock_response.stdout = ""
    mock_response.stderr = "Error: Database connection lost."
    mock_run.return_value = mock_response

    runner = MCPJesseRunner("./jesse_workspace")
    result = runner.run_backtest("2021-01-01", "2021-02-01")
    assert result["status"] == "ERROR"
    assert "Database connection lost" in result["stderr"]
