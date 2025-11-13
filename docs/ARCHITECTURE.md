# Container Packaging Tools - System Architecture

**Status**: Draft
**Version**: 1.0
**Date**: 2025-11-11
**Last Updated**: 2025-11-11

## Document Purpose

This document describes the system architecture of the Container Packaging Tools project. It details the components, their relationships, data models, technology decisions, and deployment considerations.

## System Overview

### Architectural Style

Container Packaging Tools follows a **pipeline architecture** pattern where input data flows through a series of processing stages to produce output artifacts. The system is designed as a single-process command-line application with no external dependencies or network communication.

### High-Level Architecture

```
Input Directory          Tool Pipeline              Output Directory
┌──────────────┐        ┌─────────────┐            ┌──────────────┐
│ metadata.yaml│───────>│  Validator  │            │              │
│ compose.yml  │        └──────┬──────┘            │              │
│ config.yml   │               │                   │              │
│ (optional)   │        ┌──────▼──────┐            │              │
│ icon.svg/png │───────>│   Loader    │            │              │
│ screenshots  │        └──────┬──────┘            │              │
└──────────────┘               │                   │              │
                        ┌──────▼──────┐            │              │
                        │  Template   │            │              │
                        │  Renderer   │            │              │
                        └──────┬──────┘            │              │
                               │                   │              │
                        ┌──────▼──────┐            │              │
                        │  Package    │            │  .deb file   │
                        │  Builder    │───────────>│  .buildinfo  │
                        └─────────────┘            │  .changes    │
                                                   └──────────────┘
```

## Core Components

### 1. Command-Line Interface (CLI)

**Purpose**: Parse command-line arguments and orchestrate the pipeline

**Responsibilities**:
- Parse and validate command-line arguments
- Set up logging and verbosity levels
- Initialize other components with configuration
- Handle top-level exceptions and exit codes
- Display progress and status messages

**Key Design Decisions**:
- Uses Python argparse for standard Unix-style CLI
- Supports both positional (input directory) and optional arguments
- Exit codes indicate specific error categories for scripting
- Help text generated automatically from argument definitions

**Interactions**:
- Calls Validator with input directory path
- Calls Loader to read and parse input files
- Calls Template Renderer with loaded data
- Calls Package Builder with rendered files
- Reports errors and success messages to user

### 2. Input Validator

**Purpose**: Validate all input files before processing

**Responsibilities**:
- Check required files exist (metadata.yaml, docker-compose.yml, config.yml)
- Validate JSON and YAML syntax
- Validate using Pydantic models
- Perform cross-file consistency checks
- Collect and format validation errors

**Key Design Decisions**:
- Fails fast on first validation error (or collects all errors with --strict)
- Uses Pydantic models for type-safe validation with Python type hints
- Custom validators for cross-file checks
- Clear error messages with file paths and line numbers

**Validation Stages**:

**Stage 1 - File Presence**:
- Verify required files exist
- Check optional file paths if referenced in metadata
- Validate file permissions (readable)

**Stage 2 - Syntax Validation**:
- Parse JSON files with error recovery
- Parse YAML files with error recovery
- Check Docker Compose schema version

**Stage 3 - Schema Validation**:
- Validate metadata.yaml using Pydantic model
- Validate config.yml using Pydantic model
- Check required fields present
- Validate format constraints (names, versions, emails)

**Stage 4 - Cross-Validation**:
- Verify package name ends with `-container`
- Check tags include `role::container-app`
- Ensure config field IDs match environment variables
- Validate referenced files exist (icons, screenshots)

**Interactions**:
- Reads schema files from installed schemas directory
- Returns validation results to CLI
- Provides detailed error context for user feedback

### 3. File Loader

**Purpose**: Load and parse validated input files

**Responsibilities**:
- Load and parse YAML files (metadata, compose, config)
- Copy binary files (icons, screenshots)
- Build internal data model
- Handle file encoding issues

**Key Design Decisions**:
- Assumes files are valid (validation already passed)
- Loads all data into memory (files are small)
- Preserves original YAML structure for templates
- Uses UTF-8 encoding for all text files

**Data Model**:
The Loader produces a unified data structure containing:
- Parsed metadata (Python dict from YAML)
- Docker Compose configuration (Python dict from YAML)
- Configuration schema (Python dict from YAML)
- File paths to binary assets
- Computed values (timestamps, tool version)

**Interactions**:
- Reads files from input directory
- Passes data model to Template Renderer
- Reports file loading errors to CLI

### 4. Template Renderer

**Purpose**: Generate package files from templates and metadata

**Responsibilities**:
- Load Jinja2 templates from installed location
- Create template context from data model
- Render each template file
- Format multi-line text for Debian control files
- Handle optional template sections

**Key Design Decisions**:
- Uses Jinja2 for powerful, maintainable templates
- Templates are separate from code for easy customization
- All template data passed as context dictionary
- Templates handle missing optional fields gracefully

**Template Types**:

**Debian Control Files**:
- debian/control: Package metadata and dependencies
- debian/rules: Build rules (mostly static)
- debian/install: File installation mappings
- debian/compat: Debhelper compatibility (static)
- debian/copyright: License and copyright info
- debian/changelog: Package changelog

**Maintainer Scripts**:
- debian/postinst: Post-installation (service setup)
- debian/prerm: Pre-removal (service stop)
- debian/postrm: Post-removal (cleanup)

**systemd Integration**:
- debian/package-name.service: Service unit file

**Application Files**:
- .env.template: Environment variable defaults

**Template Context Structure**:
The context passed to templates includes:
- package: All package metadata (name, version, description, etc.)
- service: systemd service configuration
- paths: Standard installation paths
- web_ui: Web interface configuration
- default_config: Default environment variables
- timestamp: Build timestamp
- tool_version: Tool version for tracking

**Interactions**:
- Loads templates from `/usr/share/container-packaging-tools/templates/`
- Receives data model from Loader
- Writes rendered files to build directory
- Reports rendering errors to CLI

### 5. Package Builder

**Purpose**: Build Debian package using dpkg-buildpackage

**Responsibilities**:
- Create build directory structure
- Copy source files to build directory
- Copy rendered templates to debian/ subdirectory
- Invoke dpkg-buildpackage with appropriate flags
- Move generated packages to output directory
- Clean up temporary build artifacts

**Key Design Decisions**:
- Uses standard Debian tools (no custom package building)
- Generates binary-only unsigned packages by default
- Preserves build directory on failure for debugging
- Captures build output for error reporting

**Build Process Flow**:

**Step 1 - Preparation**:
- Create temporary build directory
- Create debian/ subdirectory
- Copy input files (metadata, compose, config, icons)

**Step 2 - File Installation**:
- Write rendered templates to debian/
- Set executable permissions on debian/rules
- Set executable permissions on maintainer scripts

**Step 3 - Package Building**:
- Execute dpkg-buildpackage with flags: -b -us -uc
- Capture stdout and stderr
- Monitor exit code

**Step 4 - Artifact Collection**:
- Move .deb file to output directory
- Move .buildinfo and .changes files to output directory
- Preserve or clean build directory based on flags

**Interactions**:
- Receives rendered files from Template Renderer
- Invokes system dpkg-buildpackage command
- Reports build progress and errors to CLI
- Returns package file paths on success

## Data Models

### Metadata Model

**Source**: metadata.yaml

**Structure**:
The metadata model contains all package-level information:
- Identity: name, package_name, version, upstream_version
- Description: description, long_description, homepage
- Maintenance: maintainer, license
- Classification: tags, debian_section, architecture
- Dependencies: depends, recommends, suggests
- Web UI: enabled, path, port, protocol
- Configuration: default_config (environment variables)
- Assets: icon, screenshots

**Validation Rules**:
- Package name must match pattern: lowercase, hyphens, must end with `-container`
- Version must be valid Debian version (semver, date-based, CalVer, or hybrid)
- Maintainer must match pattern: `Name <email@domain>`
- Tags must include `role::container-app`
- All fields must conform to JSON schema

### Docker Compose Model

**Source**: docker-compose.yml

**Structure**:
Standard Docker Compose v3.8+ format containing:
- Services: Container definitions with images, ports, volumes, environment
- Volumes: Bind mounts for persistent data (not named volumes)
- Networks: Custom networks (optional)

**Usage**:
- Copied verbatim to package (not parsed or modified)
- Used by systemd service for container lifecycle
- Environment variables substituted at runtime from .env file

**Integration Points**:
- Environment variables referenced with ${VAR:-default} syntax
- Volumes should use bind mounts for persistence (paths under /var/lib/container-apps/<package>/)
- Container name should be meaningful for management
- No restart policy (systemd manages lifecycle)

### Configuration Schema Model

**Source**: config.yml

**Structure**:
Hierarchical configuration definition:
- Version: Schema version (currently "1.0")
- Groups: Array of field groups
  - Group ID: Identifier (lowercase_snake_case)
  - Group Label: Display name
  - Group Description: Help text (optional)
  - Fields: Array of field definitions
    - Field ID: Environment variable name (UPPER_SNAKE_CASE)
    - Field Label: Display name
    - Field Type: Data type (string, integer, boolean, enum, path, password)
    - Default: Default value
    - Required: Whether field is required
    - Constraints: min, max, options (type-dependent)
    - Description: Help text

**Purpose**:
- Defines user-configurable parameters
- Used by Cockpit UI (Phase 2) for configuration forms
- Drives environment variable generation in .env file

**Field Types**:
- string: Text input
- integer: Numeric input with optional min/max
- boolean: Checkbox or toggle
- enum: Select from predefined options
- path: File or directory path
- password: Masked text input

### Package Output Model

**Generated Artifacts**:
The tool produces three primary artifacts:

**1. Debian Binary Package (.deb)**:
Contains all installed files with metadata

**2. Build Info File (.buildinfo)**:
Build environment information for reproducibility

**3. Changes File (.changes)**:
Package changes and checksums

**Package Contents Structure**:
```
/var/lib/container-apps/<package>/
├── docker-compose.yml
├── metadata.yaml
└── .env.template

/etc/container-apps/<package>/
├── config.yml
└── .env (created by postinst)

/etc/systemd/system/
└── <package>.service

/usr/share/pixmaps/
└── <package>.(svg|png) (if icon provided)

/usr/share/metainfo/
└── <package>.metainfo.xml (AppStream metadata)

/usr/share/doc/<package>/
├── copyright
└── changelog.gz
```

## Technology Stack

### Core Technologies

**Python 3.9+**:
- **Why**: Wide availability on target platforms, excellent library ecosystem
- **Alternatives considered**: Bash (too complex), Go (packaging overhead), Rust (fewer dependencies available)
- **Trade-offs**: Slower than compiled languages but sufficient for tool's use case

**Jinja2**:
- **Why**: Powerful, mature template engine with good error handling
- **Alternatives considered**: String formatting (too limited), mako (less widely used)
- **Trade-offs**: Dependency on external library but worth it for maintainability

**Pydantic v2**:
- **Why**: Type-safe validation using Python type hints, excellent error messages, fast (Rust-based core)
- **Alternatives considered**: jsonschema (more verbose), custom validation (more code)
- **Trade-offs**: None - Pydantic v2 is superior and available in Debian Trixie
- **Benefits**: Can generate JSON schemas for documentation, validates parsed YAML directly

**dpkg-buildpackage**:
- **Why**: Standard Debian package building tool, handles complexity correctly
- **Alternatives considered**: Custom package building (fragile), fpm (not standard)
- **Trade-offs**: Requires full dpkg-dev toolchain but ensures correct packages

### Python Libraries

**Standard Library**:
- argparse: CLI argument parsing
- json: JSON parsing
- pathlib: Path manipulation
- subprocess: External command execution
- logging: Structured logging
- typing: Type hints for clarity

**External Dependencies** (all in Debian Trixie):
- python3-jinja2: Template rendering
- python3-pydantic: Data validation with type hints
- python3-yaml: YAML parsing

### Development Tools

**Package Management**:
- uv: Fast Python package installer and resolver (replaces pip/pip-tools)

**Testing**:
- pytest: Test framework
- pytest-cov: Coverage reporting

**Code Quality**:
- ruff: Fast Python linter and formatter (replaces flake8 and black)
- ty: Fast Rust-based Python type checker (similar to mypy)
- typos: Spell checker for code

### Build Tools

**Debian Packaging**:
- dpkg-dev: Package building utilities
- debhelper: Packaging helper scripts
- lintian: Package quality checks

## Integration Points

### Input Integration

**File System**:
- Reads input files from specified directory
- No network access required
- Works offline

**Validation**:
- Self-contained validation using embedded schemas
- No external validators or services

### Output Integration

**Package Repository**:
- Generated packages compatible with any Debian APT repository
- Can be uploaded to apt.hatlabs.fi or other repos
- Signing happens externally (not tool's responsibility)

**CI/CD Pipeline**:
- Returns appropriate exit codes for automation
- Structured output for parsing (with --json flag in future)
- Reproducible builds (same input → same output)

**Version Control**:
- Input definitions stored in git repositories
- Tool output (.deb files) typically not committed
- Build artifacts generated on-demand or in CI

### Runtime Integration

**systemd**:
- Generated service files integrate with systemd
- Services depend on docker.service
- Logging integrates with journald

**Docker**:
- Uses docker-compose command for container management
- Assumes Docker installed on target system
- No direct Docker API usage

**APT Package Manager**:
- Generated packages install via apt/dpkg
- Dependencies resolved automatically
- Configuration managed via debconf (future)

## Deployment Architecture

### Tool Distribution

**Package Name**: container-packaging-tools

**Installation**:
```
/usr/bin/
└── generate-container-packages

/usr/share/container-packaging-tools/
├── templates/
│   ├── debian/
│   │   ├── control.j2
│   │   ├── rules.j2
│   │   ├── install.j2
│   │   ├── postinst.j2
│   │   ├── prerm.j2
│   │   ├── postrm.j2
│   │   ├── changelog.j2
│   │   ├── copyright.j2
│   │   └── compat
│   └── systemd/
│       └── service.j2
└── schemas/
    ├── metadata.py
    └── config.py

/usr/share/doc/container-packaging-tools/
├── README.md
├── EXAMPLES.md
├── copyright
└── changelog.gz
```

**Dependencies**:
All dependencies are resolved by APT during installation:
- Python runtime and libraries
- Debian packaging tools
- Docker (recommended for testing generated packages)

### Execution Environment

**Development**:
- Developer workstations (macOS, Linux)
- Docker containers for isolated testing
- CI/CD runners (GitHub Actions)

**Production**:
- Build servers (dedicated or CI/CD)
- Developer machines (ad-hoc package creation)
- Automated pipelines (scheduled builds)

**Target Deployment**:
- Raspberry Pi 4/5 running Raspberry Pi OS (arm64)
- Any Debian 12+ system (amd64, arm64)
- Docker must be installed on target systems

## Security Considerations

### Input Validation

**Threat**: Malicious input files could exploit validation or template rendering

**Mitigation**:
- Schema validation catches malformed input
- No code execution from input files
- File paths validated to prevent directory traversal
- YAML safe loader used (no arbitrary code execution)

### File System Access

**Threat**: Tool might overwrite important files or access sensitive data

**Mitigation**:
- Tool only writes to specified output directory
- No root privileges required for package generation
- Generated packages follow standard Debian security practices
- Maintainer scripts reviewed for security issues

### Dependency Security

**Threat**: Compromised dependencies could affect tool behavior

**Mitigation**:
- Only Debian stable dependencies (trusted, reviewed)
- No external network dependencies
- Minimal dependency surface area
- Dependencies updated via Debian security process

### Generated Package Security

**Threat**: Generated packages might be insecure

**Mitigation**:
- Standard file permissions applied
- No setuid/setgid binaries
- Service runs as root (required for Docker) but follows best practices
- User data in separate directories from application data
- Configuration files not world-readable

### Build Environment

**Threat**: Build environment compromise could affect packages

**Mitigation**:
- Reproducible builds minimize attack surface
- Build happens in isolated directory
- Temporary files cleaned up properly
- Build artifacts checksummed

## Performance Considerations

### Expected Performance

**Typical Package Generation**:
- Validation: < 1 second
- Template rendering: < 1 second
- Package building: 2-5 seconds
- Total: < 10 seconds

**Large Packages**:
- With many screenshots/assets: < 20 seconds
- Complex compose files: no significant impact

### Optimization Strategies

**I/O Optimization**:
- Files loaded sequentially (small files, not a bottleneck)
- Binary files copied efficiently
- Temporary directory on fast storage

**CPU Optimization**:
- Single-threaded (sufficient for use case)
- No CPU-intensive operations
- Template rendering is fast for small templates

**Memory Optimization**:
- All input files fit in memory (typically < 1 MB)
- No streaming required
- Python garbage collection handles cleanup

### Scalability

**Concurrent Builds**:
- Tool is stateless and safe for concurrent execution
- Different output directories for parallel builds
- No shared state between invocations

**Batch Processing**:
- Can process multiple apps in sequence or parallel
- CI/CD can run multiple instances safely
- No resource contention concerns

## Extensibility and Future Enhancements

### Extension Points

**Custom Templates**:
Future versions could support:
- User-provided template overrides
- Template includes and inheritance
- Custom template functions

**Plugin Architecture**:
Potential plugin system for:
- Custom validators
- Alternative build backends
- Post-processing hooks
- Format converters

**Configuration**:
Future configuration file could specify:
- Template directory overrides
- Default values
- Build options
- Output formats

### Phase 2+ Architecture Changes

**AppStream Metadata**:
- Add AppStream XML template
- Generate desktop files for GUI apps
- Include additional metadata fields

**Multi-Architecture**:
- Cross-compilation support
- Architecture-specific templates
- Multi-arch package generation

**Package Signing**:
- GPG integration for signing
- Keyring management
- Signature verification

**Alternative Backends**:
- Podman support as Docker alternative
- containerd support
- OCI bundle generation

## Testing Strategy

### Unit Testing

**Component Tests**:
- Validator: Test each validation rule independently
- Loader: Test file parsing edge cases
- Template Renderer: Test template logic
- Path generator: Test path construction

**Test Coverage Target**: >80%

### Integration Testing

**End-to-End Tests**:
- Valid input → successful package
- Invalid input → appropriate error
- Generated package installs correctly
- Service starts and stops properly
- Package removes cleanly

**Test Environments**:
- Docker containers (Debian 12)
- Raspberry Pi OS images
- Multiple architecture emulation

### Validation Testing

**Schema Validation**:
- Every schema rule has test case
- Edge cases (min/max, boundaries)
- Invalid format detection
- Missing field detection

### Package Testing

**Generated Package Quality**:
- Lintian checks pass
- Files installed to correct locations
- Permissions set correctly
- Service unit is valid
- Scripts execute without errors

### Performance Testing

**Benchmarks**:
- Package generation time
- Validation performance
- Memory usage
- Concurrent build handling

## Error Handling Strategy

### Error Categories

**User Errors** (Exit 1):
- Invalid input files
- Schema violations
- Missing required files
Guidance: Clear message with correction suggestion

**System Errors** (Exit 3):
- Disk full
- Permission denied
- dpkg-buildpackage failure
Guidance: System-level troubleshooting steps

**Tool Errors** (Exit 2):
- Template rendering failure
- Internal logic errors
Guidance: Bug report instructions

**Dependency Errors** (Exit 4):
- Missing system packages
- Python import failures
Guidance: Installation instructions

### Error Message Format

**Structure**:
```
ERROR: <Category>: <Problem>
  File: <path>:<line>
  Field: <field_name>
  Current value: <value>
  Expected: <expected_format>
  Suggestion: <how_to_fix>
```

**Examples**:
- Validation errors include file and line
- Missing files show expected location
- Build errors include dpkg output
- Permission errors show required access

## Monitoring and Observability

### Logging

**Log Levels**:
- ERROR: Failures and fatal errors
- WARNING: Potential issues
- INFO: Major processing steps
- DEBUG: Detailed execution trace

**Log Output**:
- Default: stderr (errors and warnings only)
- Verbose: stdout (info messages)
- Debug: stdout (all messages)

### Metrics

**Future Enhancements** (Phase 2+):
- Build success/failure rates
- Average build times
- Common error types
- Package generation statistics

### Debugging

**Debug Mode**:
- Enable with --debug flag
- Shows template rendering details
- Preserves temporary build directory
- Includes full stack traces

**Troubleshooting**:
- Validation mode for pre-flight checks
- Dry-run mode for testing without building
- Keep-temp flag for manual inspection

## Documentation Strategy

### User Documentation

**README.md**:
- Quick start guide
- Installation instructions
- Basic usage examples
- Link to detailed docs

**EXAMPLES.md**:
- Complete working examples
- Common use cases
- Troubleshooting tips
- Best practices

**Man Page** (future):
- Command reference
- Option descriptions
- Examples
- See also section

### Developer Documentation

**Code Comments**:
- Docstrings for all public functions
- Inline comments for complex logic
- Type hints throughout

**Architecture Documentation**:
- This document (ARCHITECTURE.md)
- DESIGN.md for detailed designs
- SPEC.md for requirements

### Schema Documentation

**Pydantic Models**:
- Python docstrings for model classes
- `Field` descriptions for each attribute
- Examples provided via `Field`'s `example` parameter
- Custom validators for complex validation logic

## References

### Internal Documentation

- [SPEC.md](SPEC.md) - Technical specification
- [DESIGN.md](DESIGN.md) - Detailed design
- [META-PLANNING.md](../../META-PLANNING.md) - Project planning
- [PROJECT_PLANNING_GUIDE.md](../../PROJECT_PLANNING_GUIDE.md) - Development workflow

### External References

- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/) - Packaging standards
- [debhelper Documentation](https://manpages.debian.org/testing/debhelper/debhelper.7.en.html) - Build helpers
- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/) - Service units
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/) - Compose format
- [Jinja2 Documentation](https://jinja.palletsprojects.com/) - Template engine
- [JSON Schema](https://json-schema.org/) - Validation specification
- [Pydantic Documentation](https://docs.pydantic.dev/) - Data validation and settings management

## Document History

- **2025-11-11**: Initial architecture document created for Phase 1 development
