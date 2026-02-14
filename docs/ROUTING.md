# Container Routing Configuration

This document describes how to configure routing and authentication for container applications in HaLOS.

## Overview

HaLOS uses Traefik as a reverse proxy to route web traffic to container applications. Each application is accessible via a subdomain (`{app}.{hostname}.local`) and can be protected by Authelia SSO.

The routing configuration is defined in the `metadata.yaml` file under the `routing` key. At package install time, a `routing.yml` file is generated and installed to `/etc/halos/routing.d/`. At container start time, Traefik's `generate-routing-labels.sh` script reads these files and generates Docker labels for routing.

## Configuration Schema

### What You Configure in metadata.yaml

The routing configuration in `metadata.yaml` specifies:

```yaml
# metadata.yaml
app_id: grafana
package_name: marine-grafana-container
version: 12.1.4

routing:
  # Subdomain for accessing the app (required)
  # Empty string "" means root domain (e.g., halos.local instead of app.halos.local)
  subdomain: grafana

  # Backend type (optional, default: "container")
  # Use "host" for apps using host networking
  backend:
    type: container

  # Authentication configuration (required)
  auth:
    mode: forward_auth  # Options: "forward_auth", "oidc", "none"

    # ForwardAuth header configuration (optional)
    # Only used when mode is "forward_auth"
    forward_auth:
      headers:
        # Map Authelia headers to app-expected headers
        Remote-User: "X-WEBAUTH-USER"
        Remote-Groups: "X-WEBAUTH-GROUPS"
```

### Auto-Derived Values

The following values are **automatically derived** and should NOT be specified in metadata.yaml:

- **`backend.service`** - Derived from the first service in `docker-compose.yml`
- **`backend.port`** - Derived from docker-compose port mappings (container port) or `web_ui.port`

### Generated routing.yml

The package build process generates a `routing.yml` file that includes both user-configured and auto-derived values:

```yaml
# Generated /etc/halos/routing.d/grafana.yml
app_id: grafana

routing:
  subdomain: grafana
  backend:
    service: grafana      # auto-derived from docker-compose.yml
    port: 3000            # auto-derived from port mapping
    type: container
  auth:
    mode: forward_auth
    forward_auth:
      headers:
        Remote-User: X-WEBAUTH-USER
        Remote-Groups: X-WEBAUTH-GROUPS
```

## Authentication Modes

### forward_auth (Default)

For applications that don't have native SSO support. Traefik intercepts requests and validates the session with Authelia before forwarding to the backend.

```yaml
routing:
  subdomain: grafana
  auth:
    mode: forward_auth
```

**With custom header mapping:**

Some applications expect authentication headers with specific names. Use the `forward_auth.headers` section to configure this:

```yaml
routing:
  subdomain: grafana
  auth:
    mode: forward_auth
    forward_auth:
      headers:
        Remote-User: "X-WEBAUTH-USER"
        Remote-Groups: "X-WEBAUTH-GROUPS"
```

This generates a per-app ForwardAuth middleware that passes only the specified headers.

### oidc

For applications with native OpenID Connect support. The application handles the OIDC flow directly with Authelia. No Traefik middleware is applied.

```yaml
routing:
  subdomain: ""  # Root domain
  auth:
    mode: oidc
```

OIDC applications also need an OIDC client snippet. See [OIDC configuration](#oidc-client-configuration).

### none

For applications that should be publicly accessible or that implement their own authentication.

```yaml
routing:
  subdomain: signalk
  auth:
    mode: none
```

## Host Networking

Some applications require host networking (e.g., to access hardware devices). Use `backend.type: "host"` for these:

```yaml
routing:
  subdomain: signalk
  backend:
    type: host
  auth:
    mode: none
```

This generates a Traefik backend URL pointing to `host.docker.internal` instead of the container name.

## Root Domain

To serve an application at the root domain (e.g., `halos.local` instead of `app.halos.local`), use an empty subdomain:

```yaml
routing:
  subdomain: ""
  auth:
    mode: oidc
```

## Generated Files

When a package is installed, the routing configuration generates:

1. **`/etc/halos/routing.d/{app_id}.yml`** - Routing declaration file
2. **`/etc/halos/traefik-dynamic.d/{app_id}.yml`** - Per-app ForwardAuth middleware (only if custom headers are configured)

At container start time:

3. **`/run/halos/routing-labels/{app_id}.yml`** - Docker Compose override with Traefik labels

## HTTP to HTTPS Redirect

All HTTP requests are automatically redirected to HTTPS. The generated Traefik labels create separate HTTP and HTTPS routers:

- HTTP router: Applies `redirect-to-https@file` middleware
- HTTPS router: Applies TLS and authentication middleware

## OIDC Client Configuration

Applications using OIDC authentication need an OIDC client registered with Authelia. This is configured separately from routing:

```yaml
# In metadata.yaml
oidc:
  client_id: myapp
  client_name: "My Application"
  authorization_policy: one_factor
  redirect_uris:
    - "/api/auth/callback/oidc"
  scopes:
    - openid
    - profile
    - email
    - groups
  consent_mode: implicit
  token_endpoint_auth_method: client_secret_basic
```

See the Authelia documentation for available OIDC options.

## Troubleshooting

### App not accessible via subdomain

1. Check if the routing.yml file exists: `ls /etc/halos/routing.d/`
2. Check if Traefik picked up the labels: `docker inspect <container> | grep traefik`
3. Check Traefik logs: `journalctl -u halos-traefik-container`

### Authentication redirect loop

1. Verify the auth mode is correct for the application
2. Check Authelia logs: `journalctl -u halos-authelia-container`
3. Ensure the subdomain is advertised via mDNS: `avahi-browse -a | grep <subdomain>`

### ForwardAuth headers not working

1. Verify the header mapping in metadata.yaml
2. Check if per-app middleware was generated: `ls /etc/halos/traefik-dynamic.d/`
3. Check the middleware content for correct header names

## Related Documentation

- [SSO_SPEC.md](https://github.com/halos-org/halos-core-containers/blob/main/docs/SSO_SPEC.md) - SSO technical specification
- [SSO_ARCHITECTURE.md](https://github.com/halos-org/halos-core-containers/blob/main/docs/SSO_ARCHITECTURE.md) - SSO system architecture
