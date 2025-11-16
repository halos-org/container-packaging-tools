# Container Packaging Tools

Command-line tools for converting container application definitions into Debian packages.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

`container-packaging-tools` automates the creation of Debian packages from simple container app definitions. It transforms Docker Compose configurations, metadata, and configuration schemas into production-ready Debian packages with systemd integration, eliminating the need to understand Debian packaging internals.

### Key Features

- **Automated Package Generation**: Convert app definitions to complete Debian packages
- **Template-Based**: Uses Jinja2 templates for all packaging files
- **Comprehensive Validation**: Validates metadata, Docker Compose, and configuration schemas
- **systemd Integration**: Automatically generates systemd service units
- **Cockpit Ready**: Generates web UI metadata for Cockpit integration
- **AppStream Support**: Creates AppStream metadata for software centers
- **Standards Compliant**: Follows Debian packaging standards and best practices

### Use Cases

- Package marine applications (Signal K, OpenCPN, AvNav) for HaLOS
- Create container-based Debian packages for any Docker application
- Standardize packaging across multiple applications
- Automate CI/CD pipelines for container app deployment

## Requirements

- **Debian 13 (Trixie) or newer** - Required for Python 3.11+ and Pydantic v2.0+
- **Raspberry Pi OS** (Trixie-based) is also supported
- **Ubuntu 24.04+** or other Debian-based distributions with compatible package versions

**Note:** Older distributions like Ubuntu 22.04 or Debian 12 (Bookworm) do not have Pydantic v2.0+ available in their repositories.

## Agentic Coding Setup (Claude Code, GitHub Copilot, etc.)

For development with AI assistants, use the halos-distro workspace for full context:

```bash
# Clone the workspace
git clone https://github.com/hatlabs/halos-distro.git
cd halos-distro

# Get all sub-repositories including container-packaging-tools
./run repos:clone

# Work from workspace root for AI-assisted development
# Claude Code gets full context across all repos
```

See `halos-distro/docs/` for development workflows:
- `HUMAN_DEVELOPMENT_GUIDANCE.md` - Quick start guide
- `IMPLEMENTATION_CHECKLIST.md` - Development checklist
- `DEVELOPMENT_WORKFLOW.md` - Detailed workflows

## Installation

```bash
# From APT repository (when available)
sudo apt install container-packaging-tools

# Or build from source
git clone https://github.com/hatlabs/container-packaging-tools.git
cd container-packaging-tools
./run build
sudo dpkg -i ../container-packaging-tools_*.deb
```

## Quick Start

### 1. Create Your App Definition

Create a directory with three required files:

```bash
mkdir my-app
cd my-app
```

**metadata.yaml** - Package metadata:
```yaml
name: My Web Application
package_name: my-app-container
version: 1.0.0
upstream_version: 1.0.0
description: A simple web application
long_description: |
  This is my container application packaged as a Debian package.
homepage: https://example.com/my-app
maintainer: Your Name <your.email@example.com>
license: MIT
tags:
  - role::container-app
  - implemented-in::docker
debian_section: web
architecture: all

web_ui:
  enabled: true
  path: /
  port: 8080
  protocol: http

default_config:
  APP_PORT: "8080"
  LOG_LEVEL: "info"
```

**docker-compose.yml** - Container definition:
```yaml
version: '3.8'

services:
  app:
    image: nginx:alpine
    container_name: my-app
    ports:
      - "${APP_PORT:-8080}:80"
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
    volumes:
      - /var/lib/container-apps/my-app-container/data:/usr/share/nginx/html:rw
    restart: "no"
```

**config.yml** - Configuration schema:
```yaml
version: "1.0"
groups:
  - id: general
    label: General Settings
    description: Basic application configuration
    fields:
      - id: APP_PORT
        label: Application Port
        type: integer
        default: 8080
        required: true
        min: 1024
        max: 65535
        description: Port for the web interface

      - id: LOG_LEVEL
        label: Log Level
        type: enum
        default: info
        required: false
        options: [debug, info, warning, error]
        description: Logging verbosity
```

### 2. Generate and Build the Package

```bash
# Generate Debian package structure
generate-container-packages my-app/ build/

# Build the Debian package
cd build/my-app-container
dpkg-buildpackage -us -uc

# Install the package
sudo dpkg -i ../my-app-container_1.0.0_all.deb
```

### 3. Manage Your Application

```bash
# Start the service
sudo systemctl start my-app-container

# Check status
sudo systemctl status my-app-container

# View logs
sudo journalctl -u my-app-container -f

# Access the web interface
curl http://localhost:8080/

# Configure the application
sudo nano /etc/container-apps/my-app-container/env
sudo systemctl restart my-app-container
```

For more examples and detailed documentation, see [EXAMPLES.md](EXAMPLES.md).

## Documentation

- **[EXAMPLES.md](EXAMPLES.md)** - Comprehensive examples and usage patterns
- **[docs/SPEC.md](docs/SPEC.md)** - Technical specification and requirements
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[docs/DESIGN.md](docs/DESIGN.md)** - High-level design documentation

## Input Format

Each application definition directory must contain:

| File | Required | Description |
|------|----------|-------------|
| `metadata.yaml` | Yes | Package metadata (name, version, description, etc.) |
| `docker-compose.yml` | Yes | Docker Compose configuration |
| `config.yml` | Yes | User-configurable parameters schema |
| `icon.png` or `icon.svg` | No | Application icon |
| `screenshot*.png` | No | Screenshots for AppStream metadata |

## Output Structure

The tool generates a complete Debian package structure:

```
<package-name>/
├── debian/
│   ├── control           # Package metadata
│   ├── rules             # Build rules
│   ├── install           # File installation
│   ├── postinst          # Post-installation script
│   ├── prerm             # Pre-removal script
│   ├── postrm            # Post-removal script
│   ├── changelog         # Package changelog
│   ├── copyright         # License information
│   └── compat            # Debhelper compatibility
├── systemd/
│   └── service           # systemd service unit
├── appstream/
│   └── metainfo.xml      # AppStream metadata
└── files/
    ├── docker-compose.yml
    ├── config.yml
    └── env.template       # Environment file template
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/hatlabs/container-packaging-tools.git
cd container-packaging-tools

# Build the development Docker container
./run docker:build

# Run tests
./run test

# Run linter
./run lint

# Check formatting
./run format:check

# Run type checker
./run typecheck
```

### Testing

All development happens in Docker containers to ensure consistent Debian Trixie environment:

```bash
# Run all tests
./run test

# Run specific test categories
./run test:unit                    # Unit tests only
./run test:integration             # Integration tests only

# Run with coverage
./run test:coverage                # Requires 80% coverage

# Open interactive shell
./run docker:shell
```

### Code Quality

Before submitting changes, ensure all checks pass:

```bash
# Run all quality checks
./run check

# Individual checks
./run lint              # Ruff linter
./run format            # Code formatting
./run typecheck         # Type checking with ty
```

### Local Development (Non-Docker)

For faster iteration on Debian/Ubuntu systems:

```bash
# Install build dependencies
sudo apt install dpkg-dev debhelper dh-python python3-all

# Install Python dependencies
uv sync --dev

# Run tests locally
uv run pytest

# Note: Some tests require dpkg-buildpackage and will fail on non-Debian systems
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run all quality checks (`./run check`)
5. Run all tests (`./run test`)
6. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/)
7. Push to your branch
8. Open a Pull Request

### Development Workflow

- All commits must follow conventional commit format
- PRs must have passing CI checks before merge
- Code coverage must be maintained at 80% or higher
- All code must pass linting, formatting, and type checking

## Related Projects

- **[halos-marine-containers](https://github.com/hatlabs/halos-marine-containers)** - Marine application definitions using this tool
- **[halos-distro](https://github.com/hatlabs/halos-distro)** - HaLOS workspace and distribution
- **[cockpit-apt](https://github.com/hatlabs/cockpit-apt)** - APT package manager for Cockpit
- **[halos-pi-gen](https://github.com/hatlabs/halos-pi-gen)** - HaLOS image builder

## License

MIT License - see [debian/copyright](debian/copyright) for full details.

## Support

- **Issues**: [GitHub Issues](https://github.com/hatlabs/container-packaging-tools/issues)
- **Documentation**: [EXAMPLES.md](EXAMPLES.md) and [docs/](docs/)
- **HaLOS Project**: [hatlabs.github.io/halos](https://hatlabs.github.io/halos)
