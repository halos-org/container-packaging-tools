#!/bin/bash
set -euo pipefail

# Script to check if a release exists for this repository
# Returns 'create' if release should be created, 'skip' if it already exists

REPO="${1:?Repository required (owner/repo)}"
VERSION="${2:?Version required}"

echo "🔍 Checking for existing release: $VERSION"

# Check if release exists
if gh release view "$VERSION" --repo "$REPO" &>/dev/null; then
  echo "Release $VERSION already exists"
  echo "action=skip"
  exit 0
else
  echo "Release $VERSION does not exist"
  echo "action=create"
  exit 0
fi
