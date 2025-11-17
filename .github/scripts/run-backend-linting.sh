#!/bin/bash
set -euo pipefail

echo "🔍 Running backend linting..."
uv sync --dev
uv run ruff check src/ tests/
echo "✅ Linting passed"
