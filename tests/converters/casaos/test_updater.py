"""Tests for CasaOS update detector.

Tests the CasaOSUpdateDetector class that compares upstream CasaOS apps
with converted HaLOS apps to detect changes.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from generate_container_packages.converters.casaos.updater import (
    CasaOSUpdateDetector,
    ConvertedApp,
    UpdatedApp,
    UpdateReport,
    UpstreamApp,
)
from generate_container_packages.utils import compute_file_hash


class TestCasaOSUpdateDetectorInit:
    """Tests for CasaOSUpdateDetector initialization."""

    def test_init_with_paths(self, tmp_path: Path) -> None:
        """Test that detector accepts upstream and converted directories."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)

        assert detector.upstream_dir == upstream_dir
        assert detector.converted_dir == converted_dir

    def test_init_creates_directories_if_missing(self, tmp_path: Path) -> None:
        """Test that detector handles missing directories gracefully."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"

        # Directories don't exist yet
        assert not upstream_dir.exists()
        assert not converted_dir.exists()

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)

        # Should accept Path objects even if directories don't exist
        assert detector.upstream_dir == upstream_dir
        assert detector.converted_dir == converted_dir


class TestHashComputation:
    """Tests for hash computation."""

    def test_compute_hash_consistent(self, tmp_path: Path) -> None:
        """Test that same file produces same hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        hash1 = compute_file_hash(test_file)
        hash2 = compute_file_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_compute_hash_different_for_different_content(self, tmp_path: Path) -> None:
        """Test that different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = compute_file_hash(file1)
        hash2 = compute_file_hash(file2)

        assert hash1 != hash2

    def test_compute_hash_matches_sha256(self, tmp_path: Path) -> None:
        """Test that computed hash matches expected SHA256."""
        import hashlib

        test_file = tmp_path / "test.txt"
        content = "test content for hashing"
        test_file.write_text(content)

        computed_hash = compute_file_hash(test_file)
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        assert computed_hash == expected_hash


class TestUpstreamScanning:
    """Tests for scanning upstream CasaOS directory."""

    @pytest.fixture
    def upstream_app(self, tmp_path: Path) -> Path:
        """Create a CasaOS app directory with docker-compose.yml."""
        app_dir = tmp_path / "jellyfin"
        app_dir.mkdir()
        compose_file = app_dir / "docker-compose.yml"
        compose_file.write_text(
            """
version: "3.8"
services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    ports:
      - "8096:8096"
x-casaos:
  title: Jellyfin
"""
        )
        return tmp_path

    def test_scan_upstream_finds_apps(self, tmp_path: Path, upstream_app: Path) -> None:
        """Test that scan_upstream finds CasaOS apps."""
        detector = CasaOSUpdateDetector(upstream_app, tmp_path / "converted")

        apps = detector._scan_upstream()

        assert "jellyfin" in apps
        assert isinstance(apps["jellyfin"], UpstreamApp)
        assert apps["jellyfin"].app_id == "jellyfin"
        assert apps["jellyfin"].compose_path.name == "docker-compose.yml"

    def test_scan_upstream_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty upstream directory returns no apps."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()

        detector = CasaOSUpdateDetector(upstream_dir, tmp_path / "converted")
        apps = detector._scan_upstream()

        assert apps == {}

    def test_scan_upstream_multiple_apps(self, tmp_path: Path) -> None:
        """Test scanning multiple upstream apps."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()

        # Create multiple app directories
        for app_name in ["app1", "app2", "app3"]:
            app_dir = upstream_dir / app_name
            app_dir.mkdir()
            (app_dir / "docker-compose.yml").write_text("version: '3.8'")

        detector = CasaOSUpdateDetector(upstream_dir, tmp_path / "converted")
        apps = detector._scan_upstream()

        assert len(apps) == 3
        assert "app1" in apps
        assert "app2" in apps
        assert "app3" in apps

    def test_scan_upstream_ignores_non_directories(self, tmp_path: Path) -> None:
        """Test that scan ignores files in upstream directory."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()

        # Create a file (not directory)
        (upstream_dir / "README.md").write_text("readme")

        # Create valid app
        app_dir = upstream_dir / "validapp"
        app_dir.mkdir()
        (app_dir / "docker-compose.yml").write_text("version: '3.8'")

        detector = CasaOSUpdateDetector(upstream_dir, tmp_path / "converted")
        apps = detector._scan_upstream()

        assert len(apps) == 1
        assert "validapp" in apps

    def test_scan_upstream_ignores_missing_compose(self, tmp_path: Path) -> None:
        """Test that scan ignores directories without docker-compose.yml."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()

        # Directory without docker-compose.yml
        (upstream_dir / "incomplete").mkdir()

        # Directory with docker-compose.yml
        app_dir = upstream_dir / "complete"
        app_dir.mkdir()
        (app_dir / "docker-compose.yml").write_text("version: '3.8'")

        detector = CasaOSUpdateDetector(upstream_dir, tmp_path / "converted")
        apps = detector._scan_upstream()

        assert len(apps) == 1
        assert "complete" in apps


class TestConvertedScanning:
    """Tests for scanning converted HaLOS directory."""

    @pytest.fixture
    def converted_app(self, tmp_path: Path) -> Path:
        """Create a converted app directory with metadata.yaml."""
        app_dir = tmp_path / "casaos-jellyfin-container"
        app_dir.mkdir()
        metadata_file = app_dir / "metadata.yaml"
        metadata = {
            "name": "Jellyfin",
            "package_name": "casaos-jellyfin-container",
            "version": "10.8.0",
            "description": "Media server",
            "maintainer": "Test <test@example.com>",
            "license": "GPL-2.0",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "jellyfin",
                "source_url": "https://github.com/IceWhaleTech/CasaOS-AppStore",
                "upstream_hash": "abc123",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(metadata_file, "w") as f:
            yaml.dump(metadata, f)
        return tmp_path

    def test_scan_converted_finds_apps(
        self, tmp_path: Path, converted_app: Path
    ) -> None:
        """Test that scan_converted finds converted apps."""
        detector = CasaOSUpdateDetector(tmp_path / "upstream", converted_app)

        apps = detector._scan_converted()

        assert "jellyfin" in apps
        assert isinstance(apps["jellyfin"], ConvertedApp)
        assert apps["jellyfin"].app_id == "jellyfin"
        assert apps["jellyfin"].source_metadata.type == "casaos"

    def test_scan_converted_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty converted directory returns no apps."""
        converted_dir = tmp_path / "converted"
        converted_dir.mkdir()

        detector = CasaOSUpdateDetector(tmp_path / "upstream", converted_dir)
        apps = detector._scan_converted()

        assert apps == {}

    def test_scan_converted_ignores_missing_source_metadata(
        self, tmp_path: Path
    ) -> None:
        """Test that apps without source_metadata are ignored."""
        converted_dir = tmp_path / "converted"
        converted_dir.mkdir()

        # Create app without source_metadata (manual app)
        app_dir = converted_dir / "manual-app-container"
        app_dir.mkdir()
        metadata = {
            "name": "Manual App",
            "package_name": "manual-app-container",
            "version": "1.0.0",
            "description": "Manual",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }
        with open(app_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        detector = CasaOSUpdateDetector(tmp_path / "upstream", converted_dir)
        apps = detector._scan_converted()

        assert apps == {}

    def test_scan_converted_filters_by_casaos_type(self, tmp_path: Path) -> None:
        """Test that only apps with type='casaos' are processed."""
        converted_dir = tmp_path / "converted"
        converted_dir.mkdir()

        # Create CasaOS app
        casaos_dir = converted_dir / "casaos-app-container"
        casaos_dir.mkdir()
        casaos_metadata = {
            "name": "CasaOS App",
            "package_name": "casaos-app-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "app",
                "source_url": "https://example.com",
                "upstream_hash": "hash1",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(casaos_dir / "metadata.yaml", "w") as f:
            yaml.dump(casaos_metadata, f)

        # Create Runtipi app (different source)
        runtipi_dir = converted_dir / "runtipi-other-container"
        runtipi_dir.mkdir()
        runtipi_metadata = {
            "name": "Runtipi App",
            "package_name": "runtipi-other-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "runtipi",
                "app_id": "other",
                "source_url": "https://example.com",
                "upstream_hash": "hash2",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(runtipi_dir / "metadata.yaml", "w") as f:
            yaml.dump(runtipi_metadata, f)

        detector = CasaOSUpdateDetector(tmp_path / "upstream", converted_dir)
        apps = detector._scan_converted()

        assert len(apps) == 1
        assert "app" in apps
        assert "other" not in apps

    def test_scan_converted_package_prefix_filtering(self, tmp_path: Path) -> None:
        """Test that only casaos-* packages are scanned."""
        converted_dir = tmp_path / "converted"
        converted_dir.mkdir()

        # Create casaos-prefixed app
        casaos_dir = converted_dir / "casaos-test-container"
        casaos_dir.mkdir()
        casaos_metadata = {
            "name": "Test",
            "package_name": "casaos-test-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "test",
                "source_url": "https://example.com",
                "upstream_hash": "hash",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(casaos_dir / "metadata.yaml", "w") as f:
            yaml.dump(casaos_metadata, f)

        detector = CasaOSUpdateDetector(tmp_path / "upstream", converted_dir)
        apps = detector._scan_converted()

        assert len(apps) == 1
        assert "test" in apps


class TestChangeDetection:
    """Tests for detecting changes between upstream and converted."""

    def test_detect_new_apps(self, tmp_path: Path) -> None:
        """Test detection of new apps in upstream."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create upstream app
        app_dir = upstream_dir / "newapp"
        app_dir.mkdir()
        (app_dir / "docker-compose.yml").write_text("version: '3.8'")

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        report = detector.detect_changes()

        assert len(report.new_apps) == 1
        assert "newapp" in report.new_apps
        assert len(report.updated_apps) == 0
        assert len(report.removed_apps) == 0

    def test_detect_no_new_apps_when_all_converted(self, tmp_path: Path) -> None:
        """Test that no new apps are detected when all are converted."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create upstream app
        app_dir = upstream_dir / "existing"
        app_dir.mkdir()
        compose_file = app_dir / "docker-compose.yml"
        compose_file.write_text("version: '3.8'")

        # Compute hash for converted app
        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        compose_hash = compute_file_hash(compose_file)

        # Create converted app with same hash
        conv_dir = converted_dir / "casaos-existing-container"
        conv_dir.mkdir()
        metadata = {
            "name": "Existing",
            "package_name": "casaos-existing-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "existing",
                "source_url": "https://example.com",
                "upstream_hash": compose_hash,
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        report = detector.detect_changes()

        assert len(report.new_apps) == 0
        assert len(report.updated_apps) == 0
        assert len(report.removed_apps) == 0

    def test_detect_updated_app_hash_changed(self, tmp_path: Path) -> None:
        """Test detection of updated apps with changed hashes."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create upstream app with new content
        app_dir = upstream_dir / "updated"
        app_dir.mkdir()
        (app_dir / "docker-compose.yml").write_text("version: '3.9'")  # Changed

        # Create converted app with old hash
        conv_dir = converted_dir / "casaos-updated-container"
        conv_dir.mkdir()
        metadata = {
            "name": "Updated",
            "package_name": "casaos-updated-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "updated",
                "source_url": "https://example.com",
                "upstream_hash": "oldhash123",  # Different from current
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        report = detector.detect_changes()

        assert len(report.new_apps) == 0
        assert len(report.updated_apps) == 1
        assert report.updated_apps[0].app_id == "updated"
        assert report.updated_apps[0].old_hash == "oldhash123"
        assert report.updated_apps[0].new_hash != "oldhash123"
        assert len(report.removed_apps) == 0

    def test_detect_no_updates_when_hashes_match(self, tmp_path: Path) -> None:
        """Test that matching hashes result in no updates."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create upstream app
        app_dir = upstream_dir / "unchanged"
        app_dir.mkdir()
        compose_file = app_dir / "docker-compose.yml"
        compose_file.write_text("version: '3.8'")

        # Compute hash
        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        compose_hash = compute_file_hash(compose_file)

        # Create converted app with matching hash
        conv_dir = converted_dir / "casaos-unchanged-container"
        conv_dir.mkdir()
        metadata = {
            "name": "Unchanged",
            "package_name": "casaos-unchanged-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "unchanged",
                "source_url": "https://example.com",
                "upstream_hash": compose_hash,
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        report = detector.detect_changes()

        assert len(report.new_apps) == 0
        assert len(report.updated_apps) == 0
        assert len(report.removed_apps) == 0

    def test_detect_removed_apps(self, tmp_path: Path) -> None:
        """Test detection of apps removed from upstream."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create converted app without upstream counterpart
        conv_dir = converted_dir / "casaos-removed-container"
        conv_dir.mkdir()
        metadata = {
            "name": "Removed",
            "package_name": "casaos-removed-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "removed",
                "source_url": "https://example.com",
                "upstream_hash": "hash",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        report = detector.detect_changes()

        assert len(report.new_apps) == 0
        assert len(report.updated_apps) == 0
        assert len(report.removed_apps) == 1
        assert "removed" in report.removed_apps

    def test_detect_no_removed_apps_when_all_present(self, tmp_path: Path) -> None:
        """Test that no removed apps when all are still in upstream."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # Create upstream app
        app_dir = upstream_dir / "present"
        app_dir.mkdir()
        compose_file = app_dir / "docker-compose.yml"
        compose_file.write_text("version: '3.8'")

        # Compute hash
        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        compose_hash = compute_file_hash(compose_file)

        # Create converted app
        conv_dir = converted_dir / "casaos-present-container"
        conv_dir.mkdir()
        metadata = {
            "name": "Present",
            "package_name": "casaos-present-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "present",
                "source_url": "https://example.com",
                "upstream_hash": compose_hash,
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)

        report = detector.detect_changes()

        assert len(report.new_apps) == 0
        assert len(report.updated_apps) == 0
        assert len(report.removed_apps) == 0

    def test_detect_all_change_types(self, tmp_path: Path) -> None:
        """Test detection of new, updated, and removed apps together."""
        upstream_dir = tmp_path / "upstream"
        converted_dir = tmp_path / "converted"
        upstream_dir.mkdir()
        converted_dir.mkdir()

        # New app (only in upstream)
        new_dir = upstream_dir / "newapp"
        new_dir.mkdir()
        (new_dir / "docker-compose.yml").write_text("version: '3.8'")

        # Updated app (in both, but different hash)
        upd_dir = upstream_dir / "updated"
        upd_dir.mkdir()
        (upd_dir / "docker-compose.yml").write_text("version: '3.9'")

        conv_upd_dir = converted_dir / "casaos-updated-container"
        conv_upd_dir.mkdir()
        upd_metadata = {
            "name": "Updated",
            "package_name": "casaos-updated-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "updated",
                "source_url": "https://example.com",
                "upstream_hash": "oldhash",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_upd_dir / "metadata.yaml", "w") as f:
            yaml.dump(upd_metadata, f)

        # Removed app (only in converted)
        conv_rem_dir = converted_dir / "casaos-removed-container"
        conv_rem_dir.mkdir()
        rem_metadata = {
            "name": "Removed",
            "package_name": "casaos-removed-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "source_metadata": {
                "type": "casaos",
                "app_id": "removed",
                "source_url": "https://example.com",
                "upstream_hash": "hash",
                "conversion_timestamp": "2025-11-27T12:00:00Z",
            },
        }
        with open(conv_rem_dir / "metadata.yaml", "w") as f:
            yaml.dump(rem_metadata, f)

        detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
        report = detector.detect_changes()

        assert len(report.new_apps) == 1
        assert "newapp" in report.new_apps
        assert len(report.updated_apps) == 1
        assert report.updated_apps[0].app_id == "updated"
        assert len(report.removed_apps) == 1
        assert "removed" in report.removed_apps


class TestUpdateReport:
    """Tests for UpdateReport formatting and serialization."""

    def test_format_report_markdown(self) -> None:
        """Test that report formats as readable markdown."""
        timestamp = datetime(2025, 11, 27, 12, 0, 0, tzinfo=UTC)
        report = UpdateReport(
            new_apps=["app1", "app2"],
            updated_apps=[UpdatedApp("app3", "oldhash", "newhash")],
            removed_apps=["app4"],
            timestamp=timestamp,
        )

        formatted = report.format_report()

        assert "# CasaOS Update Report" in formatted
        assert "2025-11-27" in formatted
        assert "## New Apps (2)" in formatted
        assert "- app1" in formatted
        assert "- app2" in formatted
        assert "## Updated Apps (1)" in formatted
        assert "- app3" in formatted
        assert "## Removed Apps (1)" in formatted
        assert "- app4" in formatted
        assert "## Summary" in formatted

    def test_format_report_with_no_changes(self) -> None:
        """Test report formatting when no changes detected."""
        timestamp = datetime(2025, 11, 27, 12, 0, 0, tzinfo=UTC)
        report = UpdateReport(
            new_apps=[],
            updated_apps=[],
            removed_apps=[],
            timestamp=timestamp,
        )

        formatted = report.format_report()

        assert "No changes detected" in formatted

    def test_to_dict_serialization(self) -> None:
        """Test that report can be serialized to dict for JSON export."""
        timestamp = datetime(2025, 11, 27, 12, 0, 0, tzinfo=UTC)
        report = UpdateReport(
            new_apps=["app1"],
            updated_apps=[UpdatedApp("app2", "old", "new")],
            removed_apps=["app3"],
            timestamp=timestamp,
        )

        data = report.to_dict()

        assert data["new_apps"] == ["app1"]
        assert len(data["updated_apps"]) == 1
        assert data["updated_apps"][0]["app_id"] == "app2"
        assert data["updated_apps"][0]["old_hash"] == "old"
        assert data["updated_apps"][0]["new_hash"] == "new"
        assert data["removed_apps"] == ["app3"]
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
