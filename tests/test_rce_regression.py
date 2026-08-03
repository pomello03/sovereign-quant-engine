"""Regression tests for the alpha_spec code-execution vector.

The payload below is the one that was actually executed during the audit
(PROJECT_STATE.md V7). It passed schema validation, produced a syntactically
valid Python file, and ran on the first indicator access — silently, because
`_safe_indicator` wraps the getter in try/except and returns the fallback.

Each layer is tested separately. Any one of them stops the attack; all three
exist so that a future relaxation of one does not quietly re-open it.
"""

import json
import os

import jsonschema
import pytest

from core_engine.developer_bridge import DeveloperBridge

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas", "alpha_spec.json"
)

# The audit payload: a params *value* that closes the call's argument list and
# appends an expression of the attacker's choosing.
RCE_PAYLOAD = "14, __x=open(r'marker.txt','w').write('RCE')"


def _spec(params):
    return {
        "strategy_name": "SovereignStrategy",
        "indicators": [{"name": "rsi", "params": params}],
        "entry_long_conditions": ["rsi < 30"],
        "entry_short_conditions": ["rsi > 70"],
    }


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ layer 1

def test_schema_rejects_string_valued_indicator_params(schema):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_spec({"period": RCE_PAYLOAD}), schema)


def test_schema_still_accepts_the_legitimate_spec(schema):
    jsonschema.validate(_spec({"period": 14}), schema)


def test_schema_rejects_non_identifier_indicator_name(schema):
    spec = _spec({"period": 14})
    spec["indicators"][0]["name"] = "rsi(self.candles) or __import__('os')"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(spec, schema)


def test_schema_rejects_non_identifier_param_key(schema):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_spec({"period=1, x": 14}), schema)


# ------------------------------------------------------------------ layer 2

def test_generator_rejects_string_param_even_if_schema_is_bypassed(tmp_path):
    """The generator does not assume it was called through the schema."""
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    with pytest.raises(ValueError, match="must be a number"):
        bridge._generate_init_content({"alpha": _spec({"period": RCE_PAYLOAD})})


def test_generator_rejects_unsafe_indicator_name(tmp_path):
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    spec = _spec({"period": 14})
    spec["indicators"][0]["name"] = "rsi(self.candles) or x"
    with pytest.raises(ValueError, match="unsafe indicator name"):
        bridge._generate_init_content({"alpha": spec})


def test_generator_emits_a_numeric_literal_not_the_caller_text(tmp_path):
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    source = bridge._generate_init_content({"alpha": _spec({"period": 14})})
    assert "ta.rsi(self.candles, period=14)" in source


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), None, [14], {"a": 1}])
def test_generator_rejects_non_finite_and_non_numeric_params(tmp_path, bad):
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    with pytest.raises(ValueError):
        bridge._generate_init_content({"alpha": _spec({"period": bad})})


# ------------------------------------------------------------------ layer 3

def test_conditions_reject_unknown_bare_names(tmp_path):
    """A whitelist: an unrecognised name is refused, not passed through."""
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    with pytest.raises(ValueError, match="unknown name"):
        bridge._translate_condition("__import__ < 30", [{"name": "rsi"}])


def test_conditions_still_reject_calls_and_attributes(tmp_path):
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(tmp_path))
    for condition in ("open('x','w') < 30", "rsi.__class__ < 30"):
        with pytest.raises(ValueError):
            bridge._translate_condition(condition, [{"name": "rsi"}])


def test_nothing_is_written_to_disk_when_generation_is_refused(tmp_path):
    """The file must never exist, because existing is enough to be imported."""
    workspace = tmp_path / "ws"
    bridge = DeveloperBridge(payload_drop_dir=str(tmp_path), workspace_path=str(workspace))
    blueprint = {"alpha": _spec({"period": RCE_PAYLOAD}), "context": {}, "risk": {}}
    with pytest.raises(ValueError):
        bridge.generate_strategy_code(blueprint)
    written = workspace / "strategies" / "SovereignStrategy" / "__init__.py"
    assert not written.exists()
