#!/bin/bash
set -euo pipefail

echo "🔍 Running type checking..."
uv sync --dev
uvx ty check src/
echo "✅ Type checking passed"
