#!/bin/bash
# Run tests in Docker container (Debian environment)
# This allows testing package installation on macOS/non-Debian systems

set -e

cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

case "${1:-all}" in
    unit)
        echo -e "${BLUE}Running unit tests only (no installation tests)...${NC}"
        docker compose -f docker-compose.test.yml run --rm test
        ;;
    install)
        echo -e "${BLUE}Running installation tests only...${NC}"
        docker compose -f docker-compose.test.yml run --rm test-install
        ;;
    all)
        echo -e "${BLUE}Running all tests (including installation)...${NC}"
        docker compose -f docker-compose.test.yml run --rm test-all
        ;;
    shell)
        echo -e "${BLUE}Opening shell in test container...${NC}"
        docker compose -f docker-compose.test.yml run --rm shell
        ;;
    clean)
        echo -e "${BLUE}Cleaning up Docker containers and images...${NC}"
        docker compose -f docker-compose.test.yml down --rmi local -v
        ;;
    *)
        echo "Usage: $0 {unit|install|all|shell|clean}"
        echo ""
        echo "  unit    - Run unit and integration tests (skip installation)"
        echo "  install - Run installation tests only"
        echo "  all     - Run all tests including installation (default)"
        echo "  shell   - Open interactive shell in test container"
        echo "  clean   - Remove Docker containers and images"
        exit 1
        ;;
esac

echo -e "${GREEN}Done!${NC}"
