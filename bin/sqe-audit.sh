#!/bin/bash
# Static Audit Pipeline for SQE

# Determine workspace directory relative to this script
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../jesse_workspace" && pwd)"

echo "=== Running Static Audit Pipeline ==="
cd "$WORKSPACE_DIR" || { echo "Error: Could not enter workspace directory: $WORKSPACE_DIR"; exit 1; }

# Determine which python executable to use (passed from Python runner)
PYTHON_CMD="${PYTHON:-python}"

# Helper function to run a tool, preferring direct command, falling back to python -m
run_tool() {
    local tool_name="$1"
    shift
    if command -v "$tool_name" >/dev/null 2>&1; then
        "$tool_name" "$@"
    else
        "$PYTHON_CMD" -m "$tool_name" "$@"
    fi
}

echo "[1/3] Running Ruff Check..."
run_tool ruff check strategies/ --select F,E,W,I,U
RUFF_EXIT=$?

echo "[2/3] Running Vulture Dead Code Analysis..."
run_tool vulture strategies/ --min-confidence 80
VULTURE_EXIT=$?

echo "[3/3] Running Xenon Cyclomatic Complexity Analysis..."
run_tool xenon --max-absolute A --max-modules A --max-average B strategies/
XENON_EXIT=$?

# Summarize results
echo "=== Audit Summary ==="
if [ $RUFF_EXIT -eq 0 ] && [ $VULTURE_EXIT -eq 0 ] && [ $XENON_EXIT -eq 0 ]; then
    echo ">> Static Audit: PASSED!"
    exit 0
else
    echo ">> Static Audit: FAILED!"
    echo "Ruff Exit Code: $RUFF_EXIT"
    echo "Vulture Exit Code: $VULTURE_EXIT"
    echo "Xenon Exit Code: $XENON_EXIT"
    exit 1
fi
