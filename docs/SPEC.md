# Container Packaging Tools - Technical Specifications

**Version**: 1.0
**Date**: 2025-11-26
**Status**: Active

## Overview

This document serves as the index to all technical specifications for the Container Packaging Tools project. The project consists of multiple components with distinct functionality, each documented in its own specification.

## Project Purpose

Container Packaging Tools automates the creation of Debian packages for containerized applications. It transforms simple declarative definitions into complete Debian packages with systemd integration, enabling easy distribution and management of container apps through standard APT package management.

## Components

The project consists of two main functional areas:

### 1. Core Package Generation

The core packaging system converts application definitions (metadata.yaml, config.yml, docker-compose.yml) into Debian packages.

**📄 [Package Generation Specification](PACKAGING_SPEC.md)**

This specification covers:
- Input format requirements (metadata, compose, config)
- Package generation process
- Debian package structure
- systemd service integration
- Validation and error handling
- Template system
- Installation and upgrade behavior

### 2. CasaOS Converter

The CasaOS converter transforms applications from the CasaOS app store format into the HaLOS container store format, enabling rapid catalog population.

**📄 [CasaOS Converter Specification](CONVERTER_SPEC.md)**

This specification covers:
- CasaOS format parsing
- Metadata transformation
- Category and field type mapping
- Asset downloading (icons, screenshots)
- Update synchronization with upstream
- Batch conversion capabilities

## Document Organization

Each component has two primary documents:

- **SPEC.md** (Specification): What the system must do - requirements, features, constraints
- **ARCHITECTURE.md** (Architecture): How the system works - components, data flow, design decisions

## Navigation

- **[Main Architecture Document](ARCHITECTURE.md)**: System architecture index
- **[Package Generation Specification](PACKAGING_SPEC.md)**: Core tool requirements
- **[Package Generation Architecture](PACKAGING_ARCHITECTURE.md)**: Core tool design
- **[CasaOS Converter Specification](CONVERTER_SPEC.md)**: Converter requirements
- **[CasaOS Converter Architecture](CONVERTER_ARCHITECTURE.md)**: Converter design
- **[Design Document](DESIGN.md)**: Overall design and planning
- **[Security](SECURITY.md)**: Security considerations

## Development Process

These specifications follow the [HaLOS Project Planning Guide](../../docs/PROJECT_PLANNING_GUIDE.md):

1. Specifications are created before implementation begins
2. Each spec requires review and approval before moving to architecture
3. Architecture documents are created after spec approval
4. Implementation follows documented specifications and architecture

## Versioning

Component specifications are versioned independently. Major changes to functionality require spec updates and review.

---

**Current Component Versions:**
- Core Package Generation: v1.0
- CasaOS Converter: v1.0 (Draft)
