# Container Packaging Tools - Examples

This guide provides comprehensive examples for using `container-packaging-tools` to convert container application definitions into Debian packages.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Minimal Example](#minimal-example)
3. [Full-Featured Example](#full-featured-example)
4. [Common Patterns](#common-patterns)
   - [Pattern 6: Non-Root Container with Volume Permissions](#pattern-6-non-root-container-with-volume-permissions)
5. [Field Reference](#field-reference)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

## Getting Started

### Directory Structure

Each application definition must be in its own directory with the following structure:

```
my-app/
├── metadata.yaml          # Required: Package metadata
├── docker-compose.yml     # Required: Container orchestration
├── config.yml             # Required: User configuration schema
├── icon.png               # Optional: Application icon (PNG or SVG)
├── screenshot1.png        # Optional: Screenshots for AppStream
└── screenshot2.png
```

### Basic Workflow

```bash
# 1. Create your app directory with required files
mkdir my-app
cd my-app
# ... create metadata.yaml, docker-compose.yml, config.yml ...

# 2. Generate the Debian package structure
generate-container-packages my-app/ output/

# 3. Build the package
cd output/my-app-container
dpkg-buildpackage -us -uc

# 4. Install the package
sudo dpkg -i ../my-app-container_*.deb
```

## Minimal Example

This example shows the absolute minimum required to create a working package.

### Directory: simple-app/

#### metadata.yaml

```yaml
# Simple App - Minimal valid container app definition
name: Simple Web Server
package_name: simple-webserver-container
version: 1.0.0
upstream_version: 1.0.0
description: A simple web server for testing
long_description: |
  This is a simple nginx-based web server packaged as a container.
  It demonstrates the minimum required fields for container packaging.
homepage: https://example.com/simple-app
maintainer: Your Name <your.email@example.com>
license: MIT
tags:
  - role::container-app        # Required tag
  - implemented-in::docker     # Indicates Docker-based app
debian_section: net            # Debian package section
architecture: all              # Architecture-independent

# Web UI configuration (optional but recommended)
web_ui:
  enabled: true
  path: /                      # Root path
  port: 8080                   # Port where UI is accessible
  protocol: http               # http or https

# Default configuration values
default_config:
  APP_PORT: "8080"
  LOG_LEVEL: "info"
```

**Key Points:**
- `package_name` must end with `-container` suffix
- `tags` must include `role::container-app`
- `web_ui` enables Cockpit integration
- `default_config` sets environment variable defaults

#### docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    image: nginx:alpine
    container_name: simple-webserver
    ports:
      - "${APP_PORT:-8080}:80"      # Use environment variable with fallback
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
    volumes:
      # Standard path: /var/lib/container-apps/<package-name>/
      - /var/lib/container-apps/simple-webserver-container/data:/usr/share/nginx/html:rw
    restart: "no"                   # systemd manages restarts
```

**Key Points:**
- Use environment variables for configurable values: `${VAR:-default}`
- Set `restart: "no"` - systemd handles restart policies
- Volumes must use standard path: `/var/lib/container-apps/<package-name>/`
- Container name should match your app name (lowercase, hyphens)

#### config.yml

```yaml
version: "1.0"
groups:
  - id: general
    label: General Settings
    description: Basic application configuration
    fields:
      - id: APP_PORT                    # Must match env var in compose file
        label: Application Port
        type: integer
        default: 8080                   # Must match default_config in metadata
        required: true
        min: 1024                       # Validation constraints
        max: 65535
        description: Port on which the application will listen

      - id: LOG_LEVEL
        label: Log Level
        type: enum
        default: info
        required: false
        options:                        # Enum options
          - debug
          - info
          - warning
          - error
        description: Logging verbosity level
```

**Key Points:**
- Field `id` must match environment variable names
- `default` values must match `default_config` in metadata.yaml
- Groups organize related configuration fields
- Supports types: `string`, `integer`, `boolean`, `enum`, `password`

### Building the Simple Example

```bash
# Generate package structure
generate-container-packages simple-app/ build/

# Output shows:
# Generated package: build/simple-webserver-container/

# Build the Debian package
cd build/simple-webserver-container
dpkg-buildpackage -us -uc

# Result: simple-webserver-container_1.0.0_all.deb
```

## Full-Featured Example

This example demonstrates all available options and features.

### Directory: full-app/

#### metadata.yaml

```yaml
# Full App - Complete container app definition with all optional fields
name: Full Featured Application
package_name: full-featured-app-container
version: 2.1.3-1                        # Can include Debian revision
upstream_version: 2.1.3                 # Original upstream version
description: A full-featured example with all options
long_description: |
  This is a comprehensive example that demonstrates all available
  configuration options in the container packaging system. It includes
  optional fields, dependencies, extended metadata, and multiple
  configuration groups.

  Features:
  - Complete metadata definition
  - All optional fields populated
  - Multiple configuration groups
  - Dependencies and recommendations
  - AppStream metadata support
homepage: https://example.com/full-app
icon: icon.svg                          # SVG preferred, PNG supported
screenshots:                            # For AppStream/software centers
  - screenshot1.png
  - screenshot2.png
maintainer: Full Stack Developer <fullstack@example.com>
license: Apache-2.0                     # SPDX license identifier
tags:
  - role::container-app                 # Required
  - implemented-in::docker              # Implementation
  - interface::web                      # User interface type
  - use::organizing                     # Primary use case
  - works-with::network-traffic         # What it works with
debian_section: web                     # Debian section (net, web, utils, etc.)
architecture: all

# Dependencies (all optional)
depends:                                # Hard dependencies
  - docker.io (>= 20.10) | docker-ce (>= 20.10)
  - docker-compose-plugin
recommends:                             # Soft dependencies (installed by default)
  - cockpit
suggests:                               # Optional enhancements
  - nginx-proxy

# Web UI configuration
web_ui:
  enabled: true
  path: /app                           # Subpath (use / for root)
  port: 3000
  protocol: https                      # http or https

# Default configuration with multiple environment variables
default_config:
  APP_PORT: "3000"
  APP_HOST: "0.0.0.0"
  LOG_LEVEL: "debug"
  DATABASE_URL: "sqlite:///data/app.db"
  ENABLE_AUTH: "true"
  SESSION_SECRET: "change-me-in-production"
  MAX_UPLOAD_SIZE: "100"
  BACKUP_ENABLED: "true"
  BACKUP_SCHEDULE: "0 2 * * *"
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    image: node:18-alpine
    container_name: full-featured-app
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      # All configurable values from metadata.yaml default_config
      - APP_PORT=${APP_PORT:-3000}
      - APP_HOST=${APP_HOST:-0.0.0.0}
      - LOG_LEVEL=${LOG_LEVEL:-debug}
      - DATABASE_URL=${DATABASE_URL:-sqlite:///data/app.db}
      - ENABLE_AUTH=${ENABLE_AUTH:-true}
      - SESSION_SECRET=${SESSION_SECRET:-change-me-in-production}
      - MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE:-100}
      - BACKUP_ENABLED=${BACKUP_ENABLED:-true}
      - BACKUP_SCHEDULE=${BACKUP_SCHEDULE:-0 2 * * *}
    volumes:
      # Multiple volumes for different data types
      - /var/lib/container-apps/full-featured-app-container/data:/data:rw
      - /var/lib/container-apps/full-featured-app-container/config:/config:rw
      - /var/lib/container-apps/full-featured-app-container/backups:/backups:rw
    healthcheck:                        # Optional health monitoring
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: "no"                       # systemd manages restarts
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

#### config.yml

```yaml
version: "1.0"
groups:
  # Group 1: Network configuration
  - id: network
    label: Network Settings
    description: Configure network and accessibility options
    fields:
      - id: APP_PORT
        label: Application Port
        type: integer
        default: 3000
        required: true
        min: 1024
        max: 65535
        description: Port on which the application will listen

      - id: APP_HOST
        label: Bind Address
        type: string
        default: "0.0.0.0"
        required: true
        description: IP address to bind to (0.0.0.0 for all interfaces)

  # Group 2: Database configuration
  - id: database
    label: Database Configuration
    description: Database connection and storage settings
    fields:
      - id: DATABASE_URL
        label: Database URL
        type: string
        default: "sqlite:///data/app.db"
        required: true
        description: Database connection string

  # Group 3: Security settings
  - id: security
    label: Security Settings
    description: Authentication and security options
    fields:
      - id: ENABLE_AUTH
        label: Enable Authentication
        type: boolean
        default: true
        required: false
        description: Require users to authenticate

      - id: SESSION_SECRET
        label: Session Secret
        type: password                  # Password type hides input
        default: "change-me-in-production"
        required: true
        description: Secret key for session encryption (change in production!)

  # Group 4: Application behavior
  - id: application
    label: Application Settings
    description: General application behavior
    fields:
      - id: LOG_LEVEL
        label: Log Level
        type: enum
        default: debug
        required: false
        options:
          - debug
          - info
          - warning
          - error
          - critical
        description: Logging verbosity level

      - id: MAX_UPLOAD_SIZE
        label: Maximum Upload Size (MB)
        type: integer
        default: 100
        required: false
        min: 1
        max: 1000
        description: Maximum file upload size in megabytes

  # Group 5: Backup configuration
  - id: backup
    label: Backup Settings
    description: Automated backup configuration
    fields:
      - id: BACKUP_ENABLED
        label: Enable Backups
        type: boolean
        default: true
        required: false
        description: Enable automated backups

      - id: BACKUP_SCHEDULE
        label: Backup Schedule
        type: string
        default: "0 2 * * *"
        required: false
        description: "Cron schedule for backups (default: daily at 2 AM)"
```

## Common Patterns

### Pattern 1: Web Application with Database

For apps that need persistent database storage:

```yaml
# In docker-compose.yml
services:
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD:-changeme}
      - POSTGRES_USER=${DB_USER:-appuser}
      - POSTGRES_DB=${DB_NAME:-appdb}
    volumes:
      - /var/lib/container-apps/myapp-container/db:/var/lib/postgresql/data:rw
    networks:
      - app-network

  app:
    image: myapp:latest
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-appuser}:${DB_PASSWORD:-changeme}@db:5432/${DB_NAME:-appdb}
    # ... rest of config
```

### Pattern 2: Multi-Container Application

Apps with multiple services (e.g., app + worker + cache):

```yaml
services:
  web:
    image: myapp:latest
    ports:
      - "${APP_PORT:-8080}:8080"
    depends_on:
      - redis
      - worker
    # ...

  worker:
    image: myapp:latest
    command: ["worker"]
    depends_on:
      - redis
    # ...

  redis:
    image: redis:7-alpine
    volumes:
      - /var/lib/container-apps/myapp-container/redis:/data:rw
    # ...
```

### Pattern 3: Application with Volume Mounts

For apps needing access to host directories:

```yaml
# In metadata.yaml default_config
default_config:
  DATA_DIR: "/var/lib/container-apps/myapp-container/data"
  MEDIA_DIR: "/var/lib/container-apps/myapp-container/media"

# In docker-compose.yml
volumes:
  - ${DATA_DIR:-/var/lib/container-apps/myapp-container/data}:/app/data:rw
  - ${MEDIA_DIR:-/var/lib/container-apps/myapp-container/media}:/app/media:rw
```

### Pattern 4: Marine Navigation Application

Example for Signal K or similar marine apps:

```yaml
# In metadata.yaml
name: Signal K Server
package_name: signalk-server-container
tags:
  - role::container-app
  - implemented-in::docker
  - interface::web
  - field::marine                      # Marine-specific tag
  - use::monitor
  - works-with::network-traffic

web_ui:
  enabled: true
  path: /                              # Signal K runs on root path
  port: 3000
  protocol: http

# In docker-compose.yml
services:
  signalk:
    image: signalk/signalk-server:latest
    ports:
      - "${SIGNALK_PORT:-3000}:3000"
    volumes:
      - /var/lib/container-apps/signalk-server-container/data:/home/node/.signalk:rw
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0       # Serial port access for NMEA
    privileged: false                   # Avoid privileged when possible
```

### Pattern 5: Application with Custom Healthcheck

For apps that provide health endpoints:

```yaml
# In docker-compose.yml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:${APP_PORT:-8080}/health || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 40s
```

### Pattern 6: Non-Root Container with Volume Permissions

**Important:** Many containers run as non-root users for security. When a container runs as a specific UID, bind-mounted volumes must have matching ownership. The `user` field in docker-compose.yml controls this.

#### Why This Matters

Docker creates bind mount directories as `root:root`. If your container runs as a non-root user (e.g., UID 472 for Grafana), it won't be able to write to the directory and will fail to start.

#### How It Works

When you specify `user` in docker-compose.yml, the tool automatically:
1. Detects the UID/GID at build time
2. Generates a `postinst` script that creates data directories with correct ownership
3. The container can then write to its volumes without permission errors

#### Fixed UID Example (Grafana)

Grafana runs as UID 472 inside the container:

```yaml
# In docker-compose.yml
services:
  grafana:
    image: grafana/grafana:12.1.4
    container_name: grafana
    user: "472"                    # Grafana's internal UID
    volumes:
      - ${CONTAINER_DATA_ROOT}/data:/var/lib/grafana:rw
    # ...
```

The generated `postinst` will include:
```bash
mkdir -p "/var/lib/container-apps/grafana-container/data/data"
chown 472:472 "/var/lib/container-apps/grafana-container/data/data"
```

#### Configurable UID/GID Example (LinuxServer.io apps)

Many containers support configurable PUID/PGID:

```yaml
# In metadata.yaml
default_config:
  PUID: "1000"
  PGID: "1000"
  # ...

# In docker-compose.yml
services:
  app:
    image: linuxserver/sonarr:latest
    user: "${PUID}:${PGID}"        # Resolved at build time
    environment:
      - PUID=${PUID:-1000}
      - PGID=${PGID:-1000}
    volumes:
      - ${CONTAINER_DATA_ROOT}/config:/config:rw
```

#### When to Use the `user` Field

| Scenario | Action |
|----------|--------|
| Container runs as root | No `user` field needed |
| Container runs as fixed non-root UID | Add `user: "UID"` or `user: "UID:GID"` |
| Container supports PUID/PGID | Add `user: "${PUID}:${PGID}"` and define in `default_config` |

#### Finding the Container's UID

Check the container's documentation or inspect the image:

```bash
# Inspect the image's default user
docker inspect grafana/grafana:12.1.4 --format '{{.Config.User}}'

# Or run the container and check
docker run --rm grafana/grafana:12.1.4 id
# Output: uid=472(grafana) gid=0(root) groups=0(root)
```

## Field Reference

### metadata.yaml Fields

#### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Human-readable app name | `"Signal K Server"` |
| `package_name` | string | Package name (must end with `-container`) | `"signalk-container"` |
| `version` | string | Package version (Debian format) | `"2.1.3-1"` |
| `upstream_version` | string | Original upstream version | `"2.1.3"` |
| `description` | string | Short description (< 80 chars) | `"Marine data server"` |
| `long_description` | string | Detailed description (multi-line) | See examples above |
| `homepage` | URL | Project homepage | `"https://signalk.org"` |
| `maintainer` | string | Maintainer name and email | `"John Doe <john@example.com>"` |
| `license` | string | SPDX license identifier | `"MIT"`, `"Apache-2.0"`, `"GPL-3.0"` |
| `tags` | list | Debian tags (must include `role::container-app`) | See examples |
| `debian_section` | string | Debian section | `"net"`, `"web"`, `"utils"`, `"games"` |
| `architecture` | string | Target architecture | `"all"`, `"arm64"`, `"amd64"` |

#### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `icon` | path | Icon filename (PNG or SVG) | `"icon.svg"` |
| `screenshots` | list | Screenshot filenames | `["screenshot1.png"]` |
| `depends` | list | Hard dependencies | `["docker.io"]` |
| `recommends` | list | Soft dependencies | `["cockpit"]` |
| `suggests` | list | Optional packages | `["nginx-proxy"]` |
| `web_ui` | object | Web UI configuration | See below |
| `default_config` | object | Default environment variables | See examples |

#### web_ui Object

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `enabled` | boolean | Enable Cockpit integration | `true` |
| `path` | string | URL path to application | `"/"` or `"/app"` |
| `port` | integer | Port number | `3000` |
| `protocol` | string | Protocol (http or https) | `"http"` |

### config.yml Fields

#### Field Types

| Type | Description | Validation | Example Use |
|------|-------------|------------|-------------|
| `string` | Text input | None (unless pattern specified) | Paths, URLs, names |
| `integer` | Numeric input | `min`, `max` constraints | Ports, sizes, counts |
| `boolean` | True/false toggle | None | Feature flags |
| `enum` | Dropdown selection | `options` list | Log levels, modes |
| `password` | Password input (hidden) | None | Secrets, tokens |

#### Field Attributes

| Attribute | Required | Type | Description |
|-----------|----------|------|-------------|
| `id` | Yes | string | Environment variable name |
| `label` | Yes | string | Display label |
| `type` | Yes | string | Field type (see above) |
| `default` | Yes | varies | Default value |
| `required` | Yes | boolean | Whether field is required |
| `description` | Yes | string | Help text |
| `min` | No | integer | Minimum value (integer only) |
| `max` | No | integer | Maximum value (integer only) |
| `options` | No | list | Valid options (enum only) |

## Troubleshooting

### Common Errors

#### Error: Package name does not end with '-container'

**Problem:** Package name validation failed.

```yaml
# Wrong
package_name: signalk-server

# Correct
package_name: signalk-server-container
```

#### Error: Missing required tag 'role::container-app'

**Problem:** Required Debian tag not present.

```yaml
# Wrong
tags:
  - implemented-in::docker

# Correct
tags:
  - role::container-app
  - implemented-in::docker
```

#### Error: Field 'APP_PORT' in config.yml does not match default_config

**Problem:** Mismatch between config.yml field ID and metadata.yaml default_config.

```yaml
# In metadata.yaml
default_config:
  APP_PORT: "8080"        # This key...

# In config.yml
fields:
  - id: APP_PORT          # ...must match this id
    default: 8080         # And this value must match
```

#### Error: Volume path does not use standard location

**Problem:** Docker Compose volume doesn't use `/var/lib/container-apps/<package-name>/`.

```yaml
# Wrong
volumes:
  - /home/user/data:/data

# Correct
volumes:
  - /var/lib/container-apps/myapp-container/data:/data:rw
```

#### Error: Invalid version format

**Problem:** Version doesn't follow Debian versioning rules.

```yaml
# Wrong
version: v1.2.3
version: 1.2.3beta

# Correct
version: 1.2.3
version: 1.2.3-1
version: 1.2.3~beta1
version: 20250113
version: 2025.01.13
```

#### Warning: restart policy should be "no" (systemd manages restarts)

**Problem:** Docker Compose has restart policy set.

```yaml
# Wrong
restart: always
restart: unless-stopped

# Correct
restart: "no"
```

#### Error: Container fails with "Permission denied" on volume

**Problem:** Container runs as non-root user but data directory is owned by root.

**Symptoms:**
- Container exits immediately after starting
- Logs show "permission denied" or "cannot create directory"
- Data directory exists but is owned by `root:root`

**Solution:** Add the `user` field to docker-compose.yml specifying the container's UID:

```yaml
# Check what user the container runs as
docker run --rm <image> id
# Example output: uid=472(grafana) gid=0(root)

# Add user field to docker-compose.yml
services:
  app:
    image: <image>
    user: "472"          # Use the UID from above
    volumes:
      - ${CONTAINER_DATA_ROOT}/data:/app/data:rw
```

After rebuilding the package, the `postinst` script will create the directory with correct ownership.

See [Pattern 6: Non-Root Container with Volume Permissions](#pattern-6-non-root-container-with-volume-permissions) for details.

### Validation Tips

1. **Always validate before building:**
   ```bash
   generate-container-packages --validate-only my-app/
   ```

2. **Check environment variable consistency:**
   - Every variable in `default_config` should appear in `docker-compose.yml`
   - Every field in `config.yml` should match a `default_config` entry

3. **Test with minimal example first:**
   - Start with the minimal example
   - Add features incrementally
   - Validate after each addition

4. **Use proper YAML formatting:**
   - Use 2-space indentation
   - Quote string values with special characters
   - Use `|` for multi-line strings

## Best Practices

### Naming Conventions

1. **Package names**: Use lowercase, hyphens, descriptive names ending in `-container`
   - Good: `signalk-server-container`, `opencpn-viewer-container`
   - Bad: `SignalK_Container`, `opencpn`, `myapp`

2. **Environment variables**: Use UPPERCASE with underscores
   - Good: `APP_PORT`, `LOG_LEVEL`, `DATABASE_URL`
   - Bad: `app-port`, `logLevel`, `database.url`

3. **Config groups**: Use lowercase IDs, descriptive labels
   - ID: `network`, `database`, `security`
   - Label: `"Network Settings"`, `"Database Configuration"`

### Security Considerations

1. **Secrets management:**
   ```yaml
   # Provide placeholder, warn users to change
   default_config:
     SESSION_SECRET: "change-me-in-production"
     API_KEY: "configure-after-installation"

   # Use password type in config.yml
   fields:
     - id: SESSION_SECRET
       type: password
       description: "IMPORTANT: Change this value after installation!"
   ```

2. **Avoid privileged mode:**
   ```yaml
   # Use specific capabilities instead
   cap_add:
     - NET_ADMIN
   # Instead of:
   # privileged: true
   ```

3. **Restrict volume permissions:**
   ```yaml
   # Prefer read-only when possible
   volumes:
     - /var/lib/container-apps/myapp-container/config:/config:ro
     - /var/lib/container-apps/myapp-container/data:/data:rw
   ```

### Performance Tips

1. **Use appropriate base images:**
   - Alpine for smaller size
   - Debian/Ubuntu for compatibility
   - Specific version tags (not `latest`)

2. **Implement health checks:**
   - Helps systemd monitor service health
   - Enables automatic recovery
   - Provides status information

3. **Use networks wisely:**
   - Create custom networks for multi-container apps
   - Use internal networks for database-only services

### Maintenance

1. **Version all the things:**
   ```yaml
   # In docker-compose.yml
   image: signalk/signalk-server:2.1.3    # Not :latest

   # In metadata.yaml
   upstream_version: 2.1.3
   version: 2.1.3-1                       # Add Debian revision for packaging changes
   ```

2. **Document configuration:**
   ```yaml
   # Clear, helpful descriptions
   fields:
     - id: BACKUP_SCHEDULE
       description: "Cron schedule (e.g., '0 2 * * *' for daily at 2 AM)"
   ```

3. **Keep examples updated:**
   - Test examples with actual builds
   - Update when schemas change
   - Include comments for tricky parts

### Testing Your Package

```bash
# 1. Validate inputs
generate-container-packages --validate-only my-app/

# 2. Generate package structure
generate-container-packages my-app/ build/

# 3. Build package
cd build/my-app-container
dpkg-buildpackage -us -uc

# 4. Install and test
sudo dpkg -i ../my-app-container_*.deb
sudo systemctl status my-app-container
curl http://localhost:8080/

# 5. Check configuration
cat /etc/container-apps/my-app-container/env

# 6. Test removal
sudo apt remove my-app-container        # Keeps config
sudo apt purge my-app-container         # Removes everything
```

## Additional Resources

- [Technical Specification](docs/SPEC.md) - Detailed technical requirements
- [Architecture Documentation](docs/ARCHITECTURE.md) - System design
- [Project README](README.md) - Quick start and installation
- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/) - Debian packaging standards
- [Docker Compose Documentation](https://docs.docker.com/compose/) - Compose file reference
- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/) - Service unit files

## Getting Help

If you encounter issues:

1. Check validation errors carefully - they usually indicate exactly what's wrong
2. Compare your files against the examples in this document
3. Verify all field IDs match between metadata.yaml, docker-compose.yml, and config.yml
4. Test with the minimal example first to isolate issues
5. Open an issue at [github.com/hatlabs/container-packaging-tools](https://github.com/hatlabs/container-packaging-tools/issues)
