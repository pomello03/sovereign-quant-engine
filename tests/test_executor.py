"""The executor's job is to measure, or to say it could not.

These tests exist because the previous version returned SUCCESS with invented
metrics from four different branches, and two tests asserted that it should.
The assertions below are the inverse of those two.
"""

import ast
import inspect
import os

import pytest

from core_engine import mcp_executor
from core_engine.mcp_executor import MCPJesseRunner

VALID_STRATEGY = "class SovereignStrategy:\n    pass\n"
BROKEN_STRATEGY = "class SovereignStrategy\n    pass\n"  # missing colon


def _workspace(tmp_path, strategy_source=VALID_STRATEGY):
    ws = tmp_path / "jesse_workspace"
    pkg = ws / "strategies" / "SovereignStrategy"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(strategy_source, encoding="utf-8")
    return str(ws)


def _runner(tmp_path, strategy_source=VALID_STRATEGY, candles="missing.npy"):
    return MCPJesseRunner(
        _workspace(tmp_path, strategy_source),
        candles_path=str(tmp_path / candles),
    )


# --------------------------------------------------------------- the core rule

def test_missing_candles_is_not_success(tmp_path):
    """No candles means no measurement, and no measurement is not a pass."""
    result = _runner(tmp_path).run_backtest("2024-01-01", "2024-06-01")
    assert result["status"] == mcp_executor.STATUS_NO_DATA
    assert result["metrics"] is None


def test_no_data_metrics_is_none_not_empty_dict(tmp_path):
    """None, so that `metrics['sharpe_ratio']` raises instead of reading as absent.

    An empty dict would let `metrics.get('sharpe_ratio')` return None and flow
    into a gate that skips whatever it cannot see.
    """
    result = _runner(tmp_path).run_backtest("2024-01-01", "2024-06-01")
    assert result["metrics"] is None
    with pytest.raises(TypeError):
        result["metrics"]["sharpe_ratio"]


def test_reason_explains_why_there_is_no_measurement(tmp_path):
    result = _runner(tmp_path).run_backtest("2024-01-01", "2024-06-01")
    assert result["reason"]
    assert "jesse" in result["reason"].lower() or "candle" in result["reason"].lower()


def test_success_is_only_reachable_from_the_real_backtest_path():
    """Structural guard: SUCCESS must not be returnable from a fallback branch.

    The regression this prevents is the original design, where four separate
    early returns produced SUCCESS without ever touching market data.
    """
    source = inspect.getsource(mcp_executor)
    run_backtest = inspect.getsource(MCPJesseRunner.run_backtest)
    assert "STATUS_SUCCESS" not in run_backtest
    assert source.count("STATUS_SUCCESS") == 2  # the constant, and _run_jesse


def test_no_mock_metrics_anywhere_in_the_module():
    source = inspect.getsource(mcp_executor).lower()
    for forbidden in ("mock_metrics", "_mock_trade_returns", "simulated_drawdown"):
        assert forbidden not in source


# ------------------------------------------------------------------ provenance

def test_provenance_present_even_when_there_is_no_data(tmp_path):
    """A caller must always be able to ask where a number came from."""
    result = _runner(tmp_path).run_backtest("2024-01-01", "2024-06-01")
    prov = result["provenance"]
    assert prov["data_source"] is None
    assert prov["exchange"] == "Bybit Spot"
    assert prov["fee_per_side"] == 0.001
    assert prov["strategy_sha256"]


def test_provenance_records_the_strategy_hash(tmp_path):
    a = _runner(tmp_path / "a").run_backtest("2024-01-01", "2024-06-01")
    b = _runner(tmp_path / "b", strategy_source=VALID_STRATEGY + "# changed\n").run_backtest(
        "2024-01-01", "2024-06-01"
    )
    assert a["provenance"]["strategy_sha256"] != b["provenance"]["strategy_sha256"]


# ------------------------------------------------------------- compilation gate

def test_broken_strategy_is_a_compilation_error(tmp_path):
    result = _runner(tmp_path, strategy_source=BROKEN_STRATEGY).run_backtest(
        "2024-01-01", "2024-06-01"
    )
    assert result["status"] == mcp_executor.STATUS_COMPILATION_ERROR
    assert "SyntaxError" in result["stderr"]
    assert result["metrics"] is None


def test_missing_strategy_file_is_a_compilation_error(tmp_path):
    ws = tmp_path / "jesse_workspace"
    ws.mkdir()
    result = MCPJesseRunner(str(ws)).run_backtest("2024-01-01", "2024-06-01")
    assert result["status"] == mcp_executor.STATUS_COMPILATION_ERROR


def test_compilation_gate_does_not_depend_on_external_linters(tmp_path):
    """A missing dev tool must never look like broken strategy code.

    The old gate shelled out to ruff/vulture/xenon and mapped any non-zero exit
    to COMPILATION_ERROR, so an uninstalled linter sent the bridge into three
    rounds of regenerating code that was already correct.
    """
    tree = ast.parse(inspect.getsource(mcp_executor))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "subprocess" not in imported
    assert "shutil" not in imported

    result = _runner(tmp_path).run_backtest("2024-01-01", "2024-06-01")
    assert result["status"] != mcp_executor.STATUS_COMPILATION_ERROR


# ------------------------------------------------------------------ time window

def test_window_outside_the_candle_file_is_no_data(tmp_path):
    np = pytest.importorskip("numpy")
    path = tmp_path / "candles.npy"
    # One day of 1m candles in 2024, then ask for 2019.
    start = MCPJesseRunner._to_ms("2024-01-01")
    rows = [[start + i * 60_000, 100.0, 100.0, 100.0, 100.0, 1.0] for i in range(1440)]
    np.save(path, np.array(rows, dtype=float))

    runner = MCPJesseRunner(_workspace(tmp_path), candles_path=str(path))
    result = runner.run_backtest("2019-01-01", "2019-06-01")
    assert result["status"] == mcp_executor.STATUS_NO_DATA
    assert result["metrics"] is None


def test_insufficient_warmup_is_no_data(tmp_path):
    """Indicators must not warm up on the window being evaluated."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("jesse")
    path = tmp_path / "candles.npy"
    start = MCPJesseRunner._to_ms("2024-01-01")
    rows = [[start + i * 60_000, 100.0, 100.0, 100.0, 100.0, 1.0] for i in range(4320)]
    np.save(path, np.array(rows, dtype=float))

    runner = MCPJesseRunner(_workspace(tmp_path), candles_path=str(path))
    result = runner.run_backtest("2024-01-02", "2024-01-04")
    assert result["status"] == mcp_executor.STATUS_NO_DATA
    assert "warm-up" in result["reason"]


def test_workspace_path_is_absolute(tmp_path):
    runner = MCPJesseRunner(_workspace(tmp_path))
    assert os.path.isabs(runner.workspace_path)
