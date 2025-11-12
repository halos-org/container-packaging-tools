"""File loading and data model construction."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from generate_container_packages import __version__


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
        icon_path: Optional[Path] = None,
        screenshot_paths: Optional[list[Path]] = None,
    ):
        """Initialize AppDefinition.

        Args:
            metadata: Parsed metadata.yaml contents
            compose: Parsed docker-compose.yml contents
            config: Parsed config.yml contents
            icon_path: Path to icon file (if exists)
            screenshot_paths: List of paths to screenshot files
        """
        self.metadata = metadata
        self.compose = compose
        self.config = config
        self.icon_path = icon_path
        self.screenshot_paths = screenshot_paths or []

        # Computed fields
        now = datetime.now(timezone.utc)
        self.timestamp = now.isoformat()  # ISO 8601 for general use

        # RFC 2822 for Debian changelog (with colon in timezone offset)
        tz_str = now.strftime("%z")
        self.timestamp_rfc2822 = (
            now.strftime("%a, %d %b %Y %H:%M:%S ") + tz_str[:3] + ":" + tz_str[3:]
        )

        self.date_only = now.strftime("%Y-%m-%d")  # YYYY-MM-DD for AppStream
        self.tool_version = __version__


def load_input_files(directory: Path) -> AppDefinition:
    """Load all input files from directory into unified data model.

    Args:
        directory: Path to input directory

    Returns:
        AppDefinition with all loaded data

    Raises:
        FileNotFoundError: If required file is missing
        yaml.YAMLError: If YAML parsing fails
    """
    # Load required files
    metadata = load_yaml(directory / "metadata.yaml")
    compose = load_yaml(directory / "docker-compose.yml")
    config = load_yaml(directory / "config.yml")

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
