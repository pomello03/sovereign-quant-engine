import os
import json
from datetime import datetime, timezone
import jsonschema
from jsonschema import validate, ValidationError

class RuinBiasViolationError(ValueError):
    """Exception raised when the max drawdown limit exceeds 2.0%."""
    pass

class Supervisor:
    def __init__(self, schemas_dir: str = None, payload_drop_dir: str = None):
        """
        Initialize the Supervisor with schemas directory and payload drop directory.
        """
        # Resolve paths relative to project root if not specified
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.schemas_dir = schemas_dir or os.path.join(base_dir, "schemas")
        self.payload_drop_dir = payload_drop_dir or os.path.join(base_dir, "payload_drop")
        
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

        # Load files
        with open(alpha_path, "r", encoding="utf-8") as f:
            try:
                alpha_data = json.load(f)
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


        # Write output blueprint file
        os.makedirs(os.path.dirname(blueprint_path), exist_ok=True)
        with open(blueprint_path, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, indent=2)

        return blueprint
