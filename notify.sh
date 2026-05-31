#!/bin/bash
# Claude Code Notifier - hook entry point
# Reads JSON from stdin and delegates to notify.py

export HOOK_INPUT=$(cat)

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect Python 3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    # Fallback: basic notification without AI summary
    if command -v msg &>/dev/null; then
        msg "*" "Claude Code needs your attention"
    fi
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/notify.py"
