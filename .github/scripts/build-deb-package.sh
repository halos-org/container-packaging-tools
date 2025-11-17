#!/bin/bash
# Build Debian package (.deb)
# Installs build dependencies and builds the package

set -e

echo "Installing build dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  build-essential dpkg-dev debhelper dh-python \
  pybuild-plugin-pyproject \
  python3-all python3-setuptools \
  python3-pydantic python3-jinja2 python3-yaml

echo "Building Debian package..."

# Build the package
dpkg-buildpackage -b -uc -us

# List generated packages
echo "📦 Generated packages:"
ls -lh ../*.deb

echo "✅ Package build complete"
