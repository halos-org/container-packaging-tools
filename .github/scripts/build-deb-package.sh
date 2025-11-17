#!/bin/bash
set -euo pipefail

echo "🏗️  Building Debian package..."

# Install build dependencies
echo "📦 Installing build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential dpkg-dev debhelper dh-python \
  pybuild-plugin-pyproject python3-all python3-pydantic python3-jinja2 python3-yaml \
  nodejs npm >/dev/null 2>&1

# Build the package
echo "🔨 Building package..."
dpkg-buildpackage -b -uc -us

echo "✅ Package build complete"
