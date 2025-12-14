"""File loading and data model construction."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from generate_container_packages import __version__
from generate_container_packages.naming import (
    compute_package_name,
    expand_dependencies,
)

logger = logging.getLogger(__name__)


class AppDefinition:
    """Unified data model for container application definition.

    Contains all parsed data from input files plus computed fields
    for use in template rendering and package building.
    """

    def __init__(
        self,
        metadata: dict[str, Any],
        compose: dict[str, Any],
        config: dict[str, Any],
        input_dir: Path,
        icon_path: Path | None = None,
        screenshot_paths: list[Path] | None = None,
    ):
        """Initialize AppDefinition.

        Args:
            metadata: Parsed metadata.yaml contents
            compose: Parsed docker-compose.yml contents
            config: Parsed config.yml contents
            input_dir: Path to input directory
            icon_path: Path to icon file (if exists)
            screenshot_paths: List of paths to screenshot files
        """
        self.metadata = metadata
        self.compose = compose
        self.config = config
        self.input_dir = input_dir
        self.icon_path = icon_path
        self.screenshot_paths = screenshot_paths or []

        # Computed fields
        now = datetime.now(UTC)
        self.timestamp = now.isoformat()  # ISO 8601 for general use

        # RFC 2822 for Debian changelog (with colon in timezone offset)
        tz_str = now.strftime("%z")
        self.timestamp_rfc2822 = (
            now.strftime("%a, %d %b %Y %H:%M:%S ") + tz_str[:3] + ":" + tz_str[3:]
        )

        self.date_only = now.strftime("%Y-%m-%d")  # YYYY-MM-DD for AppStream
        self.tool_version = __version__


def load_input_files(directory: Path, prefix: str | None = None) -> AppDefinition:
    """Load all input files from directory into unified data model.

    Args:
        directory: Path to input directory
        prefix: Optional package name prefix (e.g., "marine", "halos", "casaos")

    Returns:
        AppDefinition with all loaded data, including computed package_name

    Raises:
        FileNotFoundError: If required file is missing
        yaml.YAMLError: If YAML parsing fails
    """
    # Load required files
    metadata = load_yaml(directory / "metadata.yaml")
    compose = load_yaml(directory / "docker-compose.yml")
    config = load_yaml(directory / "config.yml")

    # Reject deprecated package_name field
    if "package_name" in metadata:
        raise ValueError(
            "metadata.yaml contains invalid 'package_name' field. "
            "This field has been removed from the schema. "
            "Use 'app_id' to specify the base application identifier."
        )

    # Compute package_name from app_id and prefix
    metadata["package_name"] = compute_package_name(
        metadata["app_id"],
        prefix=prefix,
    )

    # Expand @ references in dependency fields
    if metadata.get("depends"):
        metadata["depends"] = expand_dependencies(metadata["depends"], prefix=prefix)
    if metadata.get("recommends"):
        metadata["recommends"] = expand_dependencies(
            metadata["recommends"], prefix=prefix
        )
    if metadata.get("suggests"):
        metadata["suggests"] = expand_dependencies(metadata["suggests"], prefix=prefix)

    # Find optional icon file (SVG or PNG)
    icon_path = None
    icon_patterns = ["icon.svg", "icon.png"]
    icon_files = find_optional_files(directory, icon_patterns)
    if icon_files:
        # Prefer SVG over PNG
        svg_icons = [f for f in icon_files if f.suffix == ".svg"]
        icon_path = svg_icons[0] if svg_icons else icon_files[0]

    # Find optional screenshot files
    screenshot_patterns = ["screenshot*.png", "screenshot*.jpg"]
    screenshot_paths = find_optional_files(directory, screenshot_patterns)

    return AppDefinition(
        metadata=metadata,
        compose=compose,
        config=config,
        input_dir=directory,
        icon_path=icon_path,
        screenshot_paths=screenshot_paths,
    )


def load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If parsed data is not a dictionary
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object in {path}, got {type(data)}")

    return data


def find_optional_files(directory: Path, patterns: list[str]) -> list[Path]:
    """Find files matching patterns in directory.

    Args:
        directory: Directory to search
        patterns: List of glob patterns (e.g., ["icon.svg", "*.png"])

    Returns:
        List of matching file paths, sorted by name
    """
    files: list[Path] = []

    for pattern in patterns:
        matches = list(directory.glob(pattern))
        # Only include files, not directories
        files.extend(p for p in matches if p.is_file())

    # Remove duplicates and sort
    unique_files = sorted(set(files))

    return unique_files
