#!/bin/bash
# Claude Code Notifier - hook entry point
# Reads JSON from stdin and delegates to notify.py

export HOOK_INPUT=$(cat)

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect Python 3 (prefer 'python' / 'py -3' on Windows to avoid Store stub)
if command -v python &>/dev/null && python --version 2>&1 | grep -q "Python 3"; then
    PYTHON=python
elif command -v py &>/dev/null; then
    PYTHON="py -3"
elif command -v python3 &>/dev/null; then
    PYTHON=python3
else
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/notify.py"
