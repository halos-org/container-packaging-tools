#!/bin/bash
set -euo pipefail

echo "🧪 Running backend tests..."
uv sync --dev

# Run top-level unit tests
echo "Running unit tests..."
uv run pytest tests/test_*.py -m "not integration and not install"

# Run converter tests
echo "Running converter tests..."
uv run pytest tests/converters/ -m "not integration and not install"

echo "✅ All backend tests passed"
