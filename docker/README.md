# Docker Test Environment

This directory contains Docker setup for running the full test suite in a Debian environment.

## Why Docker for Testing?

The package installation tests (`test_package_install.py`) require:
- Debian-based system
- `dpkg` and `dpkg-buildpackage`
- `sudo` access

Running tests in Docker allows you to:
- ✅ Run **the complete test suite** (117 unit/integration + 16 installation tests)
- ✅ Test package generation in a Debian environment from any platform
- ✅ Verify the complete end-to-end workflow
- ✅ Match the CI environment

## Quick Start

```bash
# Run all tests (including installation tests)
./docker/run-tests.sh all

# Run only installation tests
./docker/run-tests.sh install

# Run unit tests only (skip installation)
./docker/run-tests.sh unit

# Open interactive shell in test container
./docker/run-tests.sh shell

# Clean up Docker resources
./docker/run-tests.sh clean
```

## Manual Docker Commands

If you prefer to use Docker commands directly:

```bash
cd docker

# Build the test image
docker compose -f docker-compose.test.yml build

# Run all tests
docker compose -f docker-compose.test.yml run --rm test-all

# Run specific test file
docker compose -f docker-compose.test.yml run --rm test \
  bash -c "uv sync && uv run pytest tests/test_integration.py -v"

# Run with coverage
docker compose -f docker-compose.test.yml run --rm test \
  bash -c "uv sync && uv run pytest --cov=src --cov-report=term-missing"

# Interactive shell
docker compose -f docker-compose.test.yml run --rm shell
```

## Test Environment

- **Base Image**: Debian 12 (bookworm)
- **Python**: System Python 3.11+
- **Package Manager**: uv (for fast dependency installation)
- **User**: `testuser` with passwordless sudo
- **Tools**: dpkg-dev, debhelper, build-essential, lintian

## Files

- `Dockerfile.test` - Test environment image definition
- `docker-compose.test.yml` - Compose file with test services
- `run-tests.sh` - Convenience script for running tests

## Expected Results

### Unit and Integration Tests

Running unit tests (recommended for development):

```bash
./docker/run-tests.sh unit
# Expected: 117 passed, 16 skipped
```

- ✅ 102 unit tests - PASS
- ✅ 15 integration tests - PASS
- ⏭️  16 installation tests - SKIPPED (marked with `@pytest.mark.install`)

### Installation Tests

Installation tests (`test_package_install.py`) verify that generated packages install correctly and place files in proper locations. These tests run on Debian systems with dpkg/sudo but will fail if runtime dependencies (docker-compose) are not installed:

```bash
./docker/run-tests.sh all
# Expected: 117-125 passed, some installation tests may fail due to missing docker-compose
```

**For full installation testing**: Run on a Debian/Ubuntu system with Docker installed, or use CI/CD with proper Debian runners that include the docker-compose package.

## Troubleshooting

**Build fails**: Ensure you have Docker and Docker Compose installed.

**Permission errors**: The tests run as `testuser` with sudo access. If you see permission errors, check the Dockerfile.

**Slow first run**: The first run downloads the Debian image and installs dependencies. Subsequent runs are cached and much faster.

**Volume mount issues on macOS**: If you see permission issues, ensure Docker has access to the workspace directory in Docker Desktop settings.
