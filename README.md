# Container Packaging Tools

Tooling for generating Debian packages from container application definitions.

## What is This?

`container-packaging-tools` is a Debian package that provides command-line tools to convert simple container app definitions into full-fledged Debian packages. It eliminates the need for package maintainers to understand Debian packaging internals.

## Installation

```bash
sudo apt install container-packaging-tools
```

## Usage

```bash
# Generate packages from app definitions
generate-container-packages <input-dir> <output-dir>

# Example
generate-container-packages apps/ build/

# Output: build/signalk-server-container/, build/opencpn-container/, etc.
```

## Input Format

Each app directory should contain:
- `docker-compose.yml` - Container orchestration
- `config.yml` - Application configuration template
- `metadata.json` - Package metadata (name, description, tags, etc.)
- `icon.png` - Application icon (optional)

See [docs/DESIGN.md](docs/DESIGN.md) for complete format specification.

## Output

Generates Debian package directories ready for building:
- `debian/control` - Package metadata
- `debian/rules` - Build rules
- `debian/install` - File installation mapping
- `debian/postinst` - Post-installation script
- `systemd service file` - Service unit for systemd

## Features

- **Template-based**: Uses Jinja2 templates for Debian packaging files
- **Validation**: JSON schemas validate input format
- **Consistent**: Ensures all packages follow same structure
- **Extensible**: Easy to add new templates or schemas

## Development

**Requirements**:
- Python 3.11+
- See `requirements.txt` for dependencies

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## Related Repositories

- [halos-marine-containers](https://github.com/hatlabs/halos-marine-containers) - Uses this tool to build marine app packages
- [halos-distro](https://github.com/hatlabs/halos-distro) - HaLOS workspace and planning
- [cockpit-apt](https://github.com/hatlabs/cockpit-apt) - Displays and installs generated packages

## License

TBD
