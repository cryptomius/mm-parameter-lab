#!/usr/bin/env bash
# Build findings.pdf from findings.md via pandoc. Falls back to skipping if pandoc not installed.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v pandoc >/dev/null 2>&1; then
  echo "pandoc not found — skipping PDF build. The markdown source at docs/findings.md is the canonical doc."
  exit 0
fi

pandoc docs/findings.md \
  --pdf-engine=xelatex \
  --toc \
  --toc-depth=2 \
  --metadata title="Market-Making Simulator: Findings Report" \
  --metadata author="$(git config user.name 2>/dev/null || echo 'Anonymous')" \
  --metadata date="$(date +%Y-%m-%d)" \
  -o docs/findings.pdf

echo "wrote docs/findings.pdf"
