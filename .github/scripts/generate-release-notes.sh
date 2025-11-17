#!/bin/bash
set -euo pipefail

# Script to generate release notes for container-packaging-tools
# Outputs release notes to stdout

VERSION="${1:?Version required}"
CHANNEL="${2:-unstable}"

cat <<EOF
# Version $VERSION

## Release Notes

This release includes updates to container-packaging-tools for generating Debian packages from container application definitions.

For more information, visit:
- GitHub: https://github.com/hatlabs/container-packaging-tools
- Documentation: https://github.com/hatlabs/container-packaging-tools/blob/main/README.md

## Installation

### Via APT Repository

\`\`\`bash
# Add the Hat Labs APT repository (if not already added)
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys YOUR_KEY_ID
echo "deb https://apt.hatlabs.fi/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hatlabs.list

# Install the package
sudo apt-get update
sudo apt-get install container-packaging-tools
\`\`\`

### Manual Installation

\`\`\`bash
# Download and install the .deb file
wget https://github.com/hatlabs/container-packaging-tools/releases/download/$VERSION/container-packaging-tools_${VERSION}_all+any+main.deb
sudo dpkg -i container-packaging-tools_${VERSION}_all+any+main.deb
\`\`\`

---

Generated at $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
