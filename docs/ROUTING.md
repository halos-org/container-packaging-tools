# Container Routing Configuration

This document describes how to configure routing and authentication for container applications in HaLOS.

## Overview

HaLOS uses Traefik as a reverse proxy to route web traffic to container applications. Each routed application is assigned a dedicated HTTPS port at runtime and is accessible via a path redirect (`https://{hostname}/{app-id}/` redirects to the app's port). Applications can be protected by Authelia SSO.

The routing configuration is defined in the `metadata.yaml` file under the `routing` key. At package install time, a `routing.yml` file is generated and installed to `/etc/halos/routing.d/`. At container start time, `configure-container-routing` reads these files and generates Traefik configuration.

## Configuration Schema

### What You Configure in metadata.yaml

The routing configuration in `metadata.yaml` specifies:

```yaml
# metadata.yaml
app_id: grafana
package_name: marine-grafana-container
version: 12.1.4

routing:
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

The following values are **automatically derived** and must NOT be written in metadata.yaml. `routing` has no `backend` key at all; the whole block below is generator output.

- **`backend.type`** - `host` when a service in `docker-compose.yml` sets `network_mode: host`, otherwise `container`
- **`backend.service`** - Derived from the first service in `docker-compose.yml`
- **`backend.port`** - Derived from docker-compose port mappings (container port) or `web_ui.port`

Writing `backend` in metadata.yaml fails the build with `routing -> backend: Extra inputs are not permitted`.

### Generated routing.yml

The package build process generates a `routing.yml` file that includes both user-configured and auto-derived values:

```yaml
# Generated /etc/halos/routing.d/grafana.yml
app_id: grafana

routing:
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
  auth:
    mode: forward_auth
```

**With custom header mapping:**

Some applications expect authentication headers with specific names. Use the `forward_auth.headers` section to configure this:

```yaml
routing:
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
  auth:
    mode: oidc
```

OIDC applications also need an OIDC client snippet. See [OIDC configuration](#oidc-client-configuration).

### none

For applications that should be publicly accessible or that implement their own authentication.

```yaml
routing:
  auth:
    mode: none
```

## Host Networking

Some applications require host networking, for example to reach hardware devices. Declare that in `docker-compose.yml`, not in metadata.yaml:

```yaml
# docker-compose.yml
services:
  myapp:
    network_mode: host
```

The generator detects `network_mode: host` and writes `backend.type: host` into the generated routing.yml, which points the Traefik backend at `host.docker.internal` instead of the container name. A host-networked app has no port mapping to derive a port from, so give the port in metadata.yaml:

```yaml
# metadata.yaml
routing:
  host_port: 3000
  auth:
    mode: none
```

## mDNS Service Advertising

An app can advertise itself over mDNS with DNS-SD service records, so that clients on the local network discover it without a configured address:

```yaml
routing:
  mdns:
    - type: _signalk-wss._tcp
    - type: _nmea-0183._tcp
      port: 10110
```

An entry without a `port` takes the app's external TLS port, which Traefik assigns at runtime. Give a `port` for a service the proxy does not front, such as a plain TCP stream on a fixed host port.

`configure-container-routing` writes the avahi service file when the container starts, and withdraws it when the container stops or the package is removed. The app must not run its own mDNS responder: `avahi-daemon` owns UDP 5353 on the host, and a second responder under host networking answers nothing.

An app that declares `routing.mdns` gets `Depends: halos-core-containers (>= 0.8.0)`. An older release parses `routing.d`, ignores the `mdns` key, and writes no record, so without the floor a partial upgrade advertises nothing while every package reports success.

The generated declaration carries the services at the top level:

```yaml
# Generated /etc/halos/routing.d/signalk-server.yml
mdns:
- type: _signalk-wss._tcp
- type: _nmea-0183._tcp
  port: 10110
```

## Generated Files

When a package is installed, the routing configuration generates:

1. **`/etc/halos/routing.d/{app_id}.yml`** - Routing declaration file
2. **`/etc/halos/traefik-dynamic.d/{app_id}.yml`** - Per-app ForwardAuth middleware (only if custom headers are configured)

At container start time:

3. Traefik configuration is generated from routing declarations by `configure-container-routing`
4. **`/etc/avahi/services/halos-{app_id}.service`** - mDNS service records (only if `routing.mdns` is set), removed again when the app stops or is removed

## HTTP to HTTPS Redirect

All HTTP requests are automatically redirected to HTTPS. The generated Traefik configuration creates separate HTTP and HTTPS routers:

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

### App not accessible

1. Check if the routing.yml file exists: `ls /etc/halos/routing.d/`
2. Check if Traefik picked up the configuration: `docker inspect <container> | grep traefik`
3. Check Traefik logs: `journalctl -u halos-traefik-container`

### Authentication redirect loop

1. Verify the auth mode is correct for the application
2. Check Authelia logs: `journalctl -u halos-authelia-container`

### ForwardAuth headers not working

1. Verify the header mapping in metadata.yaml
2. Check if per-app middleware was generated: `ls /etc/halos/traefik-dynamic.d/`
3. Check the middleware content for correct header names

## Related Documentation

- [SSO_SPEC.md](https://github.com/halos-org/halos-core-containers/blob/main/docs/SSO_SPEC.md) - SSO technical specification
- [SSO_ARCHITECTURE.md](https://github.com/halos-org/halos-core-containers/blob/main/docs/SSO_ARCHITECTURE.md) - SSO system architecture
