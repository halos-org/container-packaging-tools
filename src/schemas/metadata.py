"""Pydantic models for validating metadata.yaml files."""

import re
import subprocess
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

# Valid watch types for systemd .path units
WatchType = Literal["directory_modified", "path_changed", "path_exists"]


class WebUI(BaseModel):
    """Web UI configuration for the container application."""

    enabled: bool = Field(description="Whether web UI is available")
    path: str | None = Field(None, description="URL path to access the web UI")
    port: int | None = Field(
        None, ge=1, le=65535, description="Port the web UI listens on"
    )
    protocol: Literal["http", "https"] | None = Field(
        None, description="Protocol used by web UI"
    )
    visible: bool = Field(
        False, description="Whether app appears on Homarr dashboards (default: false)"
    )


class Layout(BaseModel):
    """Homarr dashboard layout configuration.

    Controls how the app card appears on the Homarr dashboard including
    placement priority, size, and optional explicit positioning.
    """

    priority: int = Field(
        default=50,
        ge=0,
        le=99,
        description=(
            "Placement priority (lower = placed first). "
            "Ranges: 0-19 system, 20-39 primary, 40-59 default, 60-79 utility, 80-99 external"
        ),
    )
    width: int = Field(
        default=1,
        ge=1,
        le=12,
        description="Card width in grid columns (1-12)",
    )
    height: int = Field(
        default=1,
        ge=1,
        description="Card height in grid rows",
    )
    x_offset: int | None = Field(
        default=None,
        ge=0,
        le=11,
        description="Explicit column position (0-11). If omitted, auto-positioned.",
    )
    y_offset: int | None = Field(
        default=None,
        ge=0,
        description="Explicit row position. If omitted, auto-positioned.",
    )


class TraefikForwardAuth(BaseModel):
    """Custom header mappings for Forward Auth.

    When specified, generates a per-app Traefik middleware that maps
    Authelia response headers to custom header names expected by the app.
    """

    headers: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Mapping of Authelia header names to app-expected header names. "
            "Example: {'Remote-User': 'X-WEBAUTH-USER'}"
        ),
    )


# Generic, proxy-agnostic routing configuration models


class OidcRedirect(BaseModel):
    """OAuth2 redirect (callback) descriptor for a native-OIDC app.

    `path` style emits `https://${HALOS_DOMAIN}<path>`; `port` style emits
    `https://${HALOS_DOMAIN}:<external_port><path>`, where the external port is
    resolved at runtime from the routing port registry.
    """

    style: Literal["path", "port"] = Field(
        description="Redirect URL shape: path-based or external-port-based",
    )
    # Constrained to a URL-path charset: the value is interpolated into the
    # generated prestart's heredoc/echo lines, so shell/heredoc metacharacters
    # (quotes, $, backticks, newlines) must not be expressible.
    path: str = Field(
        min_length=1,
        pattern=r"^/[A-Za-z0-9._~/-]*$",
        description="Callback path (absolute, URL-path characters only)",
    )


# Sources the generator can resolve into a container env var for an OIDC app.
OidcEnvSource = Literal["secret", "issuer", "redirect", "external_port", "client_id"]


class OidcConfig(BaseModel):
    """Declarative OIDC client config for a native-OAuth app.

    Present under `routing.auth.oidc` with `mode: oidc`. The generator turns this
    into the Authelia client snippet, the client-secret provisioning, and the
    container env vars the app consumes — no hand-written prestart needed.
    """

    # client_id flows into a file path and a grep pattern; client_name into a
    # heredoc body. Both are interpolated into root-executed generated bash, so
    # they are charset-constrained to block injection / path traversal.
    client_id: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="OIDC client id (defaults to the app_id when omitted)",
    )
    client_name: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$",
        description="Human-readable client name shown in consent screens",
    )
    scopes: list[str] = Field(
        default=["openid", "profile", "email", "groups"],
        min_length=1,
        description="OAuth2 scopes to request",
    )
    consent_mode: Literal["implicit", "explicit", "pre-configured"] = Field(
        default="implicit",
        description="Authelia consent mode for this client",
    )
    token_endpoint_auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        Field(
            default="client_secret_basic",
            description="Token endpoint auth method the app's OIDC library uses",
        )
    )
    redirect: OidcRedirect = Field(
        description="OAuth2 callback descriptor",
    )
    env: dict[str, OidcEnvSource] = Field(
        default_factory=dict,
        description=(
            "Map of container env var name -> resolved source. Sources: secret "
            "(client secret value), issuer (Authelia issuer URL), redirect "
            "(computed redirect URI), external_port (resolved routing port), "
            "client_id."
        ),
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Scopes are interpolated into the snippet's scope list; keep them simple."""
        for scope in v:
            if not re.match(r"^[a-z0-9_]+$", scope):
                raise ValueError(f"invalid OIDC scope: '{scope}'")
        return v

    @field_validator("env")
    @classmethod
    def validate_env_var_names(
        cls, v: dict[str, OidcEnvSource]
    ) -> dict[str, OidcEnvSource]:
        """Env var names are echoed into runtime.env by generated bash; require
        the POSIX env-name charset so they cannot break out of the echo line."""
        for name in v:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                raise ValueError(f"invalid OIDC env var name: '{name}'")
        return v

    @model_validator(mode="after")
    def validate_external_port_requires_port_style(self) -> "OidcConfig":
        """An env mapping to external_port only resolves when the redirect is
        port-based (the port is otherwise never assigned in the prestart)."""
        if "external_port" in self.env.values() and self.redirect.style != "port":
            raise ValueError(
                "env source 'external_port' requires redirect.style 'port'"
            )
        return self


class RoutingAuth(BaseModel):
    """Authentication configuration for routing.

    Defines how the app authenticates users through the reverse proxy.
    This is a proxy-agnostic format that can be converted to Traefik,
    nginx, or other reverse proxy configurations at runtime.
    """

    mode: Literal["forward_auth", "oidc", "none"] = Field(
        default="forward_auth",
        description="Authentication mode: forward_auth (default), oidc, or none",
    )
    forward_auth: TraefikForwardAuth | None = Field(
        default=None,
        description="Custom forward auth configuration with header mappings",
    )
    oidc: OidcConfig | None = Field(
        default=None,
        description="OIDC client config for native-OAuth apps (with mode: oidc)",
    )

    @model_validator(mode="after")
    def validate_oidc_matches_mode(self) -> "RoutingAuth":
        """`oidc` and `mode: oidc` must agree in both directions, so the prestart
        OIDC section and the is_oidc_app scaffolding (postinst secret-gen, Authelia
        ordering) can never diverge — an oidc block under another mode would write a
        snippet whose secret is never provisioned."""
        if self.mode == "oidc" and self.oidc is None:
            raise ValueError("routing.auth.oidc is required when mode='oidc'")
        if self.mode != "oidc" and self.oidc is not None:
            raise ValueError("routing.auth.oidc is only valid with mode='oidc'")
        return self


class RoutingConfig(BaseModel):
    """Generic, proxy-agnostic routing configuration.

    This configuration format describes routing requirements without
    being tied to a specific reverse proxy implementation. At runtime,
    the reverse proxy (e.g., Traefik) reads this and generates its
    native configuration.
    """

    auth: RoutingAuth | None = Field(
        default=None,
        description="Authentication configuration",
    )
    host_port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Port for host networking apps",
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description=(
            "Backend port for routing. Overrides automatic port detection from "
            "docker-compose. Use when the main web UI port differs from exposed ports."
        ),
    )


class FileWatcherAction(BaseModel):
    """Action to take when a watched path changes.

    At least one of restart_service or script must be specified.
    """

    restart_service: bool = Field(
        default=False,
        description="Restart the main container service when path changes",
    )
    script: str | None = Field(
        default=None,
        description="Script to execute when path changes (absolute path)",
    )

    @field_validator("script")
    @classmethod
    def validate_script_is_absolute(cls, v: str | None) -> str | None:
        """Ensure script path is absolute."""
        if v is not None and not v.startswith("/"):
            raise ValueError(f"script must be an absolute path, got: '{v}'")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_action(self) -> "FileWatcherAction":
        """Ensure at least one action is specified."""
        if not self.restart_service and not self.script:
            raise ValueError(
                "on_change must specify at least one of: restart_service, script"
            )
        return self


class FileWatcher(BaseModel):
    """File watcher configuration for systemd path units.

    Defines a file or directory to watch and the action to take when it changes.
    Each watcher generates a .path unit and corresponding .service unit.
    """

    name: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="Watcher identifier (lowercase alphanumeric and hyphens)",
    )
    watch_path: str = Field(
        min_length=1,
        description="Absolute path to watch for changes",
    )
    watch_type: WatchType = Field(
        default="directory_modified",
        description=(
            "Type of change to watch for: "
            "directory_modified (contents changed), "
            "path_changed (file modified), "
            "path_exists (file/dir created)"
        ),
    )
    on_change: FileWatcherAction = Field(
        description="Action to take when the watched path changes",
    )

    @field_validator("watch_path")
    @classmethod
    def validate_watch_path_is_absolute(cls, v: str) -> str:
        """Ensure watch_path is absolute."""
        if not v.startswith("/"):
            raise ValueError(f"watch_path must be an absolute path, got: '{v}'")
        return v


class SourceMetadata(BaseModel):
    """Metadata about the source of a converted app.

    Tracks the origin and conversion details for auto-converted packages
    (e.g., from CasaOS, Runtipi). Manual packages do not have source_metadata.
    """

    type: str = Field(
        min_length=1,
        description="Source type identifier (e.g., 'casaos', 'runtipi')",
    )
    app_id: str = Field(min_length=1, description="App identifier in source system")
    source_url: str = Field(min_length=1, description="URL to source repository")
    upstream_hash: str = Field(
        min_length=1,
        description="SHA256 hash of source file(s) for change detection",
    )
    conversion_timestamp: str = Field(
        description="ISO 8601 timestamp of when conversion was performed"
    )

    # Allow source-specific extra fields
    model_config = ConfigDict(extra="allow")


class PackageMetadata(BaseModel):
    """Pydantic model for package metadata validation.

    Validates metadata.yaml files for container application packages.
    Ensures all required fields are present with correct formats and
    enforces Debian packaging conventions.

    Note: package_name is computed at build time from app_id and prefix.
    """

    model_config = ConfigDict(extra="forbid")

    # Required identity fields
    name: str = Field(min_length=1, description="Human-readable application name")
    app_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="Base application identifier (lowercase alphanumeric and hyphens)",
    )
    version: str = Field(
        min_length=1,
        description="Package version (semver, date-based, CalVer, etc. + optional Debian revision)",
    )

    # Optional version field
    upstream_version: str | None = Field(
        None, description="Original application version"
    )

    # Description fields
    description: str = Field(
        max_length=80, description="Short description for package lists"
    )
    long_description: str | None = Field(
        None, description="Detailed multi-line description"
    )

    # URLs and assets
    homepage: HttpUrl | None = Field(None, description="Project homepage URL")
    icon: str | None = Field(None, description="Relative path to icon file")
    screenshots: list[str] | None = Field(
        None, description="Array of screenshot filenames"
    )

    # Maintainer info
    maintainer: str = Field(
        pattern=r"^[^<>]+<[^@]+@[^>]+>$",
        description="Package maintainer (Name <email>)",
    )
    license: str = Field(description="SPDX license identifier")

    # Debian classification
    tags: list[str] = Field(min_length=1, description="Debian tags (debtags)")
    # Official Debian sections from Policy Manual 4.7.2.0
    # Reference: https://www.debian.org/doc/debian-policy/ch-archive.html
    debian_section: Literal[
        "admin",
        "cli-mono",
        "comm",
        "database",
        "debug",
        "devel",
        "doc",
        "editors",
        "education",
        "electronics",
        "embedded",
        "fonts",
        "games",
        "gnome",
        "gnu-r",
        "gnustep",
        "graphics",
        "hamradio",
        "haskell",
        "httpd",
        "interpreters",
        "introspection",
        "java",
        "javascript",
        "kde",
        "kernel",
        "libdevel",
        "libs",
        "lisp",
        "localization",
        "mail",
        "math",
        "metapackages",
        "misc",
        "net",
        "news",
        "ocaml",
        "oldlibs",
        "otherosfs",
        "perl",
        "php",
        "python",
        "ruby",
        "rust",
        "science",
        "shells",
        "sound",
        "tasks",
        "tex",
        "text",
        "utils",
        "vcs",
        "video",
        "web",
        "x11",
        "xfce",
        "zope",
    ] = Field(description="Debian section for package classification")
    architecture: Literal["all", "amd64", "arm64", "armhf"] = Field(
        description="Target architecture"
    )

    # Dependencies
    depends: list[str] | None = Field(
        None, description="Package dependencies (Depends)"
    )
    recommends: list[str] | None = Field(
        None, description="Recommended packages (Recommends)"
    )
    suggests: list[str] | None = Field(
        None, description="Suggested packages (Suggests)"
    )

    # Package relationships
    provides: list[str] | None = Field(
        None,
        description=(
            "Virtual packages this package provides (e.g., ['halos-reverse-proxy']). "
            "Allows other packages to depend on a capability rather than a specific implementation."
        ),
    )
    conflicts: list[str] | None = Field(
        None,
        description=(
            "Packages that conflict with this one (e.g., ['halos-reverse-proxy']). "
            "Cannot be installed alongside conflicting packages."
        ),
    )
    breaks: list[str] | None = Field(
        None,
        description=(
            "Packages this package breaks (e.g., ['homarr-container-adapter (<< 0.4.6)']). "
            "Conditional: only enforced when the named package is installed, in which "
            "case the named version range cannot coexist with this one. Auto-injected "
            "entries for the Homarr stack (added when routing + web_ui + visible is set) "
            "are prepended to this list."
        ),
    )

    # Web UI configuration
    web_ui: WebUI | None = Field(None, description="Web interface configuration")

    # Dashboard layout configuration
    layout: Layout | None = Field(
        None, description="Homarr dashboard layout configuration"
    )

    # Routing configuration (generic format)
    routing: RoutingConfig | None = Field(
        None, description="Generic routing configuration"
    )

    # System binaries to install to /usr/bin/
    # These are scripts from assets/ that should be available system-wide
    system_bin: list[str] | None = Field(
        None,
        description="List of asset files to install to /usr/bin/ (e.g., ['configure-container-routing'])",
    )

    # File watchers for systemd path units
    file_watchers: list[FileWatcher] | None = Field(
        None,
        description=(
            "File watchers that trigger actions when paths change. "
            "Each watcher generates a systemd .path unit."
        ),
    )

    @field_validator("file_watchers")
    @classmethod
    def validate_unique_watcher_names(
        cls, v: list[FileWatcher] | None
    ) -> list[FileWatcher] | None:
        """Ensure all file watcher names are unique."""
        if v is None:
            return v
        names = [w.name for w in v]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate file_watcher names: {', '.join(set(duplicates))}"
            )
        return v

    # Default configuration
    default_config: dict[str, str] | None = Field(
        None, description="Default environment variables"
    )

    # Source tracking for converted apps
    source_metadata: SourceMetadata | None = Field(
        None,
        description="Metadata for auto-converted apps (None for manual apps)",
    )

    @field_validator("tags")
    @classmethod
    def validate_required_tag(cls, v: list[str]) -> list[str]:
        """Validate that tags include role::container-app."""
        if "role::container-app" not in v:
            raise ValueError("Tags must include 'role::container-app'")
        return v

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version is compatible with Debian package versioning.

        Uses dpkg --compare-versions to ensure the version is valid and comparable.
        Supports semantic versioning, date-based, CalVer, and hybrid schemes.
        """
        # Check basic format constraints
        if not v or v.isspace():
            raise ValueError("Version cannot be empty or whitespace")

        # Validate using dpkg --compare-versions
        # We compare the version to itself to check if it's a valid version string
        try:
            result = subprocess.run(
                ["dpkg", "--compare-versions", v, "eq", v],
                capture_output=True,
                check=False,
                timeout=1,
                text=True,
            )
            # Check for warnings in stderr (indicates bad syntax)
            # dpkg prints warnings like "version 'v1.0' has bad syntax"
            if result.stderr and (
                "bad syntax" in result.stderr or "error" in result.stderr.lower()
            ):
                raise ValueError(
                    f"Invalid Debian version format: '{v}'. "
                    "Version must be valid according to Debian policy. "
                    "Examples: 1.2.3, 20250113, 2025.01.13, 5.8.4+git20250113"
                )
            # Exit code 0 means versions are equal (valid format)
            if result.returncode != 0:
                raise ValueError(
                    f"Invalid Debian version format: '{v}'. "
                    "Version must be valid according to Debian policy. "
                    "Examples: 1.2.3, 20250113, 2025.01.13, 5.8.4+git20250113"
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # If dpkg is not available or times out, do basic validation
            # Allow alphanumeric, dots, dashes, plus signs, tildes, and colons
            import re

            if not re.match(r"^[0-9][0-9a-zA-Z.+~:-]*$", v):
                raise ValueError(
                    f"Invalid version format: '{v}'. "
                    "Version must start with a digit and contain only "
                    "alphanumeric characters, dots, dashes, plus signs, tildes, and colons"
                ) from e

        return v
