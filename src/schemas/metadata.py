"""Pydantic models for validating metadata.yaml files."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class WebUI(BaseModel):
    """Web UI configuration for the container application."""

    enabled: bool = Field(description="Whether web UI is available")
    path: Optional[str] = Field(None, description="URL path to access the web UI")
    port: Optional[int] = Field(
        None, ge=1, le=65535, description="Port the web UI listens on"
    )
    protocol: Optional[Literal["http", "https"]] = Field(
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
        pattern=r"^[0-9]+\.[0-9]+(\.[0-9]+)?(-[0-9]+)?$",
        description="Package version (semver + optional Debian revision)",
    )

    # Optional version field
    upstream_version: Optional[str] = Field(
        None, description="Original application version"
    )

    # Description fields
    description: str = Field(
        max_length=80, description="Short description for package lists"
    )
    long_description: Optional[str] = Field(
        None, description="Detailed multi-line description"
    )

    # URLs and assets
    homepage: Optional[HttpUrl] = Field(None, description="Project homepage URL")
    icon: Optional[str] = Field(None, description="Relative path to icon file")
    screenshots: Optional[list[str]] = Field(
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
    debian_section: Literal[
        "admin",
        "comm",
        "database",
        "devel",
        "doc",
        "editors",
        "games",
        "gnome",
        "graphics",
        "kde",
        "mail",
        "net",
        "news",
        "science",
        "sound",
        "text",
        "utils",
        "web",
        "x11",
    ] = Field(description="Debian section for package classification")
    architecture: Literal["all", "amd64", "arm64", "armhf"] = Field(
        description="Target architecture"
    )

    # Dependencies
    depends: Optional[list[str]] = Field(
        None, description="Package dependencies (Depends)"
    )
    recommends: Optional[list[str]] = Field(
        None, description="Recommended packages (Recommends)"
    )
    suggests: Optional[list[str]] = Field(
        None, description="Suggested packages (Suggests)"
    )

    # Web UI configuration
    web_ui: Optional[WebUI] = Field(None, description="Web interface configuration")

    # Default configuration
    default_config: Optional[dict[str, str]] = Field(
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
