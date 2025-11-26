# CasaOS to HaLOS Converter - System Architecture

**Version:** 1.0
**Date:** 2025-11-26
**Status:** Draft

## Overview

The CasaOS to HaLOS converter is a Python-based conversion system integrated into the container-packaging-tools package. It transforms CasaOS application definitions into HaLOS container store format, enabling rapid population of the HaLOS app catalog from the existing CasaOS ecosystem. The architecture emphasizes modularity, testability, and seamless integration with existing tooling.

## System Components

### Component Hierarchy

The converter operates as a submodule within container-packaging-tools, extending its capabilities rather than replacing them:

**Container Packaging Tools**
- Core packaging engine (existing)
- Schema models (existing)
- **CasaOS Converter** (new)
  - Parser layer
  - Transformation layer
  - Asset management
  - Output generation

### Component Descriptions

#### CLI Extension

The converter extends the existing generate-container-packages CLI with new commands for CasaOS conversion. It adds subcommands or flags that invoke the conversion pipeline before passing to the standard packaging pipeline.

The CLI maintains consistency with existing command patterns while adding converter-specific options for batch processing, update detection, and source repository handling.

#### CasaOS Parser

The parser reads CasaOS docker-compose.yml files and extracts both standard Docker Compose configuration and x-casaos metadata extensions. It validates the input structure and normalizes it into internal data models.

The parser handles two levels of CasaOS metadata: app-level metadata at the compose root and service-level metadata within individual services. It merges these into a unified representation for transformation.

#### Metadata Transformer

The transformer maps CasaOS structures to HaLOS structures using configurable mapping rules. It implements the core conversion logic: category mapping, field type inference, configuration grouping, and path transformation.

The transformer makes intelligent decisions about field organization, generates appropriate validation rules, and enriches metadata with HaLOS-specific requirements. It applies the casaos- prefix to package names and tracks conversion provenance.

#### Asset Manager

The asset manager downloads icons and screenshots from URLs specified in CasaOS metadata. It implements caching, retry logic, validation, and parallel downloads for efficiency.

The manager validates downloaded assets for format, size, and integrity. It handles network failures gracefully and maintains a cache to avoid repeated downloads during development and testing.

#### Configuration Generator

The configuration generator creates HaLOS config.yml files from CasaOS environment variable definitions. It organizes fields into logical groups, infers appropriate field types, and generates validation rules.

The generator applies heuristics to determine grouping: network-related fields go together, authentication fields form another group, and storage configuration is separated. It creates sensible defaults and helpful descriptions.

#### Output Writer

The output writer creates the three HaLOS files with proper formatting and validation. It generates metadata.yaml, config.yml, and docker-compose.yml, ensuring each conforms to HaLOS schemas.

The writer validates all output against Pydantic models before writing files. It handles file permissions, creates necessary directories, and provides detailed error messages for validation failures.

#### Update Detector

The update detector compares the current state of converted apps with the upstream CasaOS repository to identify changes. It tracks which apps are new, which have been updated, and which have been removed.

The detector uses conversion timestamps and upstream commit hashes to determine what needs re-conversion. It generates sync reports showing exactly what changed and what actions are recommended.

## Technology Stack

### Core Technologies

**Python 3.11+**: Implementation language matching Debian Trixie baseline for compatibility with existing container-packaging-tools codebase.

**PyYAML**: YAML parsing and generation for all configuration files. Used for both reading CasaOS input and generating HaLOS output.

**Pydantic v2**: Schema validation and data modeling. Reuses existing PackageMetadata and ConfigSchema models from container-packaging-tools.

**requests**: HTTP client for downloading assets. Includes retry logic and timeout handling for reliability.

### Development Tools

**pytest**: Testing framework with fixtures. Integrates with existing container-packaging-tools test suite.

**ruff**: Linting and formatting. Uses same configuration as container-packaging-tools for consistency.

**ty**: Type checking. Ensures type safety across the converter codebase.

**Docker**: Integration testing environment matching container-packaging-tools CI setup.

### Optional Dependencies

**tqdm**: Progress bars for batch conversion operations providing user feedback during long-running tasks.

**Pillow**: Image validation and manipulation for icons and screenshots.

## Data Models

### Internal Models

**CasaOSApp**: Represents a parsed CasaOS application with all metadata and configuration. Contains fields for:
- App name, description, tagline
- Category and tags
- Service definitions
- Environment variables with metadata
- Port and volume configurations
- Icon and screenshot URLs
- Developer information

**HaLOSPackage**: Target format representation containing all data needed for the three output files. Maps directly to metadata.yaml, config.yml, and docker-compose.yml structure.

**ConversionContext**: State tracking object maintaining conversion progress, warnings, errors, downloaded assets, and transformation decisions. Enables detailed reporting and debugging.

**UpdateReport**: Describes changes detected between current converted apps and upstream CasaOS repository. Lists new apps, updated apps, removed apps, and recommended actions.

### Schema Integration

The converter reuses existing Pydantic models from container-packaging-tools:

**PackageMetadata**: Validates generated metadata.yaml ensuring all required fields are present and correctly formatted.

**ConfigSchema**: Validates generated config.yml ensuring proper group and field structure.

These models ensure converter output is immediately compatible with the packaging pipeline without additional validation layers.

### Mapping Configuration

**CategoryMap**: YAML configuration mapping CasaOS categories to HaLOS categories. Includes fallback rules for unknown categories.

**FieldTypeRules**: YAML configuration defining heuristics for inferring config.yml field types from CasaOS environment variables.

**PathTransformRules**: YAML configuration for converting CasaOS volume paths to HaLOS conventions.

## Processing Pipeline

### Single App Conversion Flow

**Stage 1 - Input Loading**: Read CasaOS docker-compose.yml from directory or repository, parse YAML structure, validate basic syntax.

**Stage 2 - Metadata Extraction**: Extract x-casaos metadata from root level, extract x-casaos metadata from service level, merge into unified CasaOSApp model.

**Stage 3 - Validation**: Validate CasaOS structure against expected schema, check for required fields, verify container image references.

**Stage 4 - Transformation**: Map category to HaLOS taxonomy, infer field types for environment variables, organize fields into logical groups, apply path transformations, generate package name with casaos- prefix.

**Stage 5 - Asset Download**: Download icon from URL, download screenshots, validate formats and sizes, cache downloaded assets.

**Stage 6 - Output Generation**: Create metadata.yaml with package metadata, create config.yml with field groups, create docker-compose.yml without x-casaos extensions, validate all outputs against schemas.

**Stage 7 - Writing**: Write three files to output directory, set appropriate file permissions, generate conversion report.

### Batch Conversion Flow

For converting multiple apps from the CasaOS repository:

**Initialization**: Clone or update CasaOS-AppStore repository, scan for all app directories, load previous conversion state.

**App Discovery**: Identify all apps in repository, compare with previously converted apps, determine which apps need conversion.

**Parallel Processing**: Process multiple apps concurrently up to configured limit, track progress with status updates, collect warnings and errors.

**Aggregation**: Generate summary statistics, create batch report, identify systematic issues, recommend manual review cases.

### Update Synchronization Flow

For re-running converter on updated upstream:

**State Comparison**: Load conversion timestamps from existing apps, fetch latest commit from CasaOS repository, identify modified apps.

**Change Detection**: Determine new apps to convert, determine updated apps to reconvert, determine removed apps to flag.

**Conflict Handling**: Check for manual modifications to existing converted apps, warn about conflicts between local changes and upstream updates, provide options for resolution.

**Selective Conversion**: Convert only changed apps unless full reconversion requested, preserve manually edited apps unless overridden, generate detailed sync report.

## File Structure

### Repository Integration

The converter integrates into container-packaging-tools with this structure:

```
container-packaging-tools/
├── src/
│   └── generate_container_packages/
│       ├── converters/              # New converter subsystem
│       │   ├── __init__.py
│       │   ├── base.py              # Base converter interface
│       │   └── casaos/
│       │       ├── __init__.py
│       │       ├── parser.py
│       │       ├── transformer.py
│       │       ├── assets.py
│       │       ├── generator.py
│       │       ├── updater.py
│       │       └── models.py
│       ├── cli.py                   # Extended with converter commands
│       └── ... (existing modules)
├── mappings/                        # New configuration directory
│   └── casaos/
│       ├── categories.yaml
│       ├── field_types.yaml
│       └── paths.yaml
├── tests/
│   ├── converters/                  # New test directory
│   │   └── casaos/
│   │       ├── fixtures/
│   │       │   ├── valid/
│   │       │   │   ├── jellyfin/
│   │       │   │   └── signalk/
│   │       │   └── invalid/
│   │       ├── test_parser.py
│   │       ├── test_transformer.py
│   │       ├── test_assets.py
│   │       ├── test_generator.py
│   │       └── test_integration.py
│   └── ... (existing tests)
└── docs/
    ├── CONVERTER_SPEC.md
    ├── CONVERTER_ARCHITECTURE.md
    └── ... (existing docs)
```

### Configuration Files

Mapping files live in mappings/casaos/ and use YAML format for easy editing without code changes.

**categories.yaml**: Maps CasaOS categories to HaLOS. Example structure:
```yaml
mappings:
  Entertainment: media
  Media: media
  Productivity: productivity
  Developer: development
default: utilities
```

**field_types.yaml**: Rules for field type inference. Example structure:
```yaml
patterns:
  - pattern: ".*PORT$"
    type: integer
    validation: {min: 1024, max: 65535}
  - pattern: ".*PASSWORD$"
    type: password
  - pattern: ".*_DIR$|.*_PATH$"
    type: path
```

**paths.yaml**: Path transformation rules. Example structure:
```yaml
transforms:
  - from: "/DATA/AppData/{app}/"
    to: "${CONTAINER_DATA_ROOT}/"
```

## Integration Points

### Container Packaging Tools Integration

The converter produces output that feeds directly into the existing packaging pipeline. After conversion, the metadata.yaml, config.yml, and docker-compose.yml are processed by the standard package generation logic.

CLI integration adds converter commands while maintaining backward compatibility. Existing commands continue to work unchanged. New commands like `generate-container-packages convert-casaos` invoke the conversion pipeline.

### CasaOS Repository Access

The converter accesses the official CasaOS-AppStore GitHub repository. It can operate on a local clone or fetch directly from GitHub. Repository operations use standard git commands or GitHub API.

The converter tracks the repository commit hash in converted app metadata, enabling change detection during updates.

### HaLOS Container Store Output

Converted apps are written to a specified output directory organized by app. Each app gets its own subdirectory containing the three required files plus assets.

The output structure is compatible with both halos-marine-containers repository and any general container store repository following HaLOS conventions.

### Build Pipeline Integration

The converter integrates with CI/CD workflows. It can be invoked from GitHub Actions to automate conversion on schedule or webhook trigger.

Exit codes and structured logging enable CI integration. The converter reports success, warnings, and failures in a machine-parseable format.

## Deployment Architecture

### Development Mode

Developers run the converter from source using `uv run` or direct Python invocation. Changes to mapping files take effect immediately without reinstallation.

The development mode includes verbose logging, detailed error messages, and access to all intermediate data for debugging.

### Installed Mode

The converter is included in the container-packaging-tools Debian package. Installation places the converter module in Python site-packages and makes commands available system-wide.

Configuration files install to /usr/share/container-packaging-tools/mappings/ with user overrides supported in /etc/container-packaging-tools/.

### CI/CD Mode

GitHub Actions workflows invoke the converter with specific flags for automated operation. The converter runs in batch mode with structured output suitable for automated processing.

Converted apps can be automatically committed to repositories, trigger package builds, and notify maintainers of issues requiring manual review.

## Security Considerations

### Input Validation

All YAML input is parsed with safe_load to prevent code execution. The converter does not evaluate or execute any content from CasaOS files.

Docker Compose configurations are parsed but never executed during conversion. Malicious compose files cannot compromise the conversion process.

### Asset Downloads

Downloads use HTTPS where available and validate content types before accepting. Size limits prevent resource exhaustion from malicious URLs.

The converter validates that downloaded images are actual image files with correct magic bytes, not executables with image extensions.

### Output Safety

Generated files are validated against schemas before writing. The converter cannot produce malformed output that might exploit downstream tools.

File permissions are set appropriately: configuration files get 0644, directories get 0755. No files are created with execute permissions.

### Credential Handling

The converter does not require credentials for public CasaOS repository access. If private repositories are supported in future, credentials are handled through environment variables or credential managers, never hardcoded or logged.

## Performance Considerations

### Parallelization Strategy

Asset downloads are parallelized using thread pools. Multiple downloads occur simultaneously with configurable concurrency limits.

Batch app conversion can process multiple apps in parallel using process pools for CPU-bound transformation work. Parallelization respects system resource limits.

### Caching Strategy

Downloaded assets are cached by URL hash in a local cache directory. The cache persists across converter runs, eliminating redundant downloads.

HTTP cache headers are respected when available. The cache implements LRU eviction when size limits are reached.

Parsed CasaOS apps can be cached to accelerate re-runs during development. The cache invalidates on file modification time changes.

### Resource Limits

Memory usage per app conversion is bounded. Large compose files or metadata do not cause unbounded memory growth.

Disk usage is dominated by downloaded assets. The converter monitors disk space and warns if running low.

Timeouts prevent hung operations. Network operations timeout after 30 seconds per attempt. Total conversion time per app is limited to prevent resource leaks.

## Testing Strategy

### Unit Testing

Each module has dedicated unit tests with mocked dependencies. Parser tests verify handling of various CasaOS formats. Transformer tests validate mapping logic. Generator tests check output correctness.

Unit tests use pytest fixtures for test data. Coverage target is 80% of converter code.

### Integration Testing

Integration tests run full conversion on realistic CasaOS apps from fixtures. Tests verify end-to-end functionality with actual CasaOS files.

Integration tests validate that output passes schema validation and can be packaged by container-packaging-tools.

### End-to-End Testing

E2E tests take converted apps through complete pipeline: conversion, packaging, installation in Docker container, service startup verification.

These tests run in Docker containers matching target Debian environment, ensuring deployment compatibility.

### Regression Testing

Golden test cases capture known good conversions. Any changes to converter logic are validated against golden outputs to detect regressions.

Golden tests cover diverse apps: simple apps, complex apps with many options, apps using various CasaOS features.

## Monitoring and Logging

### Logging Implementation

The converter uses Python logging module with multiple levels. Logger names follow hierarchical pattern: `generate_container_packages.converters.casaos.parser` for fine-grained control.

Log output includes timestamps, module names, and context about which app is being processed.

### Metrics Collection

Batch conversion collects statistics: total apps, successful conversions, failures, warnings, assets downloaded, total bytes downloaded, elapsed time.

These metrics are reported at completion and optionally exported in JSON format for monitoring systems.

### Traceability

Every converted app includes source metadata: converter version, conversion timestamp, CasaOS repository URL, CasaOS repository commit hash, original CasaOS app ID.

This metadata enables auditing, troubleshooting, and future synchronization with upstream.

## Extensibility

### Converter Interface

A base converter interface is defined to enable future converters for other sources like Runtipi. The interface specifies required methods: parse, transform, generate.

CasaOS converter implements this interface. Future converters can reuse common components like asset management and output generation.

### Mapping Customization

YAML mapping files provide declarative customization without code changes. Users can override mappings by placing custom files in configuration directories.

The converter loads mappings from multiple locations with precedence: user overrides, system defaults, built-in defaults.

### Plugin Hooks

While not implemented in v1, the architecture allows for future plugin hooks. Plugins could customize conversion for specific apps, add validation rules, or modify output.

## Development Workflow

### Feature Development

New converter features are developed in feature branches following container-packaging-tools workflow. Pull requests require tests, documentation, and code review.

The converter code follows same quality standards as container-packaging-tools: type hints, docstrings, ruff formatting, ty type checking.

### Testing Requirements

All new code requires unit tests. Complex features require integration tests. Breaking changes or major features require E2E tests.

CI runs full test suite on every push. Tests must pass before merge to main.

### Documentation Standards

Code is documented with docstrings following Google style. User-facing features require documentation updates in README or dedicated docs.

Significant design decisions are captured in architecture decision records for future reference.

## Migration and Rollout

### Initial Conversion

The first conversion run processes all CasaOS apps, generating a complete catalog. Manual review identifies apps needing customization.

A staged rollout converts a subset first for validation, then expands to full catalog once conversion quality is confirmed.

### Ongoing Synchronization

After initial conversion, regular sync runs keep the catalog current. Automated or scheduled runs can be established once quality is proven.

Manual review focuses on new apps and significantly changed apps. Minor updates can be automatically applied.

### Quality Assurance

Converted apps undergo validation: schema compliance, package build success, installation testing, basic functionality verification.

Apps failing validation are flagged for manual review and excluded from automated publishing until fixed.
