"""Pydantic models for validating metadata.yaml files."""

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


class TraefikOIDC(BaseModel):
    """OIDC configuration for apps with native OpenID Connect support.

    When auth=oidc, the app handles authentication directly with Authelia
    instead of using Forward Auth middleware.
    """

    client_name: str = Field(
        min_length=1,
        description="Human-readable client name shown in consent screens",
    )
    scopes: list[str] = Field(
        default=["openid", "profile", "email"],
        min_length=1,
        description="OAuth2 scopes to request",
    )
    redirect_path: str = Field(
        default="/callback",
        description="OAuth2 callback path (relative to app root)",
    )
    consent_mode: Literal["implicit", "explicit", "pre-configured"] = Field(
        default="implicit",
        description="Authelia consent mode for this client",
    )


class TraefikConfig(BaseModel):
    """Traefik routing and SSO configuration for container apps.

    Controls how the app integrates with the Traefik reverse proxy and
    Authelia authentication system.
    """

    subdomain: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$|^$",
        description=(
            "Subdomain for routing (defaults to app_id). "
            "Must be lowercase alphanumeric with hyphens, or empty string for root domain."
        ),
    )
    auth: Literal["forward_auth", "oidc", "none"] = Field(
        default="forward_auth",
        description="Authentication mode: forward_auth (default), oidc, or none",
    )
    forward_auth: TraefikForwardAuth | None = Field(
        default=None,
        description="Custom forward auth configuration (optional, uses default if not specified)",
    )
    oidc: TraefikOIDC | None = Field(
        default=None,
        description="OIDC client configuration (required if auth=oidc)",
    )
    host_port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Port for host networking apps (Traefik routes to host.docker.internal:port)",
    )

    @model_validator(mode="after")
    def validate_oidc_required(self) -> "TraefikConfig":
        """Ensure oidc section is present when auth=oidc."""
        if self.auth == "oidc" and self.oidc is None:
            raise ValueError("oidc config required when auth='oidc'")
        return self


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

    # Web UI configuration
    web_ui: WebUI | None = Field(None, description="Web interface configuration")

    # Dashboard layout configuration
    layout: Layout | None = Field(
        None, description="Homarr dashboard layout configuration"
    )

    # Traefik routing and SSO configuration
    traefik: TraefikConfig | None = Field(
        None, description="Traefik routing and SSO configuration"
    )

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
