import os
import json
from datetime import datetime, timezone
import jsonschema
from jsonschema import validate, ValidationError
from core_engine.state_io import atomic_write_json, read_json_fresh, StaleStateError

class RuinBiasViolationError(ValueError):
    """Exception raised when the max drawdown limit exceeds 2.0%."""
    pass

class Supervisor:
    def __init__(self, schemas_dir: str = None, payload_drop_dir: str = None,
                 max_spec_age_seconds: float = None):
        """
        Initialize the Supervisor with schemas directory and payload drop directory.

        Args:
            max_spec_age_seconds: when set, ``alpha_spec.json`` must be fresher
                than this many seconds or a StaleStateError is raised. Guards
                against acting on a silently-failed upstream agent (Vuln 1).
                Default None disables the check (suitable for demos/tests that
                read committed fixtures).
        """
        # Resolve paths relative to project root if not specified
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.schemas_dir = schemas_dir or os.path.join(base_dir, "schemas")
        self.payload_drop_dir = payload_drop_dir or os.path.join(base_dir, "payload_drop")
        self.max_spec_age_seconds = max_spec_age_seconds
        
        # Load schemas
        self.alpha_schema = self._load_schema("alpha_spec.json")
        self.risk_schema = self._load_schema("risk_constraints.json")
        self.context_schema = self._load_schema("context_regime.json")
        self.blueprint_schema = self._load_schema("strategy_blueprint.json")

    def _load_schema(self, filename: str) -> dict:
        path = os.path.join(self.schemas_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_and_generate(self) -> dict:
        """
        Validates the input specification files, applies the Ruin Bias check,
        and generates the strategy blueprint if approved.
        
        Raises:
            FileNotFoundError: If any of the spec files are missing.
            ValidationError: If JSON Schema validation fails.
            RuinBiasViolationError: If the drawdown limit exceeds 2.0%.
        """
        alpha_path = os.path.join(self.payload_drop_dir, "alpha_spec.json")
        risk_path = os.path.join(self.payload_drop_dir, "risk_constraints.json")
        context_path = os.path.join(self.payload_drop_dir, "context_regime.json")
        blueprint_path = os.path.join(self.payload_drop_dir, "strategy_blueprint.json")

        # Verify file existence
        for path, name in [(alpha_path, "alpha_spec.json"), 
                           (risk_path, "risk_constraints.json"), 
                           (context_path, "context_regime.json")]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required specification file '{name}' not found at {path}")

        # Load files. alpha_spec is the upstream agent's signal handoff, so it
        # gets a freshness guard against silent-failure stale signals (Vuln 1).
        try:
            alpha_data = read_json_fresh(alpha_path, max_age_seconds=self.max_spec_age_seconds)
        except StaleStateError:
            raise
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format in alpha_spec.json: {e}") from e

        with open(risk_path, "r", encoding="utf-8") as f:
            try:
                risk_data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON format in risk_constraints.json: {e}") from e

        with open(context_path, "r", encoding="utf-8") as f:
            try:
                context_data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON format in context_regime.json: {e}") from e

        # Validate against JSON schemas
        try:
            validate(instance=alpha_data, schema=self.alpha_schema)
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.absolute_path)
            prefix = f" at {path_str}" if path_str else ""
            raise ValidationError(f"Alpha spec validation error{prefix}: {e.message}") from e

        try:
            validate(instance=risk_data, schema=self.risk_schema)
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.absolute_path)
            prefix = f" at {path_str}" if path_str else ""
            raise ValidationError(f"Risk constraints validation error{prefix}: {e.message}") from e

        try:
            validate(instance=context_data, schema=self.context_schema)
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.absolute_path)
            prefix = f" at {path_str}" if path_str else ""
            raise ValidationError(f"Context regime validation error{prefix}: {e.message}") from e

        # Explicit Ruin Bias check (Invariant 2): limit <= 2.0%
        # (Though schemas/risk_constraints.json also specifies a maximum of 2.0,
        # we explicitly check and raise our custom RuinBiasViolationError)
        max_dd = risk_data.get("max_drawdown_limit_pct")
        if max_dd is None or max_dd > 2.0:
            raise RuinBiasViolationError(
                f"Ruin Bias Violation: max_drawdown_limit_pct ({max_dd}) exceeds maximum allowed 2.0%"
            )

        # Cross-validation: check that take_profit_value / stop_loss_value >= risk_to_reward_minimum
        tp = risk_data.get("take_profit_value")
        sl = risk_data.get("stop_loss_value")
        min_rr = risk_data.get("risk_to_reward_minimum")
        
        if tp is not None and sl is not None and min_rr is not None:
            if sl == 0:
                raise ValidationError("Risk constraints validation error: stop_loss_value cannot be zero")
            actual_rr = tp / sl
            if actual_rr < min_rr:
                raise ValidationError(
                    f"Risk constraints validation error: Actual Risk-to-Reward ratio ({actual_rr:.2f}) "
                    f"is less than the required minimum ({min_rr:.2f}). "
                    f"Take Profit ({tp}) / Stop Loss ({sl}) = {actual_rr:.2f}"
                )

        # Build approved blueprint
        blueprint = {
            "alpha": alpha_data,
            "risk": risk_data,
            "context": context_data,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "supervisor_verdict": "APPROVED"
        }

        # Validate the generated blueprint schema to ensure correctness
        try:
            validate(instance=blueprint, schema=self.blueprint_schema)
        except ValidationError as e:
            path_str = ".".join(str(p) for p in e.absolute_path)
            prefix = f" at {path_str}" if path_str else ""
            raise ValidationError(f"Generated strategy blueprint validation error{prefix}: {e.message}") from e


        # Write output blueprint atomically so a concurrent reader (the
        # Developer Bridge) never observes a partial blueprint (Vuln 1/3).
        atomic_write_json(blueprint_path, blueprint, indent=2)

        return blueprint
