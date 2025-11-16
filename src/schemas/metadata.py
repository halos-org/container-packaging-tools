"""Pydantic models for validating metadata.yaml files."""

import subprocess
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


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


class PackageMetadata(BaseModel):
    """Pydantic model for package metadata validation.

    Validates metadata.yaml files for container application packages.
    Ensures all required fields are present with correct formats and
    enforces Debian packaging conventions.
    """

    # Required identity fields
    name: str = Field(min_length=1, description="Human-readable application name")
    package_name: str = Field(
        pattern=r"^[a-z0-9][a-z0-9+.-]+$",
        description="Debian package name (must end with -container)",
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

    # Default configuration
    default_config: dict[str, str] | None = Field(
        None, description="Default environment variables"
    )

    @field_validator("package_name")
    @classmethod
    def validate_package_name_suffix(cls, v: str) -> str:
        """Validate that package name ends with -container suffix."""
        if not v.endswith("-container"):
            raise ValueError("Package name must end with '-container'")
        return v

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
