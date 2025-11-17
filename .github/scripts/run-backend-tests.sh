#!/bin/bash
set -euo pipefail

echo "🧪 Running backend tests..."
uv sync --dev
uv run pytest tests/test_*.py -m "not integration and not install"
echo "✅ Backend tests passed"
