#!/bin/bash
set -euo pipefail

# Read version from debian/changelog
VERSION=$(dpkg-parsechangelog -S Version)
TAG_VERSION=$(echo "$VERSION" | sed 's/-[^-]*$//')

echo "version=${VERSION}"
echo "tag_version=${TAG_VERSION}"
