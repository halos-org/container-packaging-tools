#!/bin/bash
# One-time provisioning for the provision test app.
# Executed (not sourced) by <package>-provision.service before the app starts.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "provisioning from ${SCRIPT_DIR}"
exit 0
