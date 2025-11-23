# Container Packaging Tools - Design Document

**Status**: Draft
**Date**: 2025-11-11
**Last Updated**: 2025-11-11

## Overview

Container Packaging Tools provides a command-line utility for generating Debian packages from container application definitions. It automates the creation of systemd-managed container applications packaged as standard .deb files.

## Purpose

- Standardize container app packaging across HaLOS ecosystem
- Generate compliant Debian packages from simple app definitions
- Automate systemd service configuration for container apps
- Validate app definitions against schemas
- Reduce boilerplate and manual packaging work

## Tool Architecture

### Command-Line Interface

**Primary Command**: `generate-container-packages`

```bash
# Generate package from current directory
generate-container-packages .

# Generate package from specific app directory
generate-container-packages /path/to/app-definition/

# Validate without building
generate-container-packages --validate /path/to/app-definition/

# Specify output directory
generate-container-packages --output /path/to/output/ /path/to/app-definition/

# Verbose output
generate-container-packages --verbose /path/to/app-definition/

# Show version
generate-container-packages --version

# Show help
generate-container-packages --help
```

**Exit Codes**:
- `0`: Success
- `1`: Validation error (invalid input files)
- `2`: Template rendering error
- `3`: Build error (dpkg-buildpackage failed)
- `4`: Missing dependencies

### Package Installation

The tool is distributed as a Debian package: `container-packaging-tools`

**Installed Files**:
```
/usr/bin/
└── generate-container-packages        # Main executable

/usr/share/container-packaging-tools/
├── templates/                          # Jinja2 templates
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
│   ├── systemd/
│   │   └── service.j2                  # systemd service template
│   └── appstream/
│       └── metainfo.xml.j2             # AppStream metadata template
└── schemas/
    ├── metadata.py                     # Pydantic model for metadata.yaml
    └── config.py                       # Pydantic model for config.yml

/usr/share/doc/container-packaging-tools/
├── README.md
├── EXAMPLES.md
├── copyright
└── changelog.gz
```

**Dependencies**:
```
Depends: python3 (>= 3.11),
         python3-jinja2,
         python3-pydantic (>= 2.0),
         python3-yaml,
         dpkg-dev,
         debhelper (>= 12)
```

## Input Format Specification

The tool expects a directory containing these files:

### Required Files

1. **metadata.yaml** - Package metadata and configuration
2. **docker-compose.yml** - Docker Compose configuration
3. **config.yml** - User-configurable parameters

### Optional Files

4. **icon.svg** or **icon.png** - Application icon (SVG preferred, or PNG 64x64+, square)
5. **screenshot*.png** - Screenshots
6. **README.md** - Additional documentation

### Input Directory Structure

```
app-definition/
├── metadata.yaml          # Required
├── docker-compose.yml     # Required
├── config.yml             # Required
├── icon.svg               # Optional (or icon.png)
├── screenshot1.png        # Optional
└── README.md              # Optional
```

### metadata.yaml Format

The metadata file uses YAML format for human readability (comments, no quotes required, etc.). The structure is validated using a Pydantic model:

```python
from pydantic import BaseModel, Field, HttpUrl, EmailStr, field_validator
from typing import Optional, List, Dict, Literal

class WebUI(BaseModel):
    enabled: bool
    path: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Optional[str] = Field(None, pattern="^(http|https)$")

class PackageMetadata(BaseModel):
    """Pydantic model for package metadata."""

    # Required fields
    name: str = Field(min_length=1, description="Human-readable application name")
    package_name: str = Field(pattern=r"^[a-z0-9][a-z0-9+.-]+$",
                              description="Debian package name (must end with -container)")
    version: str = Field(min_length=1,
                        description="Package version (flexible: semver, date-based, CalVer, etc.)")
    description: str = Field(max_length=80, description="Short description for package lists")
    maintainer: str = Field(pattern=r"^[^<>]+<[^@]+@[^>]+>$",
                           description="Package maintainer (Name <email>)")
    license: str = Field(description="SPDX license identifier")
    tags: List[str] = Field(min_length=1, description="Debian tags (debtags)")
    debian_section: Literal["admin", "comm", "database", "devel", "doc", "editors",
                           "games", "gnome", "graphics", "kde", "mail", "net", "news",
                           "science", "sound", "text", "utils", "web", "x11"]
    architecture: Literal["all", "amd64", "arm64", "armhf", "i386"]

    # Optional fields
    upstream_version: Optional[str] = None
    long_description: Optional[str] = None
    homepage: Optional[HttpUrl] = None
    icon: Optional[str] = None
    screenshots: Optional[List[str]] = None
    depends: Optional[List[str]] = None
    recommends: Optional[List[str]] = None
    suggests: Optional[List[str]] = None
    web_ui: Optional[WebUI] = None
    appstream_categories: Optional[List[str]] = None
    default_config: Optional[Dict[str, str]] = None

    @field_validator('package_name')
    def package_name_must_end_with_container(cls, v):
        if not v.endswith('-container'):
            raise ValueError('package_name must end with -container')
        return v

    @field_validator('tags')
    def tags_must_include_container_app(cls, v):
        if 'role::container-app' not in v:
            raise ValueError('tags must include role::container-app')
        return v
```

### docker-compose.yml Requirements

- Must be valid Docker Compose v3.8+ format
- Should use environment variable substitution: `${VAR:-default}`
- Should use bind mounts for persistence (not named volumes)
- Must NOT include restart policies (systemd manages lifecycle)
- Should set meaningful `container_name`

### config.yml Schema

```yaml
# Schema definition for config.yml
version: "1.0"
type: object
required:
  - version
  - groups
properties:
  version:
    type: string
    pattern: "^[0-9]+\\.[0-9]+$"
  groups:
    type: array
    items:
      type: object
      required:
        - id
        - label
        - fields
      properties:
        id:
          type: string
          pattern: "^[a-z][a-z0-9_]*$"
        label:
          type: string
        description:
          type: string
        fields:
          type: array
          items:
            type: object
            required:
              - id
              - label
              - type
            properties:
              id:
                type: string
                pattern: "^[A-Z][A-Z0-9_]*$"  # Environment variable naming
              label:
                type: string
              type:
                type: string
                enum: ["string", "integer", "boolean", "enum", "path", "password"]
              default:
                # Type varies based on field type
              min:
                type: integer
              max:
                type: integer
              options:
                type: array
                items:
                  type: object
                  properties:
                    value:
                      type: string
                    label:
                      type: string
              required:
                type: boolean
              description:
                type: string
```

## Output Format Specification

The tool generates a standard Debian source package structure:

### Generated Directory Structure

```
output-directory/
├── <package-name>-<version>/
│   ├── debian/
│   │   ├── control              # Package metadata
│   │   ├── rules                # Build rules
│   │   ├── install              # File installation list
│   │   ├── postinst             # Post-installation script
│   │   ├── prerm                # Pre-removal script
│   │   ├── postrm               # Post-removal script
│   │   ├── changelog            # Debian changelog
│   │   ├── copyright            # Copyright and license
│   │   ├── compat               # Debhelper compatibility level
│   │   └── <package>.service    # systemd service file
│   ├── docker-compose.yml       # Copied from input
│   ├── config.yml               # Copied from input
│   ├── metadata.yaml            # Copied from input
│   ├── icon.(svg|png)           # Copied from input (if present)
│   └── env.template            # Generated from default_config
└── <package-name>_<version>_<arch>.deb  # Built package (after dpkg-buildpackage)
```

### Generated debian/control

```
Source: <package-name>
Section: <debian_section>
Priority: optional
Maintainer: <maintainer>
Build-Depends: debhelper (>= 12)
Standards-Version: 4.5.0
Homepage: <homepage>

Package: <package-name>
Architecture: <architecture>
Depends: ${misc:Depends}, <depends>
Recommends: <recommends>
Suggests: <suggests>
Description: <description>
 <long_description (formatted for Debian control)>
Tag: <tags (comma-separated)>
```

### Generated debian/rules

```makefile
#!/usr/bin/make -f
%:
	dh $@

override_dh_auto_install:
	# Install application files
	install -D -m 644 docker-compose.yml \
		debian/<package>/var/lib/container-apps/<package>/docker-compose.yml
	install -D -m 644 metadata.yaml \
		debian/<package>/var/lib/container-apps/<package>/metadata.yaml
	install -D -m 644 config.yml \
		debian/<package>/var/lib/container-apps/<package>/config.yml
	install -D -m 644 env.template \
		debian/<package>/var/lib/container-apps/<package>/env.template

	# Install icon if present (SVG or PNG)
	if [ -f icon.svg ]; then \
		install -D -m 644 icon.svg \
			debian/<package>/usr/share/pixmaps/<package>.svg; \
	elif [ -f icon.png ]; then \
		install -D -m 644 icon.png \
			debian/<package>/usr/share/pixmaps/<package>.png; \
	fi

	# Install systemd service
	install -D -m 644 debian/<package>.service \
		debian/<package>/etc/systemd/system/<package>.service
```

### Generated debian/postinst

```bash
#!/bin/sh
set -e

case "$1" in
    configure)
        # Always update env.defaults from template (contains system defaults)
        cp /var/lib/container-apps/<package>/env.template \
           /etc/container-apps/<package>/env.defaults

        # Create empty env for user overrides if it doesn't exist
        if [ ! -f /etc/container-apps/<package>/env ]; then
            echo "# User environment overrides" > /etc/container-apps/<package>/env
        fi

        # Reload systemd
        systemctl daemon-reload

        # Enable and start service
        systemctl enable <package>.service
        systemctl start <package>.service || true
        ;;
esac

#DEBHELPER#

exit 0
```

### Generated debian/prerm

```bash
#!/bin/sh
set -e

case "$1" in
    remove|deconfigure)
        # Stop service
        systemctl stop <package>.service || true
        systemctl disable <package>.service || true
        ;;
esac

#DEBHELPER#

exit 0
```

### Generated debian/postrm

```bash
#!/bin/sh
set -e

case "$1" in
    purge)
        # Remove configuration (but not user data)
        rm -rf /etc/container-apps/<package>/

        # Remove systemd service
        rm -f /etc/systemd/system/<package>.service
        systemctl daemon-reload
        ;;

    remove)
        # Remove application files (but keep config)
        rm -rf /var/lib/container-apps/<package>/
        ;;
esac

#DEBHELPER#

exit 0
```

## Template System

### Jinja2 Templates

All generated files use Jinja2 templates for flexibility and maintainability.

**Template Location**: `/usr/share/container-packaging-tools/templates/`

**Template Context** (variables passed to templates):
```python
{
    'package': {
        'name': metadata['package_name'],
        'version': metadata['version'],
        'architecture': metadata['architecture'],
        'section': metadata['debian_section'],
        'description': metadata['description'],
        'long_description': metadata.get('long_description', ''),
        'homepage': metadata.get('homepage', ''),
        'maintainer': metadata['maintainer'],
        'license': metadata['license'],
        'tags': ', '.join(metadata['tags']),
        'depends': ', '.join(metadata.get('depends', [])),
        'recommends': ', '.join(metadata.get('recommends', [])),
        'suggests': ', '.join(metadata.get('suggests', []))
    },
    'service': {
        'name': f"{metadata['package_name']}.service",
        'description': f"{metadata['name']} Container",
        'working_directory': f"/var/lib/container-apps/{metadata['package_name']}",
        'env_file': f"/etc/container-apps/{metadata['package_name']}/env"
    },
    'paths': {
        'lib': f"/var/lib/container-apps/{metadata['package_name']}",
        'etc': f"/etc/container-apps/{metadata['package_name']}",
        'systemd': '/etc/systemd/system'
    },
    'web_ui': metadata.get('web_ui', {}),
    'default_config': metadata.get('default_config', {}),
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'tool_version': VERSION
}
```

### Example Template: debian/control.j2

```jinja2
Source: {{ package.name }}
Section: {{ package.section }}
Priority: optional
Maintainer: {{ package.maintainer }}
Build-Depends: debhelper (>= 12)
Standards-Version: 4.5.0
{% if package.homepage %}
Homepage: {{ package.homepage }}
{% endif %}

Package: {{ package.name }}
Architecture: {{ package.architecture }}
Depends: ${misc:Depends}{% if package.depends %}, {{ package.depends }}{% endif %}

{% if package.recommends %}
Recommends: {{ package.recommends }}
{% endif %}
{% if package.suggests %}
Suggests: {{ package.suggests }}
{% endif %}
Description: {{ package.description }}
{% for line in package.long_description.split('\n') %}
 {{ line }}
{% endfor %}
Tag: {{ package.tags }}
```

### Example Template: systemd/service.j2

```jinja2
[Unit]
Description={{ service.description }}
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={{ service.working_directory }}
EnvironmentFile={{ service.env_file }}
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Note**: Type=oneshot with RemainAfterExit=yes ensures systemd tracks the service state. The restart policy is handled by systemd (automatic restart on failure), not by Docker Compose.

## Path Conventions

All generated packages follow these standard paths:

### Application Data Directory
**Path**: `/var/lib/container-apps/<package-name>/`
**Purpose**: Application files (compose, metadata, templates)
**Permissions**: `root:root`, `0644` (files), `0755` (directories)

**Contents**:
- `docker-compose.yml` - Docker Compose configuration
- `metadata.yaml` - Application metadata (for UI consumption)
- `config.yml` - Configuration schema (field definitions for UI)
- `env.template` - Environment variable template

### Configuration Directory
**Path**: `/etc/container-apps/<package-name>/`
**Purpose**: User-editable configuration
**Permissions**: `root:root`, `0644` (files), `0755` (directories)

**Contents**:
- `env.defaults` - Default environment values (updated on every install/upgrade)
- `env` - User overrides (created once on first install, never overwritten)

### systemd Service
**Path**: `/etc/systemd/system/<package-name>.service`
**Purpose**: systemd service unit
**Permissions**: `root:root`, `0644`

### Store Definitions (for store packages)
**Path**: `/etc/container-apps/stores/`
**Purpose**: Store configuration files
**Permissions**: `root:root`, `0644` (files), `0755` (directories)

### Store Branding (for store packages)
**Path**: `/usr/share/container-stores/<store-id>/`
**Purpose**: Store icons, banners, assets
**Permissions**: `root:root`, `0644` (files), `0755` (directories)

### Icon
**Path**: `/usr/share/pixmaps/<package-name>.(svg|png)`
**Purpose**: Application icon for Cockpit/UI (SVG preferred, PNG supported)
**Permissions**: `root:root`, `0644`
**Note**: `/usr/share/pixmaps` is appropriate for Cockpit modules and system utilities

### AppStream Metadata
**Path**: `/usr/share/metainfo/<package-name>.metainfo.xml`
**Purpose**: Application metadata for software centers (GNOME Software, KDE Discover)
**Permissions**: `root:root`, `0644`
**Note**: Enables discovery in Linux software centers beyond Cockpit

### Documentation
**Path**: `/usr/share/doc/<package-name>/`
**Purpose**: Package documentation
**Permissions**: `root:root`, `0644` (files), `0755` (directories)

**Contents**:
- `copyright` - Copyright and license information
- `changelog.gz` - Debian changelog (compressed)

## Validation System

### Pre-Build Validation

The tool validates all input files before generating packages:

1. **JSON Schema Validation**:
   - Validate `metadata.yaml` against schema
   - Check required fields present
   - Verify format constraints (package name, version, email, etc.)

2. **Docker Compose Validation**:
   - Parse YAML syntax
   - Verify Docker Compose schema (v3.8+)
   - Check for environment variable substitution
   - Warn if restart policies are present (systemd manages lifecycle)
   - Recommend bind mounts over named volumes

3. **Config Validation**:
   - Parse YAML syntax
   - Validate against config schema
   - Check field IDs match environment variable naming

4. **File Checks**:
   - Verify required files present
   - Check file permissions
   - Validate image formats (SVG or PNG for icons, PNG for screenshots)

5. **Cross-Validation**:
   - Ensure config.yml field IDs present in default_config or docker-compose.yml
   - Verify package name ends with `-container`
   - Check tags include `role::container-app`

### Validation Modes

```bash
# Validate only (no package generation)
generate-container-packages --validate /path/to/app/

# Strict mode (fails on warnings)
generate-container-packages --strict /path/to/app/

# Dry run (generate files but don't build package)
generate-container-packages --dry-run /path/to/app/
```

### Error Reporting

Validation errors include:
- File path
- Line number (for YAML/JSON syntax errors)
- Field name (for schema violations)
- Clear error message
- Suggested fix (when possible)

**Example Error Output**:
```
ERROR: Validation failed for metadata.yaml
  Line 12: Field 'package_name' must end with '-container'
    Current value: 'signalk-server'
    Suggested fix: 'signalk-server-container'

ERROR: docker-compose.yml missing required environment variable
  Line 8: Environment variable 'HTTP_PORT' used but not in default_config
  Add to metadata.yaml: "default_config": {"HTTP_PORT": "3000"}
```

## Build Process

### Build Workflow

1. **Validation**: Validate all input files
2. **Preparation**: Create temporary build directory
3. **Rendering**: Render all templates with metadata context
4. **File Copying**: Copy input files to build directory
5. **Package Building**: Run `dpkg-buildpackage`
6. **Cleanup**: Remove temporary files (unless `--keep-temp` specified)

### Build Command

```bash
# Default build (binary package only)
dpkg-buildpackage -b -us -uc

# Options used:
#   -b: binary only (no source package)
#   -us: do not sign source package
#   -uc: do not sign .changes file
```

### Build Output

```
<output-directory>/
├── <package>_<version>_<arch>.deb          # Binary package
├── <package>_<version>_<arch>.buildinfo    # Build information
└── <package>_<version>_<arch>.changes      # Changes file
```

## Error Handling

### Error Categories

1. **Validation Errors** (Exit 1):
   - Invalid JSON/YAML syntax
   - Schema violations
   - Missing required files
   - Format errors

2. **Template Errors** (Exit 2):
   - Template rendering failure
   - Missing template variables
   - Template syntax errors

3. **Build Errors** (Exit 3):
   - `dpkg-buildpackage` failure
   - File permission errors
   - Disk space issues

4. **Dependency Errors** (Exit 4):
   - Missing system dependencies
   - Python module import errors

### Logging Levels

```bash
# Normal output (errors and warnings)
generate-container-packages /path/to/app/

# Verbose (includes info messages)
generate-container-packages --verbose /path/to/app/

# Debug (all messages including template rendering)
generate-container-packages --debug /path/to/app/

# Quiet (errors only)
generate-container-packages --quiet /path/to/app/
```

## Testing Strategy

### Unit Tests

Test individual components:
- Schema validation logic
- Template rendering
- Path generation
- File copying
- Error message formatting

### Integration Tests

Test complete workflow:
- Valid app definition → successful package
- Invalid metadata → validation error
- Missing files → clear error message
- Generated package installs correctly
- Service starts and stops properly

### Test Fixtures

```
tests/
├── fixtures/
│   ├── valid/
│   │   ├── simple-app/          # Minimal valid app
│   │   └── complex-app/         # Full-featured app
│   └── invalid/
│       ├── missing-metadata/    # Missing metadata.yaml
│       ├── bad-package-name/    # Invalid package name
│       └── schema-violation/    # Schema validation failure
├── test_validation.py
├── test_templates.py
├── test_generation.py
└── test_integration.py
```

### CI/CD Testing

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: sudo apt install python3-jinja2 python3-pydantic python3-yaml dpkg-dev debhelper
      - name: Run unit tests
        run: python3 -m pytest tests/
      - name: Test package generation
        run: |
          ./generate-container-packages tests/fixtures/valid/simple-app/
          sudo dpkg -i *.deb
          systemctl status simple-app-container
```

## Command Implementation

### Python Structure

```python
# /usr/bin/generate-container-packages
#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError
import yaml

from schemas.metadata import PackageMetadata
from schemas.config import ConfigSchema

VERSION = "1.0.0"
TEMPLATES_DIR = Path("/usr/share/container-packaging-tools/templates")

def main():
    parser = argparse.ArgumentParser(
        description="Generate Debian packages from container app definitions"
    )
    parser.add_argument("input_dir", help="App definition directory")
    parser.add_argument("--output", "-o", help="Output directory", default=".")
    parser.add_argument("--validate", action="store_true", help="Validate only")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args = parser.parse_args()

    try:
        # Load and validate metadata
        metadata = load_and_validate_metadata(args.input_dir)

        if args.validate:
            print("Validation successful!")
            return 0

        # Generate package
        generate_package(metadata, args.input_dir, args.output)
        print(f"Package generated successfully: {metadata.package_name}")
        return 0

    except ValidationError as e:
        print(f"ERROR: Validation failed:\n{e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

def load_and_validate_metadata(input_dir: Path) -> PackageMetadata:
    """Load and validate metadata.yaml using Pydantic"""
    metadata_file = Path(input_dir) / "metadata.yaml"
    with open(metadata_file) as f:
        data = yaml.safe_load(f)
    # Pydantic validates during model construction
    return PackageMetadata.model_validate(data)

def generate_package(metadata: Dict[str, Any], input_dir: Path, output_dir: Path):
    """Generate Debian package from app definition"""
    # Implementation...
    pass

if __name__ == "__main__":
    sys.exit(main())
```

## Future Enhancements

### Phase 1 (Current)
- Basic package generation
- Schema validation using Pydantic
- Template system
- systemd service generation
- AppStream metadata generation

### Phase 2
- Multi-architecture support
- Automated testing in generated packages
- Container image validation

### Phase 3
- GUI configuration wizard
- Package signing support
- Repository publishing integration
- Conversion tools (import from CasaOS/Runtipi)

### Phase 4
- Template customization system
- Plugin architecture
- Alternative container runtimes (podman, containerd)
- OCI bundle support

## References

### Internal Documentation
- [META-PLANNING.md](../../META-PLANNING.md) - Overall project planning
- [halos-marine-containers/docs/DESIGN.md](../../halos-marine-containers/docs/DESIGN.md) - Container definitions
- [cockpit-apt/docs/CONTAINER_STORE_DESIGN.md](../../cockpit-apt/docs/CONTAINER_STORE_DESIGN.md) - UI design

### External References
- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/)
- [Debian New Maintainers' Guide](https://www.debian.org/doc/manuals/maint-guide/)
- [debhelper Documentation](https://manpages.debian.org/testing/debhelper/debhelper.7.en.html)
- [systemd Service Units](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Docker Compose Specification](https://docs.docker.com/compose/compose-file/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
