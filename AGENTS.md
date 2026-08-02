⚠️ **THESE RULES ONLY APPLY TO FILES IN /container-packaging-tools/** ⚠️

# Container Packaging Tools - Development Guide

## 🎯 For Agentic Coding: Use the HaLOS Workspace

This repository should be used as part of the halos workspace for AI-assisted development:

```bash
# Clone workspace and all repos
git clone https://github.com/halos-org/halos.git
cd halos
./run repos:clone
```

See `halos/docs/` for development workflows and guidance.

## About This Project

Tooling for generating Debian packages from container application definitions.

**Local Instructions**: For environment-specific instructions and configurations, see @CLAUDE.local.md (not committed to version control).

## Container Lifecycle Conventions

All container apps must follow these conventions in their `docker-compose.yml`:

### Restart Policy

```yaml
services:
  myapp:
    restart: unless-stopped
```

**Rationale**: Docker handles per-container restarts (fast recovery for individual containers). Systemd is the fallback for compose process failures. This is critical for multi-service compose files where sidekick containers can crash independently.

### Logging Driver

```yaml
services:
  myapp:
    logging:
      driver: journald
      options:
        tag: "{{.Name}}"
```

**Rationale**: Provides unified logging via `journalctl -u <service>` with per-container filtering using `journalctl CONTAINER_NAME=<container>`. Eliminates log duplication (no separate json-file storage).

### Validation

The validator enforces these conventions as **blocking errors**. Apps that don't follow them will fail to build.

See [halos#49](https://github.com/halos-org/halos/issues/49) for the full design rationale.

### Custom Prestart Hook

The generator always emits the framework `prestart.sh` (creates the runtime dir and `runtime.env`, sources the env files, and writes `HOMARR_URL` for web_ui apps). An app that needs app-specific startup logic ships a `prestart.sh` in its input directory; the generator installs it as `app-prestart.sh` beside `docker-compose.yml` and the framework script **sources it last**. App authors never re-implement the framework scaffolding — the hook holds only app-specific logic (generating secrets, seeding config, installing plugins).

Hook contract — available when `app-prestart.sh` runs:

- The env files are already sourced (`env.defaults`, `env`), so their values are in scope.
- `$HALOS_DOMAIN` is inherited from the unit environment (routed/web_ui apps).
- `$RUNTIME_ENV` points at the already-created `runtime.env` (mode `600`). **Append with `>>` only — never `>`/`cat >`**, which would truncate the framework-written values.
- The hook resolves its own directory via `BASH_SOURCE`; it sits beside `docker-compose.yml`, so `"$(dirname "${BASH_SOURCE[0]}")"/docker-compose.yml` resolves.
- The framework runs under `set -e`, so a failing hook command aborts unit start. Best-effort steps must guard themselves (e.g. `if ! cmd; then echo warn; fi`).
- `runtime.env` lives in `/run` (tmpfs) and is **recreated on every start**, so it is not durable. A hook that generates a secret must persist it to a stable mode-`600` path under the app's `/var/lib/container-apps/<pkg>/data` dir with a generate-once guard (`[ -f "$f" ] || openssl rand ... > "$f"`), then echo it into `$RUNTIME_ENV` — otherwise the secret is regenerated each restart and diverges from anything that stored it.

Prefer build-time `default-data/` for static seed config; reserve the hook for logic that genuinely needs runtime context.

### Provisioning Hook

An app that needs long, one-time setup before its container starts (installing plugins, fetching a dataset) ships a `provision.sh`. The generator emits `<package>-provision.service` (`Type=oneshot`) and orders the app unit `Wants=` + `After=` it, so provisioning completes before the app starts while a failed or skipped run never prevents it from starting.

Use this rather than `app-prestart.sh` for anything slow. The prestart hook runs inside the app unit's blocking `ExecStartPre`, where exceeding `TimeoutStartSec` kills the work mid-flight and five such failures drive the unit to a permanent `failed` state. The provisioning unit has its own timeout budget, and its failures never count against the app's start limit.

Presence of the file is the whole declaration. There is no metadata field, because provisioning has no parameters to configure (contrast `file_watchers`, which needs a path, type, and action). Unlike `prestart.sh`, the hook keeps its source name (`provision.sh`; nothing generated collides with it) and is **executed, not sourced**: it runs as its own unit's `ExecStart`, in its own process, before the app's prestart has run at all.

Hook contract — what `provision.sh` may rely on, and what it owes:

- **It runs on every app start**, not once per install. That includes every `Restart=always` auto-restart and every file-watcher-triggered restart. The hook must be idempotent and a fast no-op when there is nothing to do, so check for what you would install before installing it.
- **It must enforce its own time budget.** The unit's `TimeoutStartSec` is an outer stop-loss, not policy. The app's start job waits on this unit, so a hook without per-operation timeouts and a total wall-clock budget delays app availability for as long as it runs.
- **Exit 0 on expected transient failure** (no network, registry unreachable). This does not gate the app either way, since the app only `Wants=` this unit. What a non-zero exit costs is a `failed` unit and a `degraded` system state for a condition that is not a fault. The retry is the next app start: there is no timer, and nothing re-triggers provisioning while a healthy container keeps running.
- **It must create and own any directory it writes to.** Nothing upstream guarantees one exists with the right ownership. `postinst` derives volume ownership from the compose service's `user:` field, so an app that declares none gets a **root-owned** data directory, and the app's prestart, which is where a blanket `chown` usually lives, has not run yet.
- **Name any container it runs `"$HALOS_PROVISION_CONTAINER"`**, and force-remove a stale one at hook start. The unit exports that name and reaps it in `ExecStopPost`. That is the cleanup which survives a start timeout: systemd sends `SIGTERM` when `TimeoutStartSec` expires and escalates to `SIGKILL` after `TimeoutStopSec`, so an untrapped hook dies without running its own cleanup, while a container started by dockerd outlives the unit and keeps writing to the data volume.
- **Not available**: `runtime.env`, `$HALOS_DOMAIN`, and the routing port registry. Each has a different producer, and this unit orders after none of them: `runtime.env` is written by the app's prestart; `$HALOS_DOMAIN` is published by `halos-resolve-domain.service` into `/run/halos/domain.env`, which only the app unit loads; the port registry is written by `configure-container-routing`, an `ExecStartPre` of the app unit. Only `env.defaults` and `env` are loaded here.

**Threat model:**
- The hook runs as **root** with no `User=`, and `Requires=docker.service`, where docker socket access is root-equivalent. An app definition is trusted, reviewed, first-party input: dropping a `provision.sh` into an app directory grants root execution on every boot with no further opt-in.
- `env` and `env.defaults` are loaded via `EnvironmentFile=` and are mode `600` because they may hold shipped default credentials. The unit's output goes to the journal, which operators read through Cockpit, so a hook must not run under `set -x` or echo its environment.
- Whatever the hook installs at runtime is outside the package manager. A hook that fetches third-party artifacts inherits that supply chain's trust, executes it as whatever user it installs for, and leaves no dpkg record. Decide deliberately whether that is acceptable for the app in question.

**Operational notes:**
- `PartOf=<app>.service` means stopping the app stops an in-flight run. The hook receives `SIGTERM` mid-work, so the unit ends `failed` and `systemctl is-system-running` reports `degraded`. Both clear themselves on the next successful run; no `reset-failed` is needed.
- For an app with a provisioning hook, the app unit's `StartLimitBurst` stops being a reliable "this is broken" signal. See the StartLimit note in `docs/DESIGN.md`. Treat a repeating restart loop, rather than a `failed` unit, as the symptom.

### Declarative OIDC (native-OAuth apps)

An app that authenticates users via Authelia as its own OIDC client (native OAuth — e.g. Grafana, Signal K) declares it under `routing`, instead of hand-writing the lifecycle in a prestart:

```yaml
routing:
  auth:
    mode: oidc                       # no Traefik edge gate; wires the Authelia client scaffolding
    oidc:
      client_name: Grafana           # client_id defaults to app_id
      scopes: [openid, profile, email, groups]
      consent_mode: implicit
      token_endpoint_auth_method: client_secret_basic   # or client_secret_post
      redirect:
        style: port                  # port → :${EXTERNAL_PORT}<path>; path → <path>
        path: /login/generic_oauth
      env:                           # container env var -> resolved source
        GRAFANA_OIDC_CLIENT_SECRET: secret
        HALOS_EXTERNAL_PORT: external_port
```

`mode: oidc` adds no edge gating (the app does its own OAuth) but makes `is_oidc_app` true, which drives the existing scaffolding: `postinst` provisions the client secret once (mode `600`), `service.j2` orders the unit `After=halos-authelia-container.service`, and `postrm` removes the snippet on purge. The generated prestart then resolves the external port (for `style: port`), appends the mapped `env` vars to `runtime.env`, and writes the Authelia client snippet to `/etc/halos/oidc-clients.d/<client_id>.yml`. `env` sources: `secret` (the client secret value), `issuer` (`https://${HALOS_DOMAIN}/sso`), `redirect` (computed redirect URI), `external_port`, `client_id`. App-specific extras (e.g. Signal K's `EXTERNALHOST`) stay in the `app-prestart.sh` hook.

**Threat model:**
- The client secret is generated once by `postinst` (root, mode `600`) and exposed to the container via `runtime.env` (mode `600`) — env-var delivery, as before.
- `redirect_uris` carry the literal `${HALOS_DOMAIN}` token, which the core Authelia merger expands to one URI per DNS hostname in `/etc/halos/hostnames.conf`. **`hostnames.conf` is the redirect allow-list trust anchor**; the generator relies on the loader's hostname validation and emits no redirect outside `${HALOS_DOMAIN}`. The external port is integer-validated before it reaches the snippet.
- The merger hardcodes `public: false` and `authorization_policy: one_factor` for every client; an app needing a different policy (public client, step-up auth) is not expressible via this declarative path.

## Git Workflow Policy

**Branch Workflow:** Never push to main directly - always use feature branches and PRs.

**Pre-Push Requirements:** ALWAYS run these checks locally before pushing to PR:
```bash
# Code quality checks
./run lint              # Linter must pass
./run format:check      # Formatting must pass
uvx ty check src/       # Type checker must pass

# Test checks (matching CI)
uv run pytest tests/test_*.py -m "not integration and not install" -q  # Unit tests
uv run pytest tests/test_*.py -m "integration and not install" -q      # Integration tests
```

All checks must pass locally before pushing. This prevents wasting CI resources and iteration cycles.

## Project Purpose

This package provides `generate-container-packages` command that converts simple container app definitions into full Debian packages. The goal is to make it easy for developers to add new container apps without understanding Debian packaging internals.

## Homarr-Stack Breaks Auto-Injection

The generator emits a conditional `Breaks:` line on generated .debs whenever an app's `metadata.yaml` would cause a path-only `url` to be written into `/etc/halos/webapps.d/<name>.toml`. The exact trigger condition lives in a single predicate, `registry.emits_path_only_url(metadata)`, shared by:

- `registry.generate_registry_toml` — chooses path-only vs. absolute URL for the TOML.
- `template_context._compute_homarr_stack_breaks` — decides whether to auto-inject the `Breaks:` clauses.

Today that predicate is `metadata["routing"] is not None and metadata["web_ui"]["enabled"]`. `web_ui.visible` is recorded *into* the TOML (so the adapter can decide whether to show a card) but does not gate emission — a hidden routed web app still ships a path-only TOML and is loaded by the adapter for ping coverage, which means the peer-version constraints apply identically.

The injected entries are:

- `homarr-container-adapter (<< HOMARR_ADAPTER_MIN_VERSION)`
- `halos-core-containers (<< HALOS_CORE_CONTAINERS_MIN_VERSION)`

Both constants live in `src/generate_container_packages/template_context.py`. Bump them when a new contract evolution in the Homarr stack requires a higher minimum (e.g., a new schema field on `appHrefSchema`, or an adapter capability the generator starts relying on). Bump the predicate in `registry.emits_path_only_url` if the contract's trigger surface changes.

`Breaks` is conditional: it constrains the named peer only when it is *installed*. A HaLOS device that runs container apps without the Homarr dashboard is unaffected. The choice of `Breaks` over `Depends` and of generator-injection over per-app metadata is documented in [the workspace policy doc](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md) (look for the "manual partial upgrades" clause).

App-declared `breaks:` entries in `metadata.yaml` are appended after the auto-injected ones; the two compose rather than overriding. The `breaks` field on `metadata.yaml` is a regular optional list of Debian relationship strings, peer with `depends`, `recommends`, `conflicts`, and `provides`.

## HALOS_DOMAIN Producer Dependency Auto-Injection

Routed / web_ui apps inherit `HALOS_DOMAIN` from `halos-resolve-domain.service` (in `halos-core-containers`), which resolves the canonical hostname once and publishes `/run/halos/domain.env`. The generator wires this on every routed/web_ui app's .deb:

- `service.j2` adds `After=`/`Wants=halos-resolve-domain.service` and `EnvironmentFile=-/run/halos/domain.env` (loaded last, so it wins over a stale `HALOS_DOMAIN` in `runtime.env`).
- `template_context._compute_producer_depends` injects `Depends: halos-core-containers (>= HALOS_CORE_CONTAINERS_PRODUCER_MIN_VERSION)`.
- The generated prestart no longer resolves `HALOS_DOMAIN` or hardcodes `.local`; it inherits the value.

The trigger is the single predicate `template_context._has_routing(metadata)` (`routing:` present or `web_ui.enabled`), shared by the service-template context (`has_routing`) and `_compute_producer_depends`, so the unit wiring and the package dependency cannot drift.

`HALOS_CORE_CONTAINERS_PRODUCER_MIN_VERSION` lives in `src/generate_container_packages/template_context.py`. Bump it when the producer contract (`halos-resolve-domain.service`, the `/run/halos/domain.env` format) changes shape in a way that needs a newer `halos-core-containers`. Bump `_has_routing` if the set of apps that need `HALOS_DOMAIN` changes.

`Depends` (not `Breaks`) is the deliberate choice here, unlike the Homarr-stack `Breaks` above: `halos-core-containers` is part of the minimum install on every device that ships routed/web_ui apps (Traefik/Authelia/Homarr are the web-management layer they route through), so the peer is always present. Per the [Breaks-over-Depends policy](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-05-13-prefer-breaks-over-depends-for-partial-upgrade-gating.md), `Depends` is correct for an always-present peer and documents the structural relationship. The producer-absent failure mode is empty `HALOS_DOMAIN` → broken OIDC, which is not graceful, so the constraint is kept rather than dropped under the [skip-pins policy](https://github.com/halos-org/halos/blob/main/docs/solutions/best-practices/2026-04-30-skip-apt-depends-pins-sibling-halos-packages.md).

## Project Status

**Current Phase**: Planning & Initial Development

All development tasks are tracked as GitHub issues. See the [Issues page](https://github.com/halos-org/container-packaging-tools/issues) for current status.

**Development Phases**:
1. **Core Infrastructure** (Issues #1-6): Validation, loading, and context building
2. **Templates** (Issues #7-13): Jinja2 templates and renderer
3. **Building** (Issues #14-16): Package builder and CLI
4. **Integration Testing** (Issues #17-18): End-to-end tests
5. **Packaging & Documentation** (Issues #19-22): Tool packaging, examples, CI/CD
6. **Polish** (Issues #23-24): Security review and final validation

See [PROJECT_PLANNING_GUIDE.md](../PROJECT_PLANNING_GUIDE.md) in the parent directory for the development workflow.

## Planning Documentation

Important planning documents are in the `docs/` directory:
- @docs/DESIGN.md: High-level design
- @docs/SPEC.md: Technical specification
- @docs/ARCHITECTURE.md: System architecture

## Repository Structure

```
container-packaging-tools/
├── src/
│   └── generate_container_packages/    # Main package
│       ├── __init__.py                 # Package version
│       ├── __main__.py                 # Entry point
│       ├── cli.py                      # Command-line interface
│       ├── validator.py                # Input validation
│       ├── loader.py                   # File loading
│       ├── template_context.py         # Template context builder
│       ├── renderer.py                 # Jinja2 template renderer
│       └── builder.py                  # Package builder
├── schemas/                            # Pydantic models for validation
│   ├── metadata.py                     # metadata.yaml schema
│   └── config.py                       # config.yml schema
├── templates/                          # Jinja2 templates for Debian files
│   ├── debian/
│   │   ├── control.j2
│   │   ├── rules.j2
│   │   ├── postinst.j2
│   │   ├── prerm.j2
│   │   ├── postrm.j2
│   │   ├── changelog.j2
│   │   ├── copyright.j2
│   │   └── compat
│   ├── systemd/
│   │   └── service.j2
│   └── appstream/
│       └── metainfo.xml.j2
├── tests/                              # Test suite
│   ├── fixtures/                       # Test fixtures
│   │   ├── valid/                      # Valid app definitions
│   │   │   ├── simple-app/
│   │   │   └── full-app/
│   │   └── invalid/                    # Invalid app definitions
│   ├── test_models.py                  # Pydantic model tests
│   ├── test_validator.py               # Validation tests
│   ├── test_integration.py             # Integration tests
│   └── test_package_install.py         # Installation tests
├── debian/                             # Debian packaging for this tool
│   ├── control
│   ├── rules
│   ├── install
│   └── ...
├── docs/
│   ├── SPEC.md                         # Technical specification
│   └── ARCHITECTURE.md                 # System architecture
├── pyproject.toml                      # Python packaging config
├── EXAMPLES.md                         # Usage examples
└── README.md                           # Project README
```

## Development

**Tech Stack**:
- Python 3.11+ (targeting Debian stable)
- Pydantic v2 for data validation
- Jinja2 for templating
- PyYAML for YAML parsing
- argparse for CLI (standard library)

**Development Tools**:
- pytest for testing
- ruff for linting and formatting
- ty for type checking (Rust-based Python type checker)
- uv for dependency management (in CI)

**Quick Start with Run Script**:

The `./run` script provides convenient commands for common development tasks.

**IMPORTANT: All development commands run in Docker containers**

First, build the development container:
```bash
./run docker:build   # Build the Debian Trixie development container
```

Then use Docker-based commands for all development tasks:
```bash
# Testing
./run test           # Run all tests in Docker
./run test:coverage  # Run tests with coverage report (80% required)
./run test:unit      # Run unit tests only
./run test:integration  # Run integration tests only

# Code Quality
./run check          # Run all quality checks (lint, format, typecheck)
./run lint           # Run ruff linter
./run lint:fix       # Run linter with auto-fix
./run format         # Format code with ruff
./run format:check   # Check formatting without changes
./run typecheck      # Run ty type checker

# Building
./run build          # Build Debian package in Docker

# Docker Management
./run docker:shell   # Open interactive shell in container
./run docker:clean   # Remove Docker containers and images

# Utilities
./run help           # Show all available commands
```

**Why Docker?**
- Tests require `dpkg-buildpackage` which is not available on all systems (especially macOS)
- Ensures consistent Debian Trixie environment across all developers
- Prevents "works on my machine" issues
- All CI/CD runs in the same Docker environment

**Local Development** (without Docker):
If you want to run tests locally (e.g., for faster iteration), you'll need:
```bash
# Debian/Ubuntu only - install build tools
sudo apt install dpkg-dev debhelper dh-python python3-all

# Install dependencies
uv sync --dev

# Run tests locally (will fail on non-Debian systems)
uv run pytest
```

**Code Quality**:
- Unit tests required for all modules
- Integration tests for full pipeline
- Target >80% code coverage
- All tests must pass before merging

## Building the Package

The tool is packaged as a Debian package using Docker:

```bash
./run build   # Builds in Docker with dpkg-buildpackage
```

Or manually in a Debian/Ubuntu environment:
```bash
dpkg-buildpackage -us -uc
```

The resulting package will be installable on Debian 12+ (Trixie) and Raspberry Pi OS.

## Related

- **Parent**: [../AGENTS.md](../AGENTS.md) - Workspace documentation
- **Users**: [halos-marine-containers](https://github.com/halos-org/halos-marine-containers)
