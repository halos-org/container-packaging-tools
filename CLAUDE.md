⚠️ **THESE RULES ONLY APPLY TO FILES IN /container-packaging-tools/** ⚠️

# Container Packaging Tools

Tooling for generating Debian packages from container application definitions.

**Local Instructions**: For environment-specific instructions and configurations, see @CLAUDE.local.md (not committed to version control).

## Git Workflow Policy

**Branch Workflow:** Never push to main directly - always use feature branches and PRs.

## Project Purpose

This package provides `generate-container-packages` command that converts simple container app definitions into full Debian packages. The goal is to make it easy for developers to add new container apps without understanding Debian packaging internals.

## Project Status

**Current Phase**: Planning & Initial Development

All development tasks are tracked as GitHub issues. See the [Issues page](https://github.com/hatlabs/container-packaging-tools/issues) for current status.

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
- Python 3.9+ (targeting Debian stable)
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

The `./run` script provides convenient commands for common development tasks:

```bash
./run dev:setup      # Install development dependencies
./run check          # Run all quality checks (lint, format, typecheck)
./run test           # Run all tests
./run test:coverage  # Run tests with coverage
./run build          # Build Debian package
./run dev:clean      # Clean build artifacts
./run help           # Show all available commands
```

**Manual Setup**:
```bash
# Using pip
pip install -e .[dev]

# Or using uv (recommended)
uv pip install -e .[dev]
```

**Manual Testing**:
```bash
# Run tests
pytest

# With coverage
pytest --cov=src

# Linting and formatting
ruff check src/
ruff format --check src/

# Type checking
uvx ty check
# or
mypy src/
```

**Code Quality**:
- Unit tests required for all modules
- Integration tests for full pipeline
- Target >80% code coverage
- All tests must pass before merging

## Building the Package

Once implemented, the tool will be packaged as a Debian package:

```bash
dpkg-buildpackage -us -uc
```

The resulting package will be installable on Debian 12+ and Raspberry Pi OS.

## Related

- **Parent**: [../CLAUDE.md](../CLAUDE.md) - Workspace documentation
- **Users**: [halos-marine-containers](https://github.com/hatlabs/halos-marine-containers)
