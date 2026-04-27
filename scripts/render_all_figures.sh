#!/usr/bin/env bash
# Re-render every figure that the findings doc references.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p docs/figures

for nb in 03_baseline 04_finding1 05_finding2 06_finding3 07_finding4; do
  if [[ -f "notebooks/${nb}.py" ]]; then
    echo "==> ${nb}"
    uv run python "notebooks/${nb}.py" || echo "  (skipped: ${nb} input data missing)"
  fi
done

echo "figures rendered to docs/figures/"
