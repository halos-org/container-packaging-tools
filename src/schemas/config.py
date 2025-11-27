"""Pydantic models for validating config.yml configuration schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ConfigField(BaseModel):
    """Configuration field definition.

    Defines a single configurable parameter for the container application.
    Field IDs must be valid environment variable names (UPPER_SNAKE_CASE).
    """

    id: str = Field(
        pattern=r"^[A-Z][A-Z0-9_]*$",
        description="Field ID (environment variable name in UPPER_SNAKE_CASE)",
    )
    label: str = Field(description="Human-readable field label")
    type: Literal["string", "integer", "boolean", "enum", "path", "password"] = Field(
        description="Field data type"
    )
    default: Any = Field(description="Default value for the field")
    required: bool = Field(description="Whether the field is required")
    min: int | None = Field(
        None, description="Minimum value (for integer/string types)"
    )
    max: int | None = Field(
        None, description="Maximum value (for integer/string types)"
    )
    options: list[str] | None = Field(
        None, description="Valid options (required for enum type)"
    )
    description: str | None = Field(None, description="Help text for the field")

    @model_validator(mode="after")
    def validate_enum_options(self) -> "ConfigField":
        """Validate that enum type has options."""
        if self.type == "enum" and (self.options is None or len(self.options) == 0):
            raise ValueError("Enum type must have options defined")
        return self


class ConfigGroup(BaseModel):
    """Configuration group containing related fields.

    Groups fields into logical categories for better organization
    in the UI. Group IDs must use lowercase_snake_case.
    """

    id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Group ID (lowercase_snake_case)",
    )
    label: str = Field(description="Human-readable group label")
    description: str | None = Field(None, description="Help text for the group")
    fields: list[ConfigField] = Field(min_length=1, description="Fields in this group")


class ConfigSchema(BaseModel):
    """Configuration schema for container application.

    Defines the user-configurable parameters for a container application.
    Used to generate configuration forms in the Cockpit UI and validate
    environment variable values.
    """

    version: str = Field(
        pattern=r"^1\.0$", description="Schema version (currently 1.0)"
    )
    groups: list[ConfigGroup] = Field(description="Configuration groups (can be empty)")
