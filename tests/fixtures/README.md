# Test Fixtures

This directory contains test fixtures for validating the container packaging tools. Fixtures are organized into two categories: valid and invalid app definitions.

## Valid Fixtures

Valid fixtures represent correct container app definitions that should successfully generate Debian packages.

### simple-app

A minimal valid container app with only required fields.

**Files:**
- `metadata.yaml` - Minimal package metadata
- `docker-compose.yml` - Basic single-service configuration
- `config.yml` - Simple configuration with 2 fields
- `icon.png` - Placeholder icon (PNG format)

**Use Cases:**
- Testing minimal valid configuration
- Baseline validation tests
- Quick integration tests

### full-app

A comprehensive container app demonstrating all available features and optional fields.

**Files:**
- `metadata.yaml` - Complete metadata with all optional fields
- `docker-compose.yml` - Advanced configuration with health checks, networks
- `config.yml` - Multiple configuration groups with various field types
- `icon.svg` - SVG format icon
- `screenshot1.png` - First screenshot
- `screenshot2.png` - Second screenshot

**Use Cases:**
- Testing all configuration options
- Template rendering validation
- Documentation examples
- Complex integration scenarios

**Features Demonstrated:**
- Optional dependencies (depends, recommends, suggests)
- Multiple configuration groups
- All field types (string, integer, boolean, enum, password, path)
- Multiple environment variables
- SVG icon format
- Screenshot assets
- Extended Debian revision in version
- Health checks and networking in docker-compose

## Invalid Fixtures

Invalid fixtures represent incorrect configurations designed to trigger specific validation errors.

### missing-metadata

Missing the required `metadata.yaml` file.

**Expected Error:** File not found - metadata.yaml is required

**Files:**
- `docker-compose.yml` ✓
- `config.yml` ✓
- `metadata.yaml` ✗ (intentionally missing)

### bad-package-name

Package name doesn't end with `-container` suffix.

**Expected Error:** Package name must end with `-container`

**Violation:** `package_name: bad-package-name` (should be `bad-package-name-container`)

### missing-tag

Missing the required `role::container-app` Debian tag.

**Expected Error:** Tags must include `role::container-app`

**Violation:** Only has `implemented-in::docker` tag, missing the required role tag

### invalid-version

Version doesn't follow semantic versioning format.

**Expected Error:** Version must match pattern `^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9]+)?$`

**Violation:** `version: v1.0` (has "v" prefix, missing patch version)

**Valid Examples:**
- `1.0.0` ✓
- `1.0.0-1` ✓ (with Debian revision)
- `2.1.3` ✓
- `v1.0` ✗

### invalid-email

Malformed maintainer email address.

**Expected Error:** Maintainer must match pattern `Name <email@domain>`

**Violation:** `maintainer: Test Developer test@example` (missing angle brackets and proper domain)

**Valid Example:** `Test Developer <test@example.com>` ✓

## Using Test Fixtures

### In Unit Tests

```python
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"
INVALID_FIXTURES = FIXTURES_DIR / "invalid"

def test_valid_simple_app():
    app_dir = VALID_FIXTURES / "simple-app"
    # Test code here
    assert app_dir.exists()

def test_invalid_missing_metadata():
    app_dir = INVALID_FIXTURES / "missing-metadata"
    # Expect validation error
```

### In Integration Tests

```python
import subprocess

def test_package_generation():
    result = subprocess.run(
        ["generate-container-packages", "tests/fixtures/valid/simple-app"],
        capture_output=True
    )
    assert result.returncode == 0
```

## Maintenance

When adding new fixtures:

1. Create a descriptive directory name
2. Include all required files (metadata.yaml, docker-compose.yml, config.yml)
3. Add README.md entry documenting the fixture's purpose
4. Ensure fixture tests the intended scenario
5. Update test suite to use the new fixture

## File Requirements

### metadata.yaml (Required)

Must include:
- name, package_name, version, description
- maintainer, license
- tags (must include `role::container-app`)
- debian_section, architecture

### docker-compose.yml (Required)

- Version 3.8+
- At least one service
- Use environment variable substitution: `${VAR:-default}`
- Set `restart: "no"` (systemd manages lifecycle)

### config.yml (Required)

- version: "1.0"
- At least one group with one field
- Field IDs must match environment variables in docker-compose

### Optional Files

- `icon.svg` or `icon.png` - Application icon
- `screenshot*.png` - Application screenshots
- `README.md` - Additional documentation
