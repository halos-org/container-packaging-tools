# CasaOS Converter Mapping Configuration

This directory contains YAML configuration files that control how the CasaOS converter transforms CasaOS application definitions into HaLOS container store format.

## Overview

The converter uses three types of mapping files to handle the differences between CasaOS and HaLOS formats:

1. **categories.yaml** - Maps CasaOS category names to Debian package sections
2. **field_types.yaml** - Infers HaLOS config.yml field types from environment variables
3. **paths.yaml** - Transforms CasaOS volume paths to HaLOS conventions

These mappings are externalized to YAML files to enable updates without code changes.

## Conversion Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                   CasaOS Application Input                        │
│              (docker-compose.yml + x-casaos metadata)             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│  PHASE 1: PARSE                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ • Read docker-compose.yml                                  ││
│  │ • Extract x-casaos metadata                                ││
│  │ • Validate CasaOS schema                                   ││
│  │ • Create CasaOSApp model                                   ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│  PHASE 2: TRANSFORM                                             │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ • Map category using categories.yaml                       ││
│  │ • Infer field types using field_types.yaml                 ││
│  │ • Transform paths using paths.yaml                         ││
│  │ • Generate package name (casaos-{app}-container)           ││
│  │ • Organize fields into config groups                       ││
│  │ • Apply validation rules                                   ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│  PHASE 3: GENERATE                                              │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ • Create metadata.yaml (package info, tags, maintainer)    ││
│  │ • Create config.yml (field groups and types)               ││
│  │ • Create docker-compose.yml (clean container definitions)  ││
│  │ • Download and validate assets (icons, screenshots)        ││
│  │ • Track conversion provenance                              ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      HaLOS Package Output                         │
│      metadata.yaml + config.yml + docker-compose.yml + assets    │
└──────────────────────────────────────────────────────────────────┘
```

**Mapping Files Role**: The YAML configuration files in this directory control the TRANSFORM phase, providing the rules and patterns that guide how CasaOS structures are converted to HaLOS format.

## File Formats

### categories.yaml

Maps human-friendly CasaOS category names to standardized Debian section names.

**Structure:**
```yaml
mappings:
  <CasaOS-Category>: <debian-section>
default: <fallback-section>
```

**Example:**
```yaml
mappings:
  Entertainment: video
  Media: video
  Developer: devel
  Productivity: misc
default: misc
```

**Usage:**
- When converting a CasaOS app, the converter looks up its category in the `mappings` dict
- If found, uses the corresponding Debian section
- If not found, uses the `default` section and logs a warning
- Debian sections must match the enum in `schemas/metadata.py`

**Customization:**
Add new mappings or override existing ones by editing this file. No code changes required.

### field_types.yaml

Defines patterns for inferring appropriate HaLOS field types from CasaOS environment variable names and metadata.

**Structure:**
```yaml
patterns:
  - pattern: <regex-pattern>
    type: <field-type>
    validation: {optional rules}
    group: <optional-group-name>

defaults:
  <casaos-type>: <field-type>
  fallback: <default-type>

groups:
  <group-id>: <group-label>
```

**Field Types:**
- `string` - Text input
- `integer` - Numeric input with optional min/max
- `boolean` - True/false toggle
- `enum` - Selection from predefined options
- `path` - File/directory path
- `password` - Masked text input

**Example:**
```yaml
patterns:
  - pattern: ".*PORT$"
    type: integer
    validation:
      min: 1024
      max: 65535
    group: network

  - pattern: ".*PASSWORD$"
    type: password
    group: authentication

defaults:
  number: integer
  text: string
  fallback: string
```

**Pattern Matching:**
- Patterns are evaluated in order from top to bottom
- First matching pattern wins
- Patterns use Python `re` module regex syntax
- Case-sensitive matching on environment variable names

**Groups:**
- Group hints suggest how to organize related fields
- Converter may override based on semantic analysis
- Group IDs must use `lowercase_snake_case`
- Group labels are human-readable display names

**Validation:**
- `min` and `max` apply to integer and string types
- Additional validation rules may be added in future versions

**Customization:**
- Add patterns for app-specific environment variables
- Adjust validation ranges as needed
- Patterns at the top of the file have higher priority

### paths.yaml

Transforms CasaOS volume mount paths to HaLOS path conventions.

**Structure:**
```yaml
transforms:
  - from: <casaos-path-pattern>
    to: <halos-path-pattern>
    description: <explanation>

special_cases:
  preserve: [<paths-to-preserve>]
  configurable:
    - pattern: <path-regex>
      field_name: <env-var-name>
      description: <help-text>

default:
  action: <default-behavior>
```

**Example:**
```yaml
transforms:
  - from: "/DATA/AppData/{app}/"
    to: "${CONTAINER_DATA_ROOT}/"
    description: "CasaOS AppData to HaLOS data root"

  - from: "/media"
    to: "/media"
    description: "Preserve media directory"

special_cases:
  preserve:
    - "/etc"
    - "/var"
    - "/usr"

  configurable:
    - pattern: "^/media/"
      field_name: "MEDIA_PATH"
      description: "Path to media directory"
```

**Variables:**
- `{app}` or `{app_id}` - Application identifier (lowercase)
- `{service}` - Service name for multi-service apps
- `${CONTAINER_DATA_ROOT}` - HaLOS data root environment variable

**Transform Processing:**
1. Check if path matches `preserve` list → keep unchanged
2. Apply first matching transform rule
3. Check if path matches `configurable` pattern → extract as config field
4. Apply `default` action if no matches

**Configurable Paths:**
- Some paths (like `/media`, `/downloads`) should be user-configurable
- The converter extracts these as fields in `config.yml`
- Users can customize these paths during package configuration

**Customization:**
- Add transforms for app-specific path conventions
- Mark additional paths as configurable
- Preserve system paths that should never be transformed

## Usage

The converter loads these files at runtime. To customize conversion behavior:

1. Edit the appropriate YAML file
2. Re-run the converter
3. No code changes or recompilation needed

**Location in installed package:**
- Development: `mappings/casaos/`
- Installed: `/usr/share/container-packaging-tools/mappings/casaos/`
- User overrides: `/etc/container-packaging-tools/mappings/casaos/` (future)

## Validation

All YAML files must be valid YAML format. The converter will fail with clear error messages if:
- YAML syntax is invalid
- Required keys are missing
- Values don't match expected types

Run converter with `--validate-mappings` to check mapping files without converting apps (future feature).

## Contributing

When adding new mappings:

1. **Categories**: Research the appropriate Debian section
   - Reference: https://www.debian.org/doc/debian-policy/ch-archive.html
   - Ensure section exists in `schemas/metadata.py`

2. **Field Types**: Consider common patterns
   - Use specific patterns (e.g., `.*_PORT$`) before generic ones
   - Add validation rules for safety (e.g., port ranges)
   - Choose appropriate groups for UI organization

3. **Paths**: Understand path semantics
   - Preserve system paths (`/etc`, `/var`, etc.)
   - Transform app-specific paths to HaLOS conventions
   - Mark user data paths as configurable

4. **Testing**: Add test cases
   - Verify mappings work for real CasaOS apps
   - Test edge cases and uncommon patterns
   - Ensure generated packages are valid

## References

- [CasaOS App Store](https://github.com/IceWhaleTech/CasaOS-AppStore)
- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/)
- [HaLOS Container Store Format](../../docs/CONVERTER_SPEC.md)
- [Converter Architecture](../../docs/CONVERTER_ARCHITECTURE.md)
