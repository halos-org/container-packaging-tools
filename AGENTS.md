⚠️ **THESE RULES ONLY APPLY TO FILES IN /container-packaging-tools/** ⚠️

# Container Packaging Tools - Development Guide

## 🎯 For Agentic Coding: Use the HaLOS Workspace

This repository should be used as part of the halos-distro workspace for AI-assisted development:

```bash
# Clone workspace and all repos
git clone https://github.com/halos-org/halos-distro.git
cd halos-distro
./run repos:clone
```

See `halos-distro/docs/` for development workflows and guidance.

## About This Project

Tooling for generating Debian packages from container application definitions.

**Local Instructions**: For environment-specific instructions and configurations, see @CLAUDE.local.md (not committed to version control).

## Container Lifecycle Conventions

All container apps must follow these conventions in their `docker-compose.yml`:

### Restart Policy

```yaml
services:
  myapp:
    restart: unless-stopped
```

**Rationale**: Docker handles per-container restarts (fast recovery for individual containers). Systemd is the fallback for compose process failures. This is critical for multi-service compose files where sidekick containers can crash independently.

### Logging Driver

```yaml
services:
  myapp:
    logging:
      driver: journald
      options:
        tag: "{{.Name}}"
```

**Rationale**: Provides unified logging via `journalctl -u <service>` with per-container filtering using `journalctl CONTAINER_NAME=<container>`. Eliminates log duplication (no separate json-file storage).

### Validation

The validator enforces these conventions as **blocking errors**. Apps that don't follow them will fail to build.

See [halos-distro#49](https://github.com/halos-org/halos-distro/issues/49) for the full design rationale.

## Git Workflow Policy

**Branch Workflow:** Never push to main directly - always use feature branches and PRs.

**Pre-Push Requirements:** ALWAYS run these checks locally before pushing to PR:
```bash
# Code quality checks
./run lint              # Linter must pass
./run format:check      # Formatting must pass
uvx ty check src/       # Type checker must pass

# Test checks (matching CI)
uv run pytest tests/test_*.py -m "not integration and not install" -q  # Unit tests
uv run pytest tests/test_*.py -m "integration and not install" -q      # Integration tests
```

All checks must pass locally before pushing. This prevents wasting CI resources and iteration cycles.

## Project Purpose

This package provides `generate-container-packages` command that converts simple container app definitions into full Debian packages. The goal is to make it easy for developers to add new container apps without understanding Debian packaging internals.

## Project Status

**Current Phase**: Planning & Initial Development

All development tasks are tracked as GitHub issues. See the [Issues page](https://github.com/halos-org/container-packaging-tools/issues) for current status.

**Development Phases**:
1. **Core Infrastructure** (Issues #1-6): Validation, loading, and context building
2. **Templates** (Issues #7-13): Jinja2 templates and renderer
3. **Building** (Issues #14-16): Package builder and CLI
4. **Integration Testing** (Issues #17-18): End-to-end tests
5. **Packaging & Documentation** (Issues #19-22): Tool packaging, examples, CI/CD
6. **Polish** (Issues #23-24): Security review and final validation

See [PROJECT_PLANNING_GUIDE.md](../PROJECT_PLANNING_GUIDE.md) in the parent directory for the development workflow.

## Planning Documentation

Important planning documents are in the `docs/` directory:
- @docs/DESIGN.md: High-level design
- @docs/SPEC.md: Technical specification
- @docs/ARCHITECTURE.md: System architecture

## Repository Structure

```
container-packaging-tools/
├── src/
│   └── generate_container_packages/    # Main package
│       ├── __init__.py                 # Package version
│       ├── __main__.py                 # Entry point
│       ├── cli.py                      # Command-line interface
│       ├── validator.py                # Input validation
│       ├── loader.py                   # File loading
│       ├── template_context.py         # Template context builder
│       ├── renderer.py                 # Jinja2 template renderer
│       └── builder.py                  # Package builder
├── schemas/                            # Pydantic models for validation
│   ├── metadata.py                     # metadata.yaml schema
│   └── config.py                       # config.yml schema
├── templates/                          # Jinja2 templates for Debian files
│   ├── debian/
│   │   ├── control.j2
│   │   ├── rules.j2
│   │   ├── postinst.j2
│   │   ├── prerm.j2
│   │   ├── postrm.j2
│   │   ├── changelog.j2
│   │   ├── copyright.j2
│   │   └── compat
│   ├── systemd/
│   │   └── service.j2
│   └── appstream/
│       └── metainfo.xml.j2
├── tests/                              # Test suite
│   ├── fixtures/                       # Test fixtures
│   │   ├── valid/                      # Valid app definitions
│   │   │   ├── simple-app/
│   │   │   └── full-app/
│   │   └── invalid/                    # Invalid app definitions
│   ├── test_models.py                  # Pydantic model tests
│   ├── test_validator.py               # Validation tests
│   ├── test_integration.py             # Integration tests
│   └── test_package_install.py         # Installation tests
├── debian/                             # Debian packaging for this tool
│   ├── control
│   ├── rules
│   ├── install
│   └── ...
├── docs/
│   ├── SPEC.md                         # Technical specification
│   └── ARCHITECTURE.md                 # System architecture
├── pyproject.toml                      # Python packaging config
├── EXAMPLES.md                         # Usage examples
└── README.md                           # Project README
```

## Development

**Tech Stack**:
- Python 3.11+ (targeting Debian stable)
- Pydantic v2 for data validation
- Jinja2 for templating
- PyYAML for YAML parsing
- argparse for CLI (standard library)

**Development Tools**:
- pytest for testing
- ruff for linting and formatting
- ty for type checking (Rust-based Python type checker)
- uv for dependency management (in CI)

**Quick Start with Run Script**:

The `./run` script provides convenient commands for common development tasks.

**IMPORTANT: All development commands run in Docker containers**

First, build the development container:
```bash
./run docker:build   # Build the Debian Trixie development container
```

Then use Docker-based commands for all development tasks:
```bash
# Testing
./run test           # Run all tests in Docker
./run test:coverage  # Run tests with coverage report (80% required)
./run test:unit      # Run unit tests only
./run test:integration  # Run integration tests only

# Code Quality
./run check          # Run all quality checks (lint, format, typecheck)
./run lint           # Run ruff linter
./run lint:fix       # Run linter with auto-fix
./run format         # Format code with ruff
./run format:check   # Check formatting without changes
./run typecheck      # Run ty type checker

# Building
./run build          # Build Debian package in Docker

# Docker Management
./run docker:shell   # Open interactive shell in container
./run docker:clean   # Remove Docker containers and images

# Utilities
./run help           # Show all available commands
```

**Why Docker?**
- Tests require `dpkg-buildpackage` which is not available on all systems (especially macOS)
- Ensures consistent Debian Trixie environment across all developers
- Prevents "works on my machine" issues
- All CI/CD runs in the same Docker environment

**Local Development** (without Docker):
If you want to run tests locally (e.g., for faster iteration), you'll need:
```bash
# Debian/Ubuntu only - install build tools
sudo apt install dpkg-dev debhelper dh-python python3-all

# Install dependencies
uv sync --dev

# Run tests locally (will fail on non-Debian systems)
uv run pytest
```

**Code Quality**:
- Unit tests required for all modules
- Integration tests for full pipeline
- Target >80% code coverage
- All tests must pass before merging

## Building the Package

The tool is packaged as a Debian package using Docker:

```bash
./run build   # Builds in Docker with dpkg-buildpackage
```

Or manually in a Debian/Ubuntu environment:
```bash
dpkg-buildpackage -us -uc
```

The resulting package will be installable on Debian 12+ (Trixie) and Raspberry Pi OS.

## Related

- **Parent**: [../AGENTS.md](../AGENTS.md) - Workspace documentation
- **Users**: [halos-marine-containers](https://github.com/halos-org/halos-marine-containers)
