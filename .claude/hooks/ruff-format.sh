#!/usr/bin/env bash
# PostToolUse hook: auto-format the file Claude just edited if it's Python.
# Deterministic formatting so the agent never leaves unformatted code behind.
# Reads the tool-call JSON on stdin; pulls the edited path; formats only .py.
set -euo pipefail

input="$(cat)"
# Extract file_path from the hook payload without requiring jq.
path="$(printf '%s' "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

[[ -z "${path:-}" ]] && exit 0
[[ "$path" == *.py ]] || exit 0
[[ -f "$path" ]] || exit 0

uv run ruff format "$path" >/dev/null 2>&1 || true
uv run ruff check --fix "$path" >/dev/null 2>&1 || true
exit 0
