# CasaOS to HaLOS Container Store Converter - Technical Specification

**Version:** 1.0
**Date:** 2025-11-25
**Status:** Draft

## Project Overview

The CasaOS to HaLOS Container Store Converter is a command-line tool that automatically converts application definitions from the CasaOS app store format into the HaLOS container store format. This enables rapid population of the HaLOS container store with hundreds of pre-existing applications without manual conversion work.

### Goals

1. **Automation**: Convert CasaOS app definitions to HaLOS format without manual intervention
2. **Accuracy**: Preserve all relevant metadata, configuration, and functionality during conversion
3. **Completeness**: Handle icons, screenshots, and all metadata fields
4. **Quality**: Generate valid HaLOS packages that pass all validation checks
5. **Maintainability**: Support ongoing synchronization with upstream CasaOS app store
6. **Transparency**: Track conversion provenance and enable manual review

## Background

The HaLOS project needs a large catalog of containerized applications to provide value to users. Rather than manually creating hundreds of application definitions, we can leverage the existing CasaOS app store which contains well-maintained application definitions with metadata, icons, and screenshots.

CasaOS uses a Docker Compose-based format with custom metadata extensions. HaLOS uses a similar approach but with different metadata organization. The formats are compatible enough that automated conversion is feasible with high fidelity.

## Core Features

### Input Processing

The converter accepts CasaOS application definitions as input. Each CasaOS app consists of a docker-compose.yml file containing both the container configuration and metadata embedded as x-casaos extensions.

The converter must parse and validate the CasaOS format, extracting both the container definitions and the rich metadata that describes the application's purpose, configuration options, and user interface.

### Metadata Transformation

CasaOS stores metadata in two locations within the docker-compose.yml: app-level metadata at the root under x-casaos, and service-level metadata under each service's x-casaos section.

The converter transforms this embedded metadata into the HaLOS format, which separates concerns into three files: metadata.yaml for package information, config.yml for user configuration schema, and docker-compose.yml for container definitions.

Key transformations include:
- Extracting app name, description, and tagline
- Converting category taxonomies between systems
- Transforming environment variable configurations into structured field definitions
- Mapping port and volume configurations
- Preserving developer information and links

### Configuration Schema Generation

CasaOS defines configuration through environment variable descriptions in the x-casaos metadata. The converter must transform these into the HaLOS config.yml format, which organizes fields into logical groups with rich type definitions.

The converter infers field types from CasaOS type annotations and descriptions, generates appropriate validation rules, and organizes fields into sensible groups like Network Settings, Storage, and Authentication.

### Docker Compose Conversion

The container definitions in CasaOS docker-compose.yml must be converted to HaLOS format. This involves:
- Removing x-casaos metadata extensions from the compose file
- Converting CasaOS-specific variable references to HaLOS conventions
- Adjusting volume paths from CasaOS conventions to HaLOS paths
- Ensuring restart policies are removed (systemd handles lifecycle in HaLOS)
- Preserving all functional container configuration

### Asset Management

CasaOS apps reference icons and screenshots via URLs. The converter must download these assets and include them in the output directory for packaging.

Icons must be validated for correct size and format. Screenshots should be downloaded and organized appropriately. The converter handles missing assets gracefully with warnings rather than failures.

### Source Tracking and Update Support

Every converted app must include metadata tracking its origin from CasaOS. This includes the original app ID, upstream repository URL, conversion timestamp, and any conversion notes or warnings.

The converter must support re-running on an updated CasaOS repository to sync with upstream changes. When re-run, it should:
- Detect which apps have been added, updated, or removed in the upstream CasaOS store
- Re-convert updated apps with new metadata and container definitions
- Preserve any manual customizations by warning when conflicts are detected
- Generate a sync report showing what changed

This enables keeping the HaLOS container store current with the latest CasaOS apps and updates.

## Technical Requirements

### Input Format Support

The converter must correctly parse Docker Compose v3.x format with CasaOS x-casaos extensions. It must handle both app-level and service-level metadata.

The converter must validate input against the CasaOS schema before attempting conversion, providing clear error messages for invalid or incomplete CasaOS definitions.

### Output Format Compliance

Generated metadata.yaml files must pass HaLOS schema validation using the PackageMetadata Pydantic model. All required fields must be present with valid values.

Generated config.yml files must conform to the HaLOS configuration schema with version 1.0 format, properly structured groups and fields.

Generated docker-compose.yml files must be valid Docker Compose format suitable for use with HaLOS container management.

### Category Mapping

The converter implements a mapping table between CasaOS category names and HaLOS categories. CasaOS categories like "Entertainment" and "Media" map to HaLOS "media" category. "Productivity" and "Cloud" map to "productivity". "Developer" maps to "development".

Unmapped categories should be handled with a default mapping and a warning message to allow manual review.

### Field Type Inference

The converter must infer appropriate field types for config.yml from CasaOS environment variable definitions. CasaOS "number" type maps to "integer" type. Text fields may be "string", "password", or "path" depending on the variable name and description.

Port fields are identified by naming patterns and configured with appropriate validation ranges. Boolean fields are detected from default values and descriptions.

### Asset Download

The converter must download icons from URLs specified in CasaOS metadata. Icon downloads should validate image format and dimensions, preferring SVG when available.

Screenshot downloads should handle multiple screenshots per app. Failed downloads generate warnings but do not fail the conversion, allowing manual asset addition later.

Network errors during download should be retried with exponential backoff. The converter should support caching of downloaded assets to avoid repeated downloads during development.

### Package Naming

Package names must follow HaLOS conventions with a source prefix to avoid conflicts. The format is: `casaos-<app-name>-container`.

The app name is derived from the CasaOS app name: all lowercase, spaces removed, and special characters converted to hyphens. For example, CasaOS app "Signal K" becomes `casaos-signalk-container`.

The "casaos-" prefix clearly identifies the package source and prevents naming conflicts with packages converted from other sources like Runtipi or manually created marine apps.

Package names must be validated against Debian naming rules and checked for uniqueness in the target repository.

### Version Handling

The converter extracts version information from CasaOS container image tags when available. If no version is specified, it uses a default version with a note for manual review.

Version numbers must be normalized to Debian-compatible format, removing any incompatible characters or prefixes.

## Non-Functional Requirements

### Performance

The converter should process a single app in under 5 seconds excluding asset downloads. Batch conversion of 100 apps should complete in under 10 minutes.

Asset downloads should be parallelized to minimize total conversion time. The converter should support concurrent processing of multiple apps.

### Reliability

The converter must handle errors gracefully without crashing. Invalid input should produce clear error messages indicating what is wrong and how to fix it.

Partial failures (like missing screenshots) should allow the conversion to complete with warnings. The converter should never produce invalid HaLOS packages that fail validation.

### Usability

The command-line interface should be intuitive with sensible defaults. Progress indicators should show conversion status for batch operations.

Verbose output mode should provide detailed information about conversion decisions and transformations. Quiet mode should suppress all non-error output.

### Maintainability

The codebase should be modular with clear separation between parsing, transformation, and output generation. Each component should be independently testable.

The category mapping and field type inference rules should be configurable through external files to enable updates without code changes.

## Out of Scope

### Not Included

The following are explicitly out of scope for the initial version:

**Runtipi Conversion**: This spec focuses solely on CasaOS conversion. Runtipi conversion will be a separate tool with similar architecture but different input parsing.

**Fully Automated Update Pipeline**: While the converter supports re-running on updated upstream repositories, automatic detection and triggering of conversions (e.g., via webhooks or scheduled jobs) is a future enhancement. The initial version requires manual invocation to sync with upstream updates.

**Multi-Architecture Handling**: The converter assumes apps support all architectures. Architecture-specific handling is deferred to future versions.

**Interactive Configuration**: The tool operates in batch mode. Interactive prompts for ambiguous conversions are not supported in v1.

**Package Building**: The converter outputs HaLOS app definitions ready for packaging. Actual Debian package generation uses the existing container-packaging-tools.

**Repository Publishing**: Uploading converted packages to apt repositories is handled by separate CI/CD infrastructure.

### Future Enhancements

Potential future features include:
- Interactive mode for reviewing and adjusting conversions
- Diff tool to compare CasaOS updates with existing HaLOS definitions
- Statistics and quality metrics for conversion batches
- Integration with GitHub Actions for automated conversion pipelines
- Support for custom conversion rules per-app
- Automatic detection of apps suitable for marine category

## Success Criteria

### Functional Criteria

A successful conversion produces:
- Valid metadata.yaml passing HaLOS schema validation
- Valid config.yml with appropriate field types and groups
- Valid docker-compose.yml suitable for HaLOS deployment
- Downloaded icons and screenshots in correct formats
- Complete source tracking metadata

### Quality Criteria

Converted apps must:
- Install successfully using container-packaging-tools
- Start correctly under systemd management
- Display properly in Cockpit package manager
- Function identically to original CasaOS version
- Include all user-configurable options from CasaOS

### Coverage Criteria

The converter should successfully convert:
- At least 95% of apps from the official CasaOS app store
- All common configuration field types
- All common category mappings
- Apps with multiple screenshots
- Apps with complex environment configurations

## Key Assumptions

### Technical Assumptions

We assume that CasaOS docker-compose.yml files are valid and follow documented CasaOS conventions. We assume icon and screenshot URLs are publicly accessible.

We assume the HaLOS container packaging tools are available and functional. We assume the target system has internet access for asset downloads.

### Business Assumptions

We assume that automatically converting CasaOS apps is legally permissible, as both projects are open source. We assume that CasaOS developers will not object to their metadata being converted to other formats.

We assume that the effort to manually review converted apps is acceptable. We assume that some manual fixup of converted apps is expected and planned for.

### Compatibility Assumptions

We assume that Docker Compose features used by CasaOS apps are compatible with HaLOS deployment. We assume that volume path differences can be transparently handled through variable substitution.

We assume that port mappings and network modes used by CasaOS work in HaLOS environments.

## Constraints

### Platform Constraints

The converter must run on Python 3.11+ to match Debian Trixie requirements. It must use only dependencies available in Debian repositories or via pip.

The converter must produce output compatible with container-packaging-tools which runs on Debian-based systems.

### Data Constraints

Icon files must not exceed 5MB. Screenshot files must not exceed 10MB per image. The total size of downloaded assets per app should not exceed 50MB.

### Time Constraints

Asset downloads must timeout after 30 seconds per file. Total conversion time per app should not exceed 60 seconds to keep batch operations reasonable.

### Legal Constraints

The converter must respect copyright and licensing. All converted apps must include proper attribution to original creators. The converter must preserve license information from CasaOS definitions.

## Acceptance Criteria

The converter is considered complete when:

1. It can parse all well-formed CasaOS docker-compose.yml files
2. It generates HaLOS packages that pass validation
3. Converted packages install and run correctly on HaLOS systems
4. At least 50 CasaOS apps have been successfully converted and tested
5. Documentation covers installation, usage, and troubleshooting
6. Test coverage exceeds 80% for core conversion logic
7. All GitHub issues from TASKS.md are completed
8. Code review by maintainers is approved
9. CI/CD pipeline builds and tests successfully
10. User-facing documentation is published

## Dependencies

### External Dependencies

The converter depends on:
- Python 3.11+ standard library
- PyYAML for YAML parsing and generation
- Pydantic for schema validation (HaLOS models)
- requests library for HTTP downloads
- Jinja2 for template rendering (if used)

### Internal Dependencies

The converter relies on:
- container-packaging-tools schemas (PackageMetadata, ConfigSchema)
- HaLOS container store format documentation
- CasaOS app store format documentation

### System Dependencies

Runtime requires:
- Internet access for asset downloads
- Write access to output directory
- Sufficient disk space for downloaded assets

Development requires:
- pytest for testing
- Docker for integration testing
- Access to CasaOS app store repository for test data

## Related Documentation

- **HaLOS Container Format**: halos-marine-containers/docs/DESIGN.md
- **Container Packaging Tools**: container-packaging-tools/docs/DESIGN.md
- **CasaOS App Store**: https://github.com/IceWhaleTech/CasaOS-AppStore/blob/main/CONTRIBUTING.md
- **General Container Store Architecture**: docs/archive/CONTAINER_STORE_PLAN.md
