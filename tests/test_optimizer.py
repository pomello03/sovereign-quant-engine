import os
import json
import pytest
from unittest.mock import patch, MagicMock
from core_engine.optimizer import RiskOptimizer
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import QuantValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary payload_drop and workspace directories."""
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    workspace_dir = tmp_path / "jesse_workspace"
    workspace_dir.mkdir()
    return payload_dir, workspace_dir


@pytest.fixture
def sample_blueprint():
    """A valid strategy blueprint with risk sub-dict."""
    return {
        "alpha": {
            "strategy_name": "TestStrategy",
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
            "max_position_sizing_pct": 2.0
        },
        "context": {
            "market_regime": "trending_bullish",
            "timeframe": "1h",
            "trend_strength": "strong",
            "volatility_state": "normal"
        },
        "generated_at": "2026-01-01T00:00:00Z",
        "supervisor_verdict": "APPROVED"
    }


@pytest.fixture
def sample_constraints():
    """Risk constraints that match the blueprint."""
    return {
        "max_drawdown_limit_pct": 1.5,
        "stop_loss_type": "fixed",
        "stop_loss_value": 0.02,
        "max_position_sizing_pct": 2.0
    }


@pytest.fixture
def setup_optimizer(temp_dirs, sample_blueprint, sample_constraints):
    """Write blueprint & constraints files and return a configured RiskOptimizer."""
    payload_dir, workspace_dir = temp_dirs

    with open(payload_dir / "strategy_blueprint.json", "w", encoding="utf-8") as f:
        json.dump(sample_blueprint, f)

    with open(payload_dir / "risk_constraints.json", "w", encoding="utf-8") as f:
        json.dump(sample_constraints, f)

    optimizer = RiskOptimizer(
        payload_drop_dir=str(payload_dir),
        workspace_path=str(workspace_dir),
    )
    return optimizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_metrics():
    return {
        "sharpe_ratio": 2.5,
        "max_drawdown": -0.8,
        "profit_factor": 2.0,
        "total_trades": 50,
        "win_rate": 0.65
    }


def _passing_report():
    return {
        "validation_passed": True,
        "metrics": _good_metrics(),
        "constraints": {},
        "monte_carlo_results": {
            "risk_of_ruin": 0.01,
            "average_max_drawdown": 0.5,
            "peak_simulated_drawdown": 1.0,
            "num_simulations": 1000,
            "drawdown_limit_used": 1.5,
            "win_rate_used": 0.65,
            "simulation_mode": "parametric_lognormal"
        },
        "validated_at": "2026-01-01T00:00:00Z"
    }


def _failing_report():
    report = _passing_report()
    report["validation_passed"] = False
    return report


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRiskOptimizer:
    """Tests for the closed-loop RiskOptimizer."""

    def test_optimize_finds_compliant_params(self, setup_optimizer):
        """When validation passes on the first iteration the optimizer returns immediately."""
        optimizer = setup_optimizer

        with patch.object(
            optimizer.bridge, "generate_strategy_code"
        ) as mock_gen, patch.object(
            optimizer.bridge, "execute_closed_loop",
            return_value={"status": "SUCCESS", "metrics": _good_metrics()}
        ) as mock_exec, patch.object(
            optimizer.validator, "generate_report",
            return_value=_passing_report()
        ) as mock_report:

            result = optimizer.optimize_risk_parameters(max_iterations=5)

            assert result is not None
            assert result["validation_passed"] is True
            # Should only have run one iteration
            mock_exec.assert_called_once()
            mock_report.assert_called_once()

    def test_optimize_converges_after_adjustments(self, setup_optimizer):
        """Validation fails twice then passes; position size should be reduced."""
        optimizer = setup_optimizer

        reports = [_failing_report(), _failing_report(), _passing_report()]

        with patch.object(
            optimizer.bridge, "generate_strategy_code"
        ), patch.object(
            optimizer.bridge, "execute_closed_loop",
            return_value={"status": "SUCCESS", "metrics": _good_metrics()}
        ), patch.object(
            optimizer.validator, "generate_report",
            side_effect=reports
        ) as mock_report:

            result = optimizer.optimize_risk_parameters(max_iterations=10)

            assert result is not None
            assert result["validation_passed"] is True
            # Three iterations means generate_report was called 3 times
            assert mock_report.call_count == 3

            # After two failures the pos_size (initially 2.0) should have been
            # halved twice: 2.0 -> 1.0 -> 0.5.  Verify the blueprint on disk
            # was updated accordingly.
            bp_path = os.path.join(optimizer.payload_drop_dir, "strategy_blueprint.json")
            with open(bp_path, "r", encoding="utf-8") as f:
                final_bp = json.load(f)
            assert final_bp["risk"]["max_position_sizing_pct"] < 2.0

    def test_optimize_max_iterations_exceeded(self, setup_optimizer):
        """When validation never passes the optimizer returns after max_iterations."""
        optimizer = setup_optimizer

        with patch.object(
            optimizer.bridge, "generate_strategy_code"
        ), patch.object(
            optimizer.bridge, "execute_closed_loop",
            return_value={"status": "SUCCESS", "metrics": _good_metrics()}
        ), patch.object(
            optimizer.validator, "generate_report",
            return_value=_failing_report()
        ) as mock_report:

            result = optimizer.optimize_risk_parameters(max_iterations=3)

            # Should return the best (last) report even though it failed
            assert result is not None
            assert result["validation_passed"] is False
            assert mock_report.call_count == 3

    def test_optimize_missing_files(self, temp_dirs):
        """FileNotFoundError is raised when blueprint or constraints files are absent."""
        payload_dir, workspace_dir = temp_dirs

        optimizer = RiskOptimizer(
            payload_drop_dir=str(payload_dir),
            workspace_path=str(workspace_dir),
        )

        with pytest.raises(FileNotFoundError, match="Blueprint or risk constraints"):
            optimizer.optimize_risk_parameters()

    def test_optimize_backtest_failure_continues(self, setup_optimizer):
        """When execute_closed_loop returns ERROR the loop skips and continues."""
        optimizer = setup_optimizer

        exec_returns = [
            {"status": "ERROR", "metrics": None},
            {"status": "ERROR", "metrics": None},
            {"status": "SUCCESS", "metrics": _good_metrics()},
        ]

        with patch.object(
            optimizer.bridge, "generate_strategy_code"
        ), patch.object(
            optimizer.bridge, "execute_closed_loop",
            side_effect=exec_returns
        ) as mock_exec, patch.object(
            optimizer.validator, "generate_report",
            return_value=_passing_report()
        ) as mock_report:

            result = optimizer.optimize_risk_parameters(max_iterations=5)

            # The first two ERROR iterations are skipped; third iteration passes.
            assert result is not None
            assert result["validation_passed"] is True
            assert mock_exec.call_count == 3
            # generate_report should only be called on the SUCCESS iteration
            mock_report.assert_called_once()

    def test_optimize_records_history(self, setup_optimizer):
        """Each attempt is recorded in optimization_history and passed to generate_report."""
        optimizer = setup_optimizer

        with patch.object(
            optimizer.bridge, "generate_strategy_code"
        ), patch.object(
            optimizer.bridge, "execute_closed_loop",
            return_value={"status": "SUCCESS", "metrics": _good_metrics()}
        ), patch.object(
            optimizer.validator, "generate_report",
            return_value=_passing_report()
        ) as mock_report:

            optimizer.optimize_risk_parameters(max_iterations=5)

            assert len(optimizer.optimization_history) == 1
            entry = optimizer.optimization_history[0]
            assert entry["iteration"] == 1
            assert entry["params"]["max_position_sizing_pct"] == 2.0
            assert entry["params"]["stop_loss_value"] == 0.02
            assert entry["metrics"]["sharpe_ratio"] == 2.5
            assert "risk_of_ruin" in entry
            assert "validation_passed" in entry
            # The history list is forwarded to generate_report for the dashboard stepper
            kwargs = mock_report.call_args.kwargs
            assert kwargs["optimization_history"] is optimizer.optimization_history
            assert kwargs["blueprint"] is not None
            assert kwargs["mc_results"] is not None
