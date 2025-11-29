"""Template context builder for Jinja2 rendering."""

from pathlib import Path
from typing import Any

from generate_container_packages.loader import AppDefinition


def build_context(app_def: AppDefinition) -> dict[str, Any]:
    """Build template context from app definition.

    Args:
        app_def: Application definition with all parsed data

    Returns:
        Dictionary containing all template variables

    The context structure follows the format expected by all Jinja2 templates,
    with properly formatted strings for Debian packaging requirements.
    """
    metadata = app_def.metadata
    package_name = metadata["package_name"]

    context = {
        "package": _build_package_context(metadata),
        "service": _build_service_context(package_name, metadata, app_def.compose),
        "paths": _build_paths(package_name),
        "web_ui": metadata.get("web_ui", {}),
        "default_config": metadata.get("default_config", {}),
        "timestamp": app_def.timestamp,
        "timestamp_rfc2822": app_def.timestamp_rfc2822,
        "date_only": app_def.date_only,
        "tool_version": app_def.tool_version,
        "has_icon": app_def.icon_path is not None,
        "icon_extension": _get_icon_extension(app_def.icon_path),
        "has_screenshots": len(app_def.screenshot_paths) > 0,
        "screenshot_count": len(app_def.screenshot_paths),
    }

    return context


def _build_package_context(metadata: dict[str, Any]) -> dict[str, Any]:
    """Build package-level context from metadata.

    Args:
        metadata: Parsed metadata.yaml contents

    Returns:
        Dictionary with package metadata formatted for Debian control files
    """
    return {
        "name": metadata["package_name"],
        "version": metadata["version"],
        "architecture": metadata["architecture"],
        "section": metadata["debian_section"],
        "description": metadata["description"],
        "long_description": format_long_description(
            metadata.get("long_description", "")
        ),
        "homepage": metadata.get("homepage", ""),
        "maintainer": metadata["maintainer"],
        "license": metadata["license"],
        "tags": format_dependencies(metadata.get("tags", [])),
        "depends": format_dependencies(metadata.get("depends", [])),
        "recommends": format_dependencies(metadata.get("recommends", [])),
        "suggests": format_dependencies(metadata.get("suggests", [])),
        # Additional fields for templates
        "human_name": metadata["name"],
        "upstream_version": metadata.get("upstream_version", metadata["version"]),
    }


def _build_service_context(
    package_name: str, metadata: dict[str, Any], compose: dict[str, Any]
) -> dict[str, Any]:
    """Build systemd service context.

    Args:
        package_name: Debian package name
        metadata: Parsed metadata.yaml contents
        compose: Parsed docker-compose.yml contents

    Returns:
        Dictionary with systemd service configuration
    """
    return {
        "name": f"{package_name}.service",
        "description": f"{metadata['name']} Container",
        "working_directory": f"/var/lib/container-apps/{package_name}",
        "env_defaults_file": f"/etc/container-apps/{package_name}/env.defaults",
        "env_file": f"/etc/container-apps/{package_name}/env",
        "volume_directories": _extract_volume_directories(compose),
    }


def _extract_volume_directories(compose: dict[str, Any]) -> list[str]:
    """Extract volume source directories from docker-compose.yml.

    Parse the docker-compose services and extract bind mount source paths that
    should be created before starting the container. Only extracts paths that:
    1. Are bind mounts (not named volumes)
    2. Use environment variable references (like ${CONTAINER_DATA_ROOT}/...)
    3. Don't reference system paths (like /dev, /sys, etc.)

    Args:
        compose: Parsed docker-compose.yml contents

    Returns:
        List of volume source paths (may contain env var references)
        Empty list if no volumes or all are named volumes
    """
    directories = []

    # Get all services from compose file
    services = compose.get("services", {})

    for service_name, service_config in services.items():
        volumes = service_config.get("volumes", [])

        for volume in volumes:
            # Handle different volume formats
            if isinstance(volume, dict):
                # Long format: {source: ..., target: ..., type: bind}
                if volume.get("type") == "bind":
                    source = volume.get("source", "")
                    if source and _is_bindable_path(source):
                        directories.append(source)
            elif isinstance(volume, str):
                # Short format: "source:target" or "source:target:ro"
                parts = volume.split(":")
                if len(parts) >= 2:
                    source = parts[0]
                    if source and _is_bindable_path(source):
                        directories.append(source)

    return directories


def _is_bindable_path(path: str) -> bool:
    """Check if a path should have its directory auto-created.

    Args:
        path: Volume source path (may contain env vars)

    Returns:
        True if path should be created, False otherwise
    """
    # Skip named volumes (no slashes)
    if "/" not in path:
        return False

    # Skip system paths that should not be created
    system_prefixes = ("/dev", "/sys", "/proc", "/run", "/tmp")
    for prefix in system_prefixes:
        if path.startswith(prefix):
            return False

    # Include paths with environment variables (will be expanded at runtime)
    if "$" in path or path.startswith("/var/lib/container-apps"):
        return True

    return False


def _build_paths(package_name: str) -> dict[str, str]:
    """Build standard installation paths.

    Args:
        package_name: Debian package name

    Returns:
        Dictionary with standard paths for package installation
    """
    return {
        "lib": f"/var/lib/container-apps/{package_name}",
        "etc": f"/etc/container-apps/{package_name}",
        "systemd": "/etc/systemd/system",
        "pixmaps": "/usr/share/pixmaps",
        "metainfo": "/usr/share/metainfo",
        "doc": f"/usr/share/doc/{package_name}",
    }


def _get_icon_extension(icon_path: Path | None) -> str:
    """Get icon file extension.

    Args:
        icon_path: Path to icon file (or None)

    Returns:
        File extension (e.g., 'svg', 'png') or empty string if no icon
    """
    if icon_path is None:
        return ""
    return icon_path.suffix.lstrip(".")


def format_long_description(text: str) -> str:
    """Format long description for Debian control file.

    Debian control file format requires:
    - First line is short description (handled separately in control template)
    - Subsequent lines must start with a space
    - Empty lines must be represented as a single space and period " ."

    Args:
        text: Long description text (may contain newlines)

    Returns:
        Formatted text with proper Debian control file formatting
    """
    if not text:
        return ""

    lines = text.strip().split("\n")
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if line:
            # Non-empty line: add leading space
            formatted_lines.append(f" {line}")
        else:
            # Empty line: use " ." notation
            formatted_lines.append(" .")

    return "\n".join(formatted_lines)


def format_dependencies(deps: list[str] | None) -> str:
    """Format dependency list for Debian control file.

    Args:
        deps: List of dependency package names

    Returns:
        Comma-separated dependency string, or empty string if no dependencies
    """
    if not deps:
        return ""
    return ", ".join(deps)
