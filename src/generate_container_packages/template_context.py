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
        "service": _build_service_context(package_name, metadata),
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
    package_name: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    """Build systemd service context.

    Args:
        package_name: Debian package name
        metadata: Parsed metadata.yaml contents

    Returns:
        Dictionary with systemd service configuration
    """
    return {
        "name": f"{package_name}.service",
        "description": f"{metadata['name']} Container",
        "working_directory": f"/var/lib/container-apps/{package_name}",
        "env_file": f"/etc/container-apps/{package_name}/.env",
    }


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
