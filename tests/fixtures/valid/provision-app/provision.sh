#!/bin/bash
# Provisioning hook for the provision test app.
# Executed (not sourced) by <package>-provision.service before the app starts,
# and re-run on every app start -- hence the sentinel.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENTINEL="${CONTAINER_DATA_ROOT:-/tmp}/.provisioned"

if [ -f "$SENTINEL" ]; then
    exit 0
fi

echo "provisioning from ${SCRIPT_DIR}"
mkdir -p "$(dirname "$SENTINEL")" && touch "$SENTINEL"
