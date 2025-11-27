"""CasaOS update detector for comparing upstream with converted apps.

Detects new, updated, and removed apps by comparing upstream CasaOS
repository with converted HaLOS packages.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from generate_container_packages.utils import compute_file_hash
from schemas import SourceMetadata


@dataclass
class UpstreamApp:
    """Represents a CasaOS app in the upstream repository."""

    app_id: str
    compose_path: Path
    compose_hash: str


@dataclass
class ConvertedApp:
    """Represents a converted HaLOS package."""

    app_id: str
    metadata_path: Path
    source_metadata: SourceMetadata


@dataclass
class UpdatedApp:
    """Represents an app that has been updated upstream."""

    app_id: str
    old_hash: str
    new_hash: str


@dataclass
class UpdateReport:
    """Report of detected changes between upstream and converted apps."""

    new_apps: list[str]
    updated_apps: list[UpdatedApp]
    removed_apps: list[str]
    timestamp: datetime

    def format_report(self) -> str:
        """Generate human-readable markdown report."""
        if not self.new_apps and not self.updated_apps and not self.removed_apps:
            return (
                f"# CasaOS Update Report ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})\n\n"
                "No changes detected.\n"
            )

        lines = [
            f"# CasaOS Update Report ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})",
            "",
        ]

        if self.new_apps:
            lines.append(f"## New Apps ({len(self.new_apps)})")
            lines.append("")
            for app_id in sorted(self.new_apps):
                lines.append(f"- {app_id}")
            lines.append("")

        if self.updated_apps:
            lines.append(f"## Updated Apps ({len(self.updated_apps)})")
            lines.append("")
            for app in sorted(self.updated_apps, key=lambda a: a.app_id):
                lines.append(f"- {app.app_id} (hash changed)")
            lines.append("")

        if self.removed_apps:
            lines.append(f"## Removed Apps ({len(self.removed_apps)})")
            lines.append("")
            for app_id in sorted(self.removed_apps):
                lines.append(f"- {app_id}")
            lines.append("")

        lines.append("## Summary")
        lines.append("")
        if self.new_apps:
            lines.append(f"- {len(self.new_apps)} apps ready to convert")
        if self.updated_apps:
            lines.append(f"- {len(self.updated_apps)} apps need re-conversion")
        if self.removed_apps:
            lines.append(f"- {len(self.removed_apps)} apps no longer in upstream")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "new_apps": self.new_apps,
            "updated_apps": [
                {
                    "app_id": app.app_id,
                    "old_hash": app.old_hash,
                    "new_hash": app.new_hash,
                }
                for app in self.updated_apps
            ],
            "removed_apps": self.removed_apps,
            "timestamp": self.timestamp.isoformat(),
        }


class CasaOSUpdateDetector:
    """Detects changes between upstream CasaOS apps and converted HaLOS packages.

    Compares upstream CasaOS repository with converted apps to identify:
    - New apps (in upstream but not converted)
    - Updated apps (hash changed since conversion)
    - Removed apps (converted but no longer in upstream)
    """

    def __init__(self, upstream_dir: Path, converted_dir: Path):
        """Initialize detector with upstream and converted directories.

        Args:
            upstream_dir: Path to upstream CasaOS repository Apps directory
            converted_dir: Path to directory containing converted HaLOS packages
        """
        self.upstream_dir = Path(upstream_dir)
        self.converted_dir = Path(converted_dir)

    def detect_changes(self) -> UpdateReport:
        """Compare upstream with converted apps and generate report.

        Returns:
            UpdateReport with lists of new, updated, and removed apps
        """
        upstream_apps = self._scan_upstream()
        converted_apps = self._scan_converted()

        # Detect new apps (in upstream but not converted)
        new_apps = [app_id for app_id in upstream_apps if app_id not in converted_apps]

        # Detect updated apps (hash mismatch)
        updated_apps = [
            UpdatedApp(
                app_id=app_id,
                old_hash=converted_apps[app_id].source_metadata.upstream_hash,
                new_hash=upstream_apps[app_id].compose_hash,
            )
            for app_id in upstream_apps
            if app_id in converted_apps
            and upstream_apps[app_id].compose_hash
            != converted_apps[app_id].source_metadata.upstream_hash
        ]

        # Detect removed apps (converted but not in upstream)
        removed_apps = [
            app_id for app_id in converted_apps if app_id not in upstream_apps
        ]

        return UpdateReport(
            new_apps=new_apps,
            updated_apps=updated_apps,
            removed_apps=removed_apps,
            timestamp=datetime.now(UTC),
        )

    def _scan_upstream(self) -> dict[str, UpstreamApp]:
        """Scan upstream directory for CasaOS apps.

        Returns:
            Dictionary mapping app_id to UpstreamApp
        """
        apps: dict[str, UpstreamApp] = {}

        # Handle non-existent directory
        if not self.upstream_dir.exists():
            return apps

        for app_dir in self.upstream_dir.iterdir():
            # Skip non-directories
            if not app_dir.is_dir():
                continue

            # Check for docker-compose.yml
            compose_file = app_dir / "docker-compose.yml"
            if not compose_file.exists():
                continue

            # Compute hash of compose file
            compose_hash = compute_file_hash(compose_file)

            # Use directory name as app_id
            app_id = app_dir.name

            apps[app_id] = UpstreamApp(
                app_id=app_id,
                compose_path=compose_file,
                compose_hash=compose_hash,
            )

        return apps

    def _scan_converted(self) -> dict[str, ConvertedApp]:
        """Scan converted directory for HaLOS packages with CasaOS source.

        Only includes packages with:
        - source_metadata field present
        - source_metadata.type == "casaos"
        - package_name starts with "casaos-"

        Returns:
            Dictionary mapping app_id to ConvertedApp
        """
        apps: dict[str, ConvertedApp] = {}

        # Handle non-existent directory
        if not self.converted_dir.exists():
            return apps

        for app_dir in self.converted_dir.iterdir():
            # Skip non-directories
            if not app_dir.is_dir():
                continue

            # Only process casaos-* packages
            if not app_dir.name.startswith("casaos-"):
                continue

            # Check for metadata.yaml
            metadata_file = app_dir / "metadata.yaml"
            if not metadata_file.exists():
                continue

            # Load and validate metadata
            try:
                with open(metadata_file) as f:
                    metadata_dict = yaml.safe_load(f)

                # Skip if no source_metadata
                if "source_metadata" not in metadata_dict:
                    continue

                # Validate source_metadata
                source_metadata = SourceMetadata(**metadata_dict["source_metadata"])

                # Only process CasaOS apps
                if source_metadata.type != "casaos":
                    continue

                # Extract app_id from source_metadata
                app_id = source_metadata.app_id

                apps[app_id] = ConvertedApp(
                    app_id=app_id,
                    metadata_path=metadata_file,
                    source_metadata=source_metadata,
                )

            except (yaml.YAMLError, ValidationError, KeyError):
                # Skip invalid metadata files
                continue

        return apps
