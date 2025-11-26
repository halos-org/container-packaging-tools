# Container Packaging Tools - System Architecture

**Version**: 1.0
**Date**: 2025-11-26
**Status**: Active

## Overview

This document serves as the index to all architecture documentation for the Container Packaging Tools project. The system consists of multiple components with distinct responsibilities, each documented in its own architecture specification.

## System Purpose

Container Packaging Tools automates the creation of Debian packages for containerized applications. The system transforms declarative application definitions into Debian packages with proper systemd integration, validation, and lifecycle management.

## Architectural Components

The system is organized into two main functional subsystems:

### 1. Core Package Generation System

The core system handles conversion of application definitions to Debian packages through template rendering, validation, and package building.

**📐 [Package Generation Architecture](PACKAGING_ARCHITECTURE.md)**

This architecture covers:
- Component structure (CLI, validator, loader, renderer, builder)
- Data flow through the packaging pipeline
- Template system design
- Pydantic schema models
- Debian package structure
- systemd service generation
- Build process and tooling

### 2. CasaOS Converter System

The converter system transforms CasaOS application definitions into HaLOS format, handling parsing, transformation, and asset management.

**📐 [CasaOS Converter Architecture](CONVERTER_ARCHITECTURE.md)**

This architecture covers:
- Converter component structure (parser, transformer, asset manager, generator)
- Integration with core packaging system
- CasaOS format parsing and validation
- Metadata transformation pipeline
- Asset downloading and caching
- Batch processing and update detection
- Configuration mapping system

## System Integration

The two subsystems work together in a pipeline:

```
CasaOS Apps → [Converter] → HaLOS Format → [Core Packager] → Debian Packages
```

The converter produces output (metadata.yaml, config.yml, docker-compose.yml) that serves as input to the core packaging system. This modular design allows:

- Independent development and testing of components
- Support for additional input formats in the future
- Reuse of core packaging logic across different sources

## Technology Stack

**Language**: Python 3.11+ (Debian Trixie baseline)

**Core Libraries**:
- PyYAML: YAML parsing and generation
- Pydantic v2: Schema validation and data modeling
- Jinja2: Template rendering
- requests: HTTP operations (converter)

**Development Tools**:
- pytest: Testing framework
- ruff: Linting and formatting
- ty: Type checking
- Docker: Integration testing

## Deployment Modes

**Development**: Run from source using `uv run` with immediate feedback

**Installed**: Debian package installation to system Python site-packages

**CI/CD**: Automated execution in GitHub Actions workflows

## Document Organization

Each major component has its own architecture document describing:

- Component breakdown and responsibilities
- Data models and schemas
- Processing pipelines and workflows
- Integration points
- Security and performance considerations
- Testing strategy

## Navigation

### Specifications (Requirements)
- **[Main Specification Index](SPEC.md)**: Requirements overview
- **[Package Generation Spec](PACKAGING_SPEC.md)**: Core tool requirements
- **[CasaOS Converter Spec](CONVERTER_SPEC.md)**: Converter requirements

### Architecture (Design)
- **[Package Generation Architecture](PACKAGING_ARCHITECTURE.md)**: Core tool design
- **[CasaOS Converter Architecture](CONVERTER_ARCHITECTURE.md)**: Converter design

### Other Documentation
- **[Design Document](DESIGN.md)**: Overall design and planning
- **[Security](SECURITY.md)**: Security considerations

## Design Principles

### Modularity

Components have clear responsibilities and well-defined interfaces. Each module can be tested and evolved independently.

### Validation First

Input is validated early using Pydantic schemas. Invalid input fails fast with clear error messages before processing begins.

### Template-Based Generation

Debian package files are generated from Jinja2 templates, allowing easy customization and maintenance without code changes.

### Reusability

Core packaging logic is reused across different input sources. The converter produces standard format consumed by the core packager.

### Testability

Each component has comprehensive unit tests. Integration tests verify end-to-end functionality. E2E tests validate actual package installation.

## Extension Points

The architecture supports future extensions:

- **Additional Converters**: Runtipi, Umbrel, or custom formats following the converter interface
- **Output Formats**: Alternative package formats or deployment methods
- **Template Customization**: User-provided templates for specialized package requirements
- **Validation Rules**: Custom validation beyond schema requirements

## Development Workflow

Architecture documents are created after specification approval following the [HaLOS Project Planning Guide](../../docs/PROJECT_PLANNING_GUIDE.md). Implementation must follow documented architecture.

Changes to architecture require updates to these documents and review before implementation.

---

**Current Component Versions:**
- Core Package Generation: v1.0
- CasaOS Converter: v1.0 (Draft)
