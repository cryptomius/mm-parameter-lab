#!/usr/bin/env bash
# Run every experiment in the manifest. ~5hr single-thread; ~1hr with workers=8.
set -euo pipefail
cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-1}"

echo "==> baseline + F1 + F2 + F3 (lightweight)"
uv run python -m runner.cli run "baseline_calm" --workers 1
uv run python -m runner.cli run "f1_*" --workers "$WORKERS"
uv run python -m runner.cli run "f2_*" --workers "$WORKERS"
uv run python -m runner.cli run "f3_*" --workers "$WORKERS"

echo "==> F4 (heavy: 5x5x20=500 runs, run overnight)"
uv run python -m runner.cli run "f4_*" --workers "$WORKERS"

echo "all experiments done"
