"""Pydantic models for CasaOS application format.

These models represent the CasaOS application definition structure,
which uses Docker Compose with x-casaos metadata extensions.
The models support flexible validation to handle undocumented fields
while ensuring required data is present.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CasaOSEnvVar(BaseModel):
    """Environment variable definition in CasaOS format.

    CasaOS defines environment variables with optional metadata for
    user configuration. This model captures both the variable value
    and its UI presentation metadata.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, description="Environment variable name")
    default: str = Field(description="Default value for the variable")
    label: str | None = Field(None, description="Human-readable label for UI")
    description: str | None = Field(None, description="Help text explaining the variable")
    type: str | None = Field(
        None,
        description="CasaOS type hint (e.g., 'number', 'text', 'password')",
    )


class CasaOSPort(BaseModel):
    """Port mapping definition in CasaOS format.

    Defines how container ports are exposed to the host system.
    """

    model_config = ConfigDict(extra="allow")

    container: int = Field(ge=1, le=65535, description="Container port number")
    host: int = Field(ge=1, le=65535, description="Host port number")
    protocol: Literal["tcp", "udp"] | None = Field(None, description="Protocol (tcp or udp)")
    description: str | None = Field(None, description="Port description")


class CasaOSVolume(BaseModel):
    """Volume mount definition in CasaOS format.

    Defines how host directories/files are mounted into the container.
    """

    model_config = ConfigDict(extra="allow")

    container: str = Field(min_length=1, description="Container mount path")
    host: str = Field(min_length=1, description="Host path")
    mode: str | None = Field(None, description="Mount mode (e.g., 'ro', 'rw')")
    description: str | None = Field(None, description="Volume description")


class CasaOSService(BaseModel):
    """Service definition in CasaOS format.

    Represents a single container service within a CasaOS application.
    CasaOS apps may have one or more services (e.g., app + database).
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, description="Service name")
    image: str = Field(min_length=1, description="Docker image reference")
    environment: list[CasaOSEnvVar] = Field(
        default_factory=list,
        description="Environment variables for this service",
    )
    ports: list[CasaOSPort] = Field(
        default_factory=list,
        description="Port mappings for this service",
    )
    volumes: list[CasaOSVolume] = Field(
        default_factory=list,
        description="Volume mounts for this service",
    )
    command: list[str] | str | None = Field(
        None,
        description="Command to run in container",
    )
    entrypoint: list[str] | str | None = Field(
        None,
        description="Entrypoint override",
    )


class CasaOSApp(BaseModel):
    """Complete CasaOS application definition.

    Represents a full CasaOS app with all metadata and service definitions.
    CasaOS stores this information in docker-compose.yml with x-casaos extensions.
    """

    model_config = ConfigDict(extra="allow")

    # Core identity
    id: str = Field(min_length=1, description="Unique app identifier")
    name: str = Field(min_length=1, description="Display name")
    tagline: str = Field(min_length=1, description="Short tagline")
    description: str = Field(min_length=1, description="Full description")
    category: str = Field(min_length=1, description="CasaOS category")

    # Optional metadata
    developer: str | None = Field(None, description="Developer/author name")
    homepage: str | None = Field(None, description="Project homepage URL")
    icon: str | None = Field(None, description="Icon URL")
    screenshots: list[str] = Field(default_factory=list, description="Screenshot URLs")
    tags: list[str] = Field(default_factory=list, description="Tags for searching")

    # Service definitions (at least one required)
    services: list[CasaOSService] = Field(
        min_length=1,
        description="Container services for this app",
    )


class ConversionContext(BaseModel):
    """Context object tracking the state of a conversion operation.

    Used to collect warnings, errors, and metadata during the conversion
    process. Enables detailed reporting and debugging.
    """

    model_config = ConfigDict(extra="allow")

    # Source tracking
    source_format: str = Field(min_length=1, description="Source format name (e.g., 'casaos')")
    app_id: str = Field(min_length=1, description="ID of app being converted")

    # State tracking
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings during conversion",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors encountered during conversion",
    )
    downloaded_assets: list[str] = Field(
        default_factory=list,
        description="Paths to successfully downloaded assets",
    )

    # Additional metadata can be added via extra="allow"
