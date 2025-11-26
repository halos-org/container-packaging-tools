# Container Packaging Tools - Technical Specification

**Status**: Draft
**Version**: 1.0
**Date**: 2025-11-11
**Last Updated**: 2025-11-11

## Document Purpose

This specification defines the functional and technical requirements for the Container Packaging Tools project. It describes what the system must do and the constraints under which it must operate.

## Project Overview

### Summary

Container Packaging Tools is a command-line utility that automates the generation of Debian packages from container application definitions. It transforms simple declarative definitions (metadata, Docker Compose files, and configuration schemas) into fully functional Debian packages with systemd integration.

### Goals

1. **Standardization**: Establish a consistent, repeatable process for packaging container applications as Debian packages
2. **Automation**: Eliminate manual package creation work and reduce human error
3. **Integration**: Seamlessly integrate with HaLOS ecosystem and Cockpit-based management
4. **Quality**: Ensure generated packages meet Debian policy and quality standards
5. **Usability**: Provide clear error messages and validation feedback to package creators

### Target Users

- **HaLOS Developers**: Creating marine and system container applications
- **Third-Party Developers**: Contributing apps to HaLOS stores
- **Package Maintainers**: Managing container app packages in APT repositories
- **CI/CD Systems**: Automated package generation in build pipelines

## Core Features

### Package Generation

The tool must accept a directory containing application definition files and produce a valid Debian binary package. The generated package must include:

- Standard Debian package metadata (control file, changelog, copyright)
- systemd service unit for container lifecycle management
- Pre- and post-installation scripts for proper system integration
- Application files in standard locations
- User configuration files with sensible defaults

### Input Validation

The tool must validate all input files before attempting package generation:

- **Metadata Validation**: Verify JSON schema compliance, required fields, format constraints
- **Docker Compose Validation**: Check YAML syntax, Docker Compose schema version, environment variable usage
- **Configuration Schema Validation**: Validate field definitions, types, and constraints
- **Cross-Validation**: Ensure consistency between metadata, compose file, and configuration
- **File Checks**: Verify required files exist and optional files meet format requirements

Validation errors must be clear, actionable, and include suggested fixes where possible.

### Template System

The tool must use a flexible template system for generating package files. Templates must:

- Support variable substitution based on application metadata
- Handle optional fields gracefully
- Generate syntactically correct output files
- Be maintainable and customizable
- Support both simple and complex package scenarios

### Error Handling

The tool must provide clear error reporting for:

- Missing or invalid input files
- Schema validation failures
- Template rendering errors
- Build process failures
- System dependency issues

Error messages must include file paths, line numbers where applicable, specific error descriptions, and suggested remediation steps.

## Functional Requirements

### FR1: Command-Line Interface

The tool must provide a command-line interface with the following capabilities:

- Accept input directory path as primary argument
- Support output directory specification
- Provide validation-only mode (no package generation)
- Offer multiple verbosity levels (quiet, normal, verbose, debug)
- Display version information
- Show usage help

### FR2: Input File Processing

The tool must process three required input files:

1. **metadata.yaml**: Package metadata including name, version, description, maintainer, dependencies, and tags
2. **docker-compose.yml**: Docker Compose configuration defining container services, volumes, and networks
3. **config.yml**: User-configurable parameters organized into groups with typed fields

Optional input files include application icons, screenshots, and additional documentation.

### FR3: Package Structure Generation

The tool must generate a complete Debian source package structure including:

- debian/control: Package metadata and dependencies
- debian/rules: Build rules following debhelper conventions
- debian/install: File installation mappings
- debian/postinst: Post-installation script for service setup
- debian/prerm: Pre-removal script for service shutdown
- debian/postrm: Post-removal script for cleanup
- debian/changelog: Package changelog in Debian format
- debian/copyright: Copyright and license information
- debian/compat: Debhelper compatibility level
- debian/*.service: systemd service unit file

### FR4: Path Standardization

The tool must enforce standard installation paths:

- Application files: `/var/lib/container-apps/<package-name>/`
- Configuration files: `/etc/container-apps/<package-name>/`
- systemd service: `/etc/systemd/system/<package-name>.service`
- Application icon: `/usr/share/pixmaps/<package-name>.(svg|png)` (SVG preferred)
- Documentation: `/usr/share/doc/<package-name>/`

### FR5: systemd Integration

The tool must generate systemd service units that:

- Start containers using docker-compose
- Stop containers gracefully on service stop
- Load environment variables from configuration files
- Set proper working directories
- Depend on Docker service availability
- Enable automatic startup on boot
- Integrate with systemd logging (journald)

### FR6: Configuration Management

The tool must handle configuration through:

- Environment variable templates generated from metadata defaults
- Configuration files created during package installation
- Preservation of user configuration during package upgrades
- Removal options (keep or purge) during package removal

### FR7: Package Building

The tool must invoke dpkg-buildpackage to create binary packages:

- Generate unsigned binary-only packages by default
- Produce standard Debian package artifacts (.deb, .buildinfo, .changes)
- Handle build errors gracefully with clear error messages
- Support build directory cleanup or preservation for debugging

### FR8: Package Naming Conventions

The tool must enforce naming conventions:

- Package names must end with `-container` suffix
- Package names must use lowercase with hyphens
- Version numbers must be valid Debian versions (supports semver, date-based, CalVer, hybrid schemes)
- Filenames must follow Debian standards

**Supported Version Formats**:

The tool supports any versioning scheme compatible with Debian package versioning. Common patterns include:

- **Semantic Versioning (semver)**: `1.2.3`, `2.8.0-1` (with Debian revision)
  - Used by Signal K, OpenCPN, and many modern applications
- **Date-based**: `20250113`, `20250113-1` (YYYYMMDD format)
  - Used by AvNav and applications with frequent time-based releases
- **Calendar Versioning (CalVer)**: `2025.01.13`, `2025.1-1`
  - Alternative date-based format with better human readability
- **Hybrid schemes**: `5.8.4+git20250113`, `3.2.1~rc1`
  - Combines base version with additional metadata (git date, release candidate, etc.)
- **Epoch versioning**: `1:2.8.0` (for handling version scheme changes)

Version validation uses `dpkg --compare-versions` to ensure compatibility with Debian's version comparison algorithm.

### FR9: Tagging and Categorization

The tool must support Debian tags (debtags) for package categorization:

- Require `role::container-app` tag for all packages
- Support additional field tags (e.g., `field::marine`, `field::home-automation`)
- Validate tag format and known tag names
- Generate tag entries in package control file

### FR10: AppStream Metadata Generation

The tool must generate AppStream metadata for software center integration:

- Create AppStream XML file from package metadata
- Include application name, summary, description, icon, screenshots
- Support categorization with AppStream categories
- Install to `/usr/share/metainfo/` for GNOME Software, KDE Discover integration
- Validate generated XML against AppStream specification
- Enable discovery in software centers beyond Cockpit

## Technical Requirements

### TR1: Programming Language and Runtime

The tool must be implemented in Python 3.11 or later for:

- Wide availability on Debian Bookworm (Stable) and later systems
- Strong typing support including modern union types (X | Y syntax)
- Rich ecosystem of libraries for YAML, JSON, templating
- Ease of maintenance and contribution
- Good error handling and reporting capabilities

### TR2: Dependencies

The tool must depend only on packages available in Debian Bookworm (Stable) and later:

- python3 (>= 3.11)
- python3-jinja2 (templating)
- python3-pydantic (>= 2.0) (validation with type hints)
- python3-yaml (YAML parsing)
- dpkg-dev (package building tools)
- debhelper (>= 12)

No external dependencies outside Debian repositories are permitted.

### TR3: Distribution Package

The tool itself must be distributed as a Debian package:

- Package name: `container-packaging-tools`
- Install executable to `/usr/bin/`
- Install templates to `/usr/share/container-packaging-tools/templates/`
- Install schemas to `/usr/share/container-packaging-tools/schemas/`
- Install documentation to `/usr/share/doc/container-packaging-tools/`
- Follow Debian packaging standards and policies

### TR4: File Formats

The tool must support standard file formats:

- YAML for all configuration files (YAML 1.2)
- SVG or PNG for application icons (SVG preferred for scalability)
- PNG for screenshots
- Markdown for documentation
- Plain text for logs and error messages

### TR5: Data Validation

The tool must use Pydantic for validation:

- Define Pydantic models for metadata.yaml and config.yml structures
- Validate required fields, data types, format constraints using type hints
- Provide clear, actionable validation error messages
- Support model versioning for future extensions
- Validate parsed YAML data directly with type safety
- Can export JSON schemas for documentation purposes

### TR6: Template Engine

The tool must use Jinja2 for template rendering:

- Support variable substitution and expressions
- Handle optional fields with conditional blocks
- Format multi-line text appropriately for Debian control files
- Generate syntactically correct output

### TR7: Debian Compatibility

Generated packages must be compatible with:

- Debian 12 (bookworm) and later
- Raspberry Pi OS 64-bit (based on Debian)
- Standard Debian packaging tools (dpkg, apt)
- Debian Policy Manual version 4.5.0 or later

### TR8: Docker Compose Compatibility

The tool must support Docker Compose file format version 3.8 or later, including:

- Service definitions with images and build contexts
- Bind mounts for data persistence (preferred over named volumes)
- Environment variable substitution
- Port mappings
- Network definitions
- No restart policies (lifecycle managed by systemd)

## Non-Functional Requirements

### NFR1: Performance

- Package generation must complete in under 10 seconds for typical applications
- Validation-only mode must complete in under 2 seconds
- Memory usage must not exceed 100 MB during normal operation
- Support concurrent execution for batch processing

### NFR2: Reliability

- Validation must catch all schema violations before package building
- Build failures must not leave partial artifacts in output directory
- Error handling must be comprehensive with no uncaught exceptions
- Generated packages must install and remove cleanly

### NFR3: Usability

- Command-line interface must follow Unix conventions
- Error messages must be clear and actionable
- Help text must be comprehensive and include examples
- Validation feedback must guide users to correct problems
- Exit codes must indicate specific error categories

### NFR4: Maintainability

- Code must follow Python PEP 8 style guidelines
- Functions must be modular with clear responsibilities
- Templates must be separate from code logic
- Schemas must be external and versionable
- Comments must explain complex logic and edge cases

### NFR5: Testability

- Core functions must be unit testable
- Integration tests must verify complete package generation
- Test fixtures must cover valid and invalid inputs
- Tests must run in CI/CD environments
- Generated packages must be installable in test containers

### NFR6: Security

- Validation must prevent path traversal attacks
- File permissions must be set appropriately
- No execution of arbitrary code from input files
- Package scripts must follow security best practices
- Dependencies must be from trusted repositories only

### NFR7: Documentation

- CLI help must document all options and arguments
- README must provide quick start guide and examples
- EXAMPLES.md must show common use cases
- Schema documentation must explain all fields
- Generated packages must include proper documentation

### NFR8: Extensibility

- Template system must allow customization
- Schema validation must support custom fields
- Architecture must accommodate future enhancements
- Plugin system considerations for Phase 2+

## Constraints and Assumptions

### Constraints

1. **Platform**: Must run on Debian-based ARM64 systems (Raspberry Pi 4/5)
2. **Dependencies**: Only Debian stable repository packages permitted
3. **Docker**: Assumes Docker is installed and available on target systems
4. **Permissions**: Package installation requires root/sudo access
5. **systemd**: Target systems must use systemd as init system
6. **Network**: No network access required during package generation (offline capable)

### Assumptions

1. Input files are created by humans or trusted tools, not arbitrary user input
2. Docker Compose files reference published container images or local builds
3. Users have basic knowledge of Debian packaging concepts
4. Target systems have sufficient disk space for container images and volumes
5. Container applications expose configuration through environment variables
6. Application maintainers will keep metadata and compose files synchronized

## Out of Scope

The following features are explicitly out of scope for Phase 1:

### Not Included in Phase 1

1. **GUI Interface**: No graphical configuration wizard (command-line only)
2. **Repository Publishing**: No automatic upload to APT repositories
3. **Package Signing**: No GPG signing support
4. **Multi-Architecture Builds**: No cross-compilation support
5. **Conversion Tools**: No import from other app store formats
6. **Container Validation**: No runtime testing of container functionality
7. **Image Building**: No Docker image building, only references to existing images
8. **Alternative Runtimes**: Docker Compose only, no podman or containerd support
9. **Custom Templates**: No user-customizable template system

## Success Criteria

The Container Packaging Tools project will be considered successful when:

1. **Functional Completeness**: All core features are implemented and working
2. **Quality**: Generated packages install cleanly and services start reliably
3. **Usability**: Developers can create packages without reading extensive documentation
4. **Integration**: Tool integrates smoothly into HaLOS development workflow
5. **Validation**: At least 5 real applications successfully packaged using the tool
6. **Documentation**: Complete usage documentation with examples
7. **Testing**: Comprehensive test suite with >80% code coverage
8. **Acceptance**: Tool is used for all marine container app packaging in Phase 1

## Acceptance Testing

### Test Cases

1. **TC1**: Generate package from minimal valid input (metadata, compose, config)
2. **TC2**: Validate detection of missing required files
3. **TC3**: Validate detection of schema violations in metadata
4. **TC4**: Validate detection of invalid Docker Compose syntax
5. **TC5**: Install generated package on clean Debian system
6. **TC6**: Verify systemd service starts and runs container
7. **TC7**: Verify configuration file creation and environment variable loading
8. **TC8**: Remove package and verify cleanup (config preserved)
9. **TC9**: Purge package and verify complete removal (config deleted)
10. **TC10**: Generate 5 real marine applications successfully

## References

### Internal Documentation

- [DESIGN.md](DESIGN.md) - Detailed design specifications
- [META-PLANNING.md](../../META-PLANNING.md) - Overall project planning
- [PROJECT_PLANNING_GUIDE.md](../../PROJECT_PLANNING_GUIDE.md) - Development workflow

### External Standards

- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/) - Debian packaging standards
- [Debian New Maintainers' Guide](https://www.debian.org/doc/manuals/maint-guide/) - Package creation guide
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/) - Compose file format
- [JSON Schema Specification](https://json-schema.org/) - Schema validation standard
- [systemd Service Units](https://www.freedesktop.org/software/systemd/man/systemd.service.html) - Service file format
- [Semantic Versioning](https://semver.org/) - Version numbering specification

## Document History

- **2025-11-11**: Initial specification created for Phase 1 development
