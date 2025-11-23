"""Input validation logic using Pydantic models."""

from pathlib import Path
from typing import Any, NamedTuple

import yaml
from pydantic import ValidationError

from schemas.config import ConfigSchema
from schemas.metadata import PackageMetadata


class ValidationWarning(NamedTuple):
    """Warning message from validation."""

    file: str
    message: str
    suggestion: str


class ValidationResult(NamedTuple):
    """Result of input directory validation."""

    success: bool
    metadata: PackageMetadata | None = None
    config: ConfigSchema | None = None
    compose: dict[str, Any] | None = None
    errors: list[str] = []
    warnings: list[ValidationWarning] = []


def validate_input_directory(path: Path) -> ValidationResult:
    """Validate input directory contains all required files and valid data.

    Args:
        path: Path to input directory

    Returns:
        ValidationResult with success flag, parsed data, and any errors/warnings
    """
    errors: list[str] = []
    warnings: list[ValidationWarning] = []

    # Check required files exist
    if not path.is_dir():
        return ValidationResult(
            success=False,
            errors=[f"Input path is not a directory: {path}"],
        )

    required_files = {
        "metadata.yaml": path / "metadata.yaml",
        "docker-compose.yml": path / "docker-compose.yml",
        "config.yml": path / "config.yml",
    }

    for name, file_path in required_files.items():
        if not file_path.exists():
            errors.append(f"Required file not found: {name}")

    if errors:
        return ValidationResult(success=False, errors=errors)

    # Validate each file
    try:
        metadata = validate_metadata(required_files["metadata.yaml"])
    except ValidationError as e:
        errors.append(format_pydantic_error("metadata.yaml", e))
        return ValidationResult(success=False, errors=errors)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in metadata.yaml: {e}")
        return ValidationResult(success=False, errors=errors)

    try:
        config = validate_config(required_files["config.yml"])
    except ValidationError as e:
        errors.append(format_pydantic_error("config.yml", e))
        return ValidationResult(success=False, errors=errors)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in config.yml: {e}")
        return ValidationResult(success=False, errors=errors)

    try:
        compose = validate_compose(required_files["docker-compose.yml"])
        compose_warnings = check_compose_warnings(compose)
        warnings.extend(compose_warnings)
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in docker-compose.yml: {e}")
        return ValidationResult(success=False, errors=errors)
    except ValueError as e:
        errors.append(f"Invalid docker-compose.yml: {e}")
        return ValidationResult(success=False, errors=errors)

    # Cross-validation checks
    cross_warnings = cross_validate(path, metadata, config, compose)
    warnings.extend(cross_warnings)

    return ValidationResult(
        success=True,
        metadata=metadata,
        config=config,
        compose=compose,
        warnings=warnings,
    )


def validate_metadata(path: Path) -> PackageMetadata:
    """Validate metadata.yaml file.

    Args:
        path: Path to metadata.yaml

    Returns:
        Validated PackageMetadata object

    Raises:
        ValidationError: If validation fails
        yaml.YAMLError: If YAML is invalid
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return PackageMetadata.model_validate(data)


def validate_config(path: Path) -> ConfigSchema:
    """Validate config.yml file.

    Args:
        path: Path to config.yml

    Returns:
        Validated ConfigSchema object

    Raises:
        ValidationError: If validation fails
        yaml.YAMLError: If YAML is invalid
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ConfigSchema.model_validate(data)


def validate_compose(path: Path) -> dict[str, Any]:
    """Validate docker-compose.yml file.

    Args:
        path: Path to docker-compose.yml

    Returns:
        Parsed docker-compose data

    Raises:
        yaml.YAMLError: If YAML is invalid
        ValueError: If compose file is invalid
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("docker-compose.yml must be a YAML object")

    # Check for version field (optional in Docker Compose v2+)
    version = data.get("version")
    if version:
        # Parse version (may be string like "3.8" or float like 3.8)
        try:
            version_num = float(str(version))
            if version_num < 3.8:
                raise ValueError(
                    f"docker-compose.yml version {version} is too old, requires version 3.8 or newer"
                )
        except (ValueError, TypeError):
            raise ValueError(f"Invalid docker-compose.yml version: {version}") from None

    # Check for services
    if "services" not in data:
        raise ValueError("docker-compose.yml missing 'services' section")

    if not data["services"]:
        raise ValueError("docker-compose.yml has no services defined")

    return data


def check_compose_warnings(compose: dict[str, Any]) -> list[ValidationWarning]:
    """Check docker-compose file for potential issues.

    Args:
        compose: Parsed docker-compose data

    Returns:
        List of validation warnings
    """
    warnings: list[ValidationWarning] = []

    services = compose.get("services", {})

    for service_name, service in services.items():
        # Check for restart policy
        restart = service.get("restart")
        if restart and restart != "no":
            warnings.append(
                ValidationWarning(
                    file="docker-compose.yml",
                    message=f"Service '{service_name}' has restart policy '{restart}'",
                    suggestion="Set restart: 'no' - systemd manages service lifecycle",
                )
            )

    # Check for named volumes
    volumes = compose.get("volumes", {})
    if volumes:
        warnings.append(
            ValidationWarning(
                file="docker-compose.yml",
                message="Named volumes are defined",
                suggestion="Use bind mounts instead for persistent data "
                "(paths under /var/lib/container-apps/)",
            )
        )

    return warnings


def cross_validate(
    base_path: Path,
    metadata: PackageMetadata,
    config: ConfigSchema,
    compose: dict[str, Any],
) -> list[ValidationWarning]:
    """Perform cross-file validation checks.

    Args:
        base_path: Base directory path
        metadata: Validated metadata
        config: Validated config schema
        compose: Parsed docker-compose data

    Returns:
        List of validation warnings
    """
    warnings: list[ValidationWarning] = []

    # Check referenced icon file exists
    if metadata.icon:
        icon_path = base_path / metadata.icon
        if not icon_path.exists():
            warnings.append(
                ValidationWarning(
                    file="metadata.yaml",
                    message=f"Referenced icon file not found: {metadata.icon}",
                    suggestion=f"Create icon file at {metadata.icon} or remove icon field",
                )
            )

    # Check referenced screenshot files exist
    if metadata.screenshots:
        for screenshot in metadata.screenshots:
            screenshot_path = base_path / screenshot
            if not screenshot_path.exists():
                warnings.append(
                    ValidationWarning(
                        file="metadata.yaml",
                        message=f"Referenced screenshot file not found: {screenshot}",
                        suggestion=f"Create screenshot file at {screenshot} "
                        f"or remove from screenshots list",
                    )
                )

    # Check config field IDs are present in default_config
    if metadata.default_config:
        config_field_ids = set()
        for group in config.groups:
            for field in group.fields:
                config_field_ids.add(field.id)

        default_config_ids = set(metadata.default_config.keys())

        # Warn about config fields without defaults
        missing_defaults = config_field_ids - default_config_ids
        for field_id in missing_defaults:
            warnings.append(
                ValidationWarning(
                    file="config.yml",
                    message=f"Field '{field_id}' has no default value in metadata.yaml",
                    suggestion=f"Add '{field_id}' to default_config in metadata.yaml",
                )
            )

        # Warn about default_config entries not in config schema
        extra_defaults = default_config_ids - config_field_ids
        for field_id in extra_defaults:
            warnings.append(
                ValidationWarning(
                    file="metadata.yaml",
                    message=f"default_config entry '{field_id}' not defined in config.yml",
                    suggestion=f"Add field definition for '{field_id}' in config.yml "
                    f"or remove from default_config",
                )
            )

    return warnings


def format_pydantic_error(filename: str, error: ValidationError) -> str:
    """Format Pydantic ValidationError for CLI output.

    Args:
        filename: Name of file being validated
        error: Pydantic ValidationError

    Returns:
        Formatted error message string
    """
    errors = error.errors()
    if len(errors) == 1:
        e = errors[0]
        field_path = " -> ".join(str(loc) for loc in e["loc"])
        return (
            f"Validation error in {filename}:\n"
            f"  Field: {field_path}\n"
            f"  Error: {e['msg']}\n"
            f"  Input: {e.get('input', 'N/A')}"
        )
    else:
        lines = [f"Validation errors in {filename}:"]
        for e in errors:
            field_path = " -> ".join(str(loc) for loc in e["loc"])
            lines.append(f"  - {field_path}: {e['msg']}")
        return "\n".join(lines)
