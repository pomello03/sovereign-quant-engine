import os
import time
import json
import pytest
from jsonschema import ValidationError
from core_engine.supervisor import Supervisor, RuinBiasViolationError
from core_engine.developer_bridge import DeveloperBridge
from core_engine.quant_validator import MissingMetricError, QuantValidator
from core_engine.state_io import StaleStateError


# ---------------------------------------------------------------------------
# Shared constants / paths
# ---------------------------------------------------------------------------

REAL_SCHEMAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "schemas"
)


# ---------------------------------------------------------------------------
# Fixtures – Supervisor
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_payload_dir(tmp_path):
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    return payload_dir


@pytest.fixture
def valid_payloads():
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
    with open(payload_dir / "alpha_spec.json", "w", encoding="utf-8") as f:
        json.dump(alpha, f)
    with open(payload_dir / "risk_constraints.json", "w", encoding="utf-8") as f:
        json.dump(risk, f)
    with open(payload_dir / "context_regime.json", "w", encoding="utf-8") as f:
        json.dump(context, f)


# ---------------------------------------------------------------------------
# Fixtures – DeveloperBridge (for AST tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def bridge(tmp_path):
    payload_dir = tmp_path / "payload_drop"
    payload_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    return DeveloperBridge(
        payload_drop_dir=str(payload_dir),
        workspace_path=str(workspace_dir)
    )


# ===========================================================================
# SECTION 1 – Supervisor Edge Cases
# ===========================================================================

class TestSupervisorEdgeCases:

    def test_supervisor_zero_stop_loss(self, temp_payload_dir, valid_payloads):
        """stop_loss_value=0 must be rejected.

        The schema now rejects it via exclusiveMinimum before the code-level
        division-by-zero guard is reached, so the message differs; both refuse.
        """
        alpha, risk, context = valid_payloads
        risk["stop_loss_value"] = 0
        write_payload_files(temp_payload_dir, alpha, risk, context)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        with pytest.raises(ValidationError):
            supervisor.validate_and_generate()

    def test_supervisor_rejects_negative_stop_and_target(self, temp_payload_dir, valid_payloads):
        """Two negatives cancel in the ratio: (-0.04)/(-0.02) = 2.0 used to pass."""
        alpha, risk, context = valid_payloads
        risk["stop_loss_value"] = -0.02
        risk["take_profit_value"] = -0.04
        write_payload_files(temp_payload_dir, alpha, risk, context)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        with pytest.raises(ValidationError):
            supervisor.validate_and_generate()

    def test_supervisor_rejects_stale_alpha_spec(self, temp_payload_dir, valid_payloads):
        """Vuln 1: a stale alpha_spec.json (silent upstream failure) is rejected
        when freshness enforcement is enabled."""
        alpha, risk, context = valid_payloads
        write_payload_files(temp_payload_dir, alpha, risk, context)
        # Backdate alpha_spec.json past the freshness window.
        alpha_path = temp_payload_dir / "alpha_spec.json"
        old = time.time() - 120
        os.utime(alpha_path, (old, old))

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR,
                                payload_drop_dir=str(temp_payload_dir),
                                max_spec_age_seconds=60)
        with pytest.raises(StaleStateError):
            supervisor.validate_and_generate()

    def test_supervisor_fresh_alpha_spec_passes(self, temp_payload_dir, valid_payloads):
        """Freshness enabled + freshly written spec -> approved."""
        alpha, risk, context = valid_payloads
        write_payload_files(temp_payload_dir, alpha, risk, context)
        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR,
                                payload_drop_dir=str(temp_payload_dir),
                                max_spec_age_seconds=60)
        assert supervisor.validate_and_generate()["supervisor_verdict"] == "APPROVED"

    def test_supervisor_boundary_drawdown_exactly_2(self, temp_payload_dir, valid_payloads):
        """max_drawdown_limit_pct=2.0 is exactly on the boundary and should pass."""
        alpha, risk, context = valid_payloads
        risk["max_drawdown_limit_pct"] = 2.0
        write_payload_files(temp_payload_dir, alpha, risk, context)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        blueprint = supervisor.validate_and_generate()
        assert blueprint["supervisor_verdict"] == "APPROVED"

    def test_supervisor_none_drawdown(self, temp_payload_dir, valid_payloads):
        """max_drawdown_limit_pct=None should be caught by the Ruin Bias check
        (if max_dd is None -> violation)."""
        alpha, risk, context = valid_payloads
        risk["max_drawdown_limit_pct"] = None
        write_payload_files(temp_payload_dir, alpha, risk, context)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        # Schema validation may reject None (not a number), or the explicit
        # Ruin Bias check raises RuinBiasViolationError for None.
        with pytest.raises((ValidationError, RuinBiasViolationError)):
            supervisor.validate_and_generate()

    def test_supervisor_missing_risk_file(self, temp_payload_dir, valid_payloads):
        """Only risk_constraints.json is missing -> FileNotFoundError."""
        alpha, _, context = valid_payloads
        # Write alpha and context, skip risk
        with open(temp_payload_dir / "alpha_spec.json", "w", encoding="utf-8") as f:
            json.dump(alpha, f)
        with open(temp_payload_dir / "context_regime.json", "w", encoding="utf-8") as f:
            json.dump(context, f)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        with pytest.raises(FileNotFoundError, match="risk_constraints.json"):
            supervisor.validate_and_generate()

    def test_supervisor_missing_context_file(self, temp_payload_dir, valid_payloads):
        """Only context_regime.json is missing -> FileNotFoundError."""
        alpha, risk, _ = valid_payloads
        # Write alpha and risk, skip context
        with open(temp_payload_dir / "alpha_spec.json", "w", encoding="utf-8") as f:
            json.dump(alpha, f)
        with open(temp_payload_dir / "risk_constraints.json", "w", encoding="utf-8") as f:
            json.dump(risk, f)

        supervisor = Supervisor(schemas_dir=REAL_SCHEMAS_DIR, payload_drop_dir=str(temp_payload_dir))
        with pytest.raises(FileNotFoundError, match="context_regime.json"):
            supervisor.validate_and_generate()


# ===========================================================================
# SECTION 2 – AST Transformer Edge Cases
# ===========================================================================

class TestASTTransformerEdgeCases:

    def test_translate_condition_unknown_variable(self, bridge):
        """'volume > 1000' – volume is a Jesse price field and should map to self.volume."""
        indicators = [{"name": "RSI", "params": {"period": 14}}]
        result = bridge._translate_condition("volume > 1000", indicators)
        assert result == "self.volume > 1000"

    def test_translate_condition_high_low(self, bridge):
        """'high > low' should map both to self.high and self.low."""
        indicators = []
        result = bridge._translate_condition("high > low", indicators)
        assert result == "self.high > self.low"

    def test_translate_condition_empty_returns_error(self, bridge):
        """An empty string condition is invalid Python and should raise ValueError."""
        indicators = [{"name": "RSI", "params": {"period": 14}}]
        with pytest.raises(ValueError, match="Invalid condition syntax"):
            bridge._translate_condition("", indicators)

    def test_translate_condition_arithmetic(self, bridge):
        """'rsi + 10 > 50' should correctly translate the indicator name."""
        indicators = [{"name": "RSI", "params": {"period": 14}}]
        result = bridge._translate_condition("rsi + 10 > 50", indicators)
        assert result == "self.rsi + 10 > 50"


# ===========================================================================
# SECTION 3 – QuantValidator Edge Cases
# ===========================================================================

class TestValidatorEdgeCases:

    # --- validate_with_monte_carlo ---

    def test_validate_with_monte_carlo_rejects_high_ruin(self):
        """risk_of_ruin > 0.05 should cause validate_with_monte_carlo to fail."""
        validator = QuantValidator()
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": -1.0, "profit_factor": 2.0}
        constraints = {"max_drawdown_limit_pct": 2.0}
        mc_results = {
            "risk_of_ruin": 0.10,           # Too high
            "average_max_drawdown": 1.0,
        }
        assert validator.validate_with_monte_carlo(metrics, constraints, mc_results) is False

    def test_validate_with_monte_carlo_rejects_high_avg_dd(self):
        """average_max_drawdown exceeding the limit should fail."""
        validator = QuantValidator()
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": -1.0, "profit_factor": 2.0}
        constraints = {"max_drawdown_limit_pct": 1.5}
        mc_results = {
            "risk_of_ruin": 0.01,
            "average_max_drawdown": 2.0,    # Exceeds 1.5 limit
        }
        assert validator.validate_with_monte_carlo(metrics, constraints, mc_results) is False

    def test_validate_with_monte_carlo_passes_good_mc(self):
        """When both base metrics and MC results are good, should pass."""
        validator = QuantValidator()
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": -1.0, "profit_factor": 2.0,
                   "total_trades": 40}
        constraints = {
            "max_drawdown_limit_pct": 2.0,
            "sharpe_ratio_minimum": 1.5,
            "profit_factor_minimum": 1.5
        }
        # Unbiased stress test: bootstrap mode with a sufficient real-trade sample (Vuln 5).
        mc_results = {
            "risk_of_ruin": 0.02,
            "average_max_drawdown": 1.0,
            "simulation_mode": "bootstrap",
            "real_trades_used": 40,
        }
        assert validator.validate_with_monte_carlo(metrics, constraints, mc_results) is True

    def test_validate_with_monte_carlo_rejects_inactive_strategy(self):
        """Empty-trades bypass guard (Vuln 5): no real trades -> reject even with 0% ruin."""
        validator = QuantValidator()
        metrics = {"sharpe_ratio": 2.0, "max_drawdown": 0.0, "profit_factor": 2.0,
                   "total_trades": 0}
        constraints = {"max_drawdown_limit_pct": 2.0, "sharpe_ratio_minimum": 1.5,
                       "profit_factor_minimum": 1.5}
        # Inactive strategy: parametric fallback, zero real trades -> false positive otherwise.
        mc_results = {
            "risk_of_ruin": 0.0,
            "average_max_drawdown": 0.0,
            "simulation_mode": "parametric_lognormal",
            "real_trades_used": 0,
        }
        assert validator.validate_with_monte_carlo(metrics, constraints, mc_results) is False

    def test_validate_with_monte_carlo_fails_if_base_fails(self):
        """Even if MC results are stellar, bad base metrics should fail."""
        validator = QuantValidator()
        metrics = {
            "sharpe_ratio": 0.5,       # Below typical minimum
            "max_drawdown": -3.0,      # Exceeds limit
            "profit_factor": 0.8
        }
        constraints = {
            "max_drawdown_limit_pct": 2.0,
            "sharpe_ratio_minimum": 1.5,
            "profit_factor_minimum": 1.0
        }
        mc_results = {
            "risk_of_ruin": 0.00,
            "average_max_drawdown": 0.5,
        }
        assert validator.validate_with_monte_carlo(metrics, constraints, mc_results) is False

    # --- validate_metrics with None values ---

    def test_validate_metrics_none_values_raise(self):
        """Unmeasured metrics must raise, not sail through every gate.

        This test used to assert the opposite, and it was right about the code:
        each check was wrapped in `if x is not None`, so a metrics dict of all
        None satisfied even deliberately severe constraints. That is the
        behaviour being removed, so the assertion is inverted rather than the
        test deleted — the record of what was once considered correct is worth
        keeping.
        """
        validator = QuantValidator()
        metrics = {
            "sharpe_ratio": None,
            "max_drawdown": None,
            "profit_factor": None
        }
        constraints = {
            "max_drawdown_limit_pct": 2.0,
            "sharpe_ratio_minimum": 1.5,
            "profit_factor_minimum": 1.2
        }
        with pytest.raises(MissingMetricError):
            validator.validate_metrics(metrics, constraints)

    def test_validate_metrics_rejects_none_metrics_object(self):
        validator = QuantValidator()
        with pytest.raises(MissingMetricError):
            validator.validate_metrics(None, {"max_drawdown_limit_pct": 2.0})

    def test_zero_trade_strategy_is_rejected_not_errored(self):
        """A strategy that never traded is a measured fact, and it is not a pass.

        The alpha_spec shipped in this repo produces exactly zero entries on
        five years of real Bybit spot candles (see research/RESULT_P0-1.md),
        and the pipeline certified it PASSED with risk_of_ruin 0.0.
        """
        validator = QuantValidator()
        metrics = {"total_trades": 0, "sharpe_ratio": None,
                   "max_drawdown": None, "profit_factor": None}
        assert validator.validate_metrics(metrics, {"max_drawdown_limit_pct": 2.0}) is False

    # --- run_monte_carlo determinism / seed ---

    def test_run_monte_carlo_with_seed(self):
        """run_monte_carlo(seed=42) should produce deterministic results."""
        validator = QuantValidator()
        metrics = {
            "profit_factor": 1.5,
            "total_trades": 50,
            "win_rate": 0.55
        }
        r1 = validator.run_monte_carlo(metrics, num_simulations=200, drawdown_limit=2.0, seed=42)
        r2 = validator.run_monte_carlo(metrics, num_simulations=200, drawdown_limit=2.0, seed=42)

        assert r1["risk_of_ruin"] == r2["risk_of_ruin"]
        assert r1["average_max_drawdown"] == r2["average_max_drawdown"]
        assert r1["peak_simulated_drawdown"] == r2["peak_simulated_drawdown"]

    def test_run_monte_carlo_without_seed(self):
        """run_monte_carlo() without a seed should still return valid results."""
        validator = QuantValidator()
        metrics = {
            "profit_factor": 1.5,
            "total_trades": 50,
            "win_rate": 0.55
        }
        result = validator.run_monte_carlo(metrics, num_simulations=100, drawdown_limit=2.0)

        assert "risk_of_ruin" in result
        assert "average_max_drawdown" in result
        assert 0.0 <= result["risk_of_ruin"] <= 1.0
        assert result["average_max_drawdown"] >= 0.0

    def test_monte_carlo_equity_floor(self):
        """Extreme negative trade_returns should never produce negative equity
        because the code clamps with max(0.0, ...)."""
        validator = QuantValidator()
        metrics = {
            "profit_factor": 1.5,
            "total_trades": 20,
            "win_rate": 0.50,
            "trade_returns": [-0.99, -0.95, -0.90, -0.80, 0.01, 0.02]
        }
        result = validator.run_monte_carlo(metrics, num_simulations=500, drawdown_limit=2.0, seed=42)

        # Equity can't go negative -> drawdown caps at 100%
        assert result["peak_simulated_drawdown"] <= 100.0
        assert result["average_max_drawdown"] >= 0.0
        # With such extreme losses, nearly every simulation should breach the limit
        assert result["risk_of_ruin"] > 0.0
