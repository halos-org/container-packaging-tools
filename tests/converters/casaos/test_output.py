"""Tests for CasaOS output writer.

Tests the OutputWriter class that writes metadata.yaml, config.yml,
and docker-compose.yml files with validation.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from generate_container_packages.converters.casaos.models import ConversionContext
from generate_container_packages.converters.casaos.output import OutputWriter


class TestOutputWriterInit:
    """Tests for OutputWriter initialization."""

    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that OutputWriter creates output directory."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        OutputWriter(output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_init_accepts_existing_dir(self, tmp_path: Path) -> None:
        """Test that OutputWriter accepts existing directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Should not raise
        OutputWriter(output_dir)

        assert output_dir.exists()


class TestWritePackage:
    """Tests for write_package method."""

    @pytest.fixture
    def valid_metadata(self) -> dict:
        """Valid metadata dictionary."""
        return {
            "name": "Test App",
            "app_id": "test-app",
            "version": "1.0.0",
            "description": "Test application",
            "long_description": "A test application for unit testing",
            "maintainer": "Test Developer <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app", "implemented-in::docker"],
            "debian_section": "net",
            "architecture": "all",
        }

    @pytest.fixture
    def valid_config(self) -> dict:
        """Valid config dictionary."""
        return {
            "version": "1.0",
            "groups": [
                {
                    "id": "general",
                    "label": "General Settings",
                    "description": "Basic configuration",
                    "fields": [
                        {
                            "id": "APP_PORT",
                            "label": "Application Port",
                            "type": "integer",
                            "default": 8080,
                            "required": True,
                            "min": 1024,
                            "max": 65535,
                            "description": "Port for the application",
                        }
                    ],
                }
            ],
        }

    @pytest.fixture
    def valid_compose(self) -> dict:
        """Valid docker-compose dictionary."""
        return {
            "version": "3.8",
            "services": {
                "app": {
                    "image": "nginx:alpine",
                    "ports": ["${APP_PORT}:80"],
                    "restart": "unless-stopped",
                }
            },
        }

    @pytest.fixture
    def conversion_context(self) -> ConversionContext:
        """Conversion context for testing."""
        return ConversionContext(source_format="casaos", app_id="test-app")

    def test_write_package_creates_all_files(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that write_package creates all three files."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        # Check all files exist
        assert (output_dir / "metadata.yaml").exists()
        assert (output_dir / "config.yml").exists()
        assert (output_dir / "docker-compose.yml").exists()

    def test_write_package_validates_metadata(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that write_package validates metadata against schema."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        # Invalid metadata (missing required field)
        invalid_metadata = valid_metadata.copy()
        del invalid_metadata["maintainer"]

        with pytest.raises(ValidationError) as exc_info:
            writer.write_package(
                invalid_metadata, valid_config, valid_compose, conversion_context
            )

        assert "maintainer" in str(exc_info.value).lower()

    def test_write_package_validates_config(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that write_package validates config against schema."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        # Invalid config (wrong version format)
        invalid_config = valid_config.copy()
        invalid_config["version"] = "2.0"  # Only "1.0" is valid

        with pytest.raises(ValidationError) as exc_info:
            writer.write_package(
                valid_metadata, invalid_config, valid_compose, conversion_context
            )

        assert "version" in str(exc_info.value).lower()

    def test_write_package_content_valid_yaml(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that written files contain valid YAML."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        # Load and verify each file is valid YAML
        with open(output_dir / "metadata.yaml") as f:
            metadata_yaml = yaml.safe_load(f)
            assert metadata_yaml["name"] == "Test App"

        with open(output_dir / "config.yml") as f:
            config_yaml = yaml.safe_load(f)
            assert config_yaml["version"] == "1.0"

        with open(output_dir / "docker-compose.yml") as f:
            compose_yaml = yaml.safe_load(f)
            assert compose_yaml["version"] == "3.8"

    def test_write_package_metadata_content(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that metadata.yaml contains correct data."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        with open(output_dir / "metadata.yaml") as f:
            metadata_yaml = yaml.safe_load(f)

        assert metadata_yaml["name"] == "Test App"
        assert metadata_yaml["app_id"] == "test-app"
        assert metadata_yaml["version"] == "1.0.0"
        assert metadata_yaml["maintainer"] == "Test Developer <test@example.com>"
        assert metadata_yaml["license"] == "MIT"

    def test_write_package_config_content(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that config.yml contains correct data."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        with open(output_dir / "config.yml") as f:
            config_yaml = yaml.safe_load(f)

        assert config_yaml["version"] == "1.0"
        assert len(config_yaml["groups"]) == 1
        assert config_yaml["groups"][0]["id"] == "general"
        assert len(config_yaml["groups"][0]["fields"]) == 1
        assert config_yaml["groups"][0]["fields"][0]["id"] == "APP_PORT"

    def test_write_package_compose_content(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that docker-compose.yml contains correct data."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        with open(output_dir / "docker-compose.yml") as f:
            compose_yaml = yaml.safe_load(f)

        assert compose_yaml["version"] == "3.8"
        assert "services" in compose_yaml
        assert "app" in compose_yaml["services"]
        assert compose_yaml["services"]["app"]["image"] == "nginx:alpine"

    def test_write_package_no_xcasaos_in_compose(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that x-casaos metadata is not written to docker-compose.yml."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        # Compose with x-casaos (should be stripped by transformer, but verify)
        compose_with_xcasaos = {
            "version": "3.8",
            "services": {
                "app": {"image": "nginx:alpine", "x-casaos": {"some": "metadata"}}
            },
            "x-casaos": {"app": "metadata"},
        }

        writer.write_package(
            valid_metadata, valid_config, compose_with_xcasaos, conversion_context
        )

        with open(output_dir / "docker-compose.yml") as f:
            compose_yaml = yaml.safe_load(f)

        # x-casaos should not be in output
        assert "x-casaos" not in compose_yaml
        assert "x-casaos" not in compose_yaml["services"]["app"]

    def test_write_package_overwrites_existing_files(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that write_package overwrites existing files."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        # Write initial files
        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        # Modify metadata and write again
        modified_metadata = valid_metadata.copy()
        modified_metadata["name"] = "Modified App"

        writer.write_package(
            modified_metadata, valid_config, valid_compose, conversion_context
        )

        # Verify file was overwritten
        with open(output_dir / "metadata.yaml") as f:
            metadata_yaml = yaml.safe_load(f)

        assert metadata_yaml["name"] == "Modified App"

    def test_write_package_yaml_formatting(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that YAML files are properly formatted."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        writer.write_package(
            valid_metadata, valid_config, valid_compose, conversion_context
        )

        # Check that files use proper YAML formatting (not inline flow style)
        with open(output_dir / "metadata.yaml") as f:
            content = f.read()
            # Should have newlines between fields
            assert "\n" in content
            # Should not use inline flow style {}
            assert content.count("{") == 0 or content.count("{") <= 2

    def test_write_package_with_optional_fields(
        self,
        tmp_path: Path,
        valid_metadata: dict,
        valid_config: dict,
        valid_compose: dict,
        conversion_context: ConversionContext,
    ) -> None:
        """Test writing package with optional metadata fields."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        # Add optional fields
        metadata_with_optional = valid_metadata.copy()
        metadata_with_optional["homepage"] = "https://example.com"
        metadata_with_optional["icon"] = "icon.png"
        metadata_with_optional["screenshots"] = ["screenshot1.png", "screenshot2.png"]

        writer.write_package(
            metadata_with_optional, valid_config, valid_compose, conversion_context
        )

        with open(output_dir / "metadata.yaml") as f:
            metadata_yaml = yaml.safe_load(f)

        assert metadata_yaml["homepage"] == "https://example.com"
        assert metadata_yaml["icon"] == "icon.png"
        assert metadata_yaml["screenshots"] == ["screenshot1.png", "screenshot2.png"]


class TestYAMLFormatting:
    """Tests for YAML formatting behavior."""

    @pytest.fixture
    def conversion_context(self) -> ConversionContext:
        """Conversion context for testing."""
        return ConversionContext(source_format="casaos", app_id="test-app")

    def test_yaml_multiline_strings(
        self, tmp_path: Path, conversion_context: ConversionContext
    ) -> None:
        """Test that multiline strings are formatted correctly."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        metadata = {
            "name": "Test App",
            "app_id": "test-app",
            "version": "1.0.0",
            "description": "Short description",
            "long_description": "This is a very long description\nthat spans multiple lines\nand should be formatted nicely",
            "maintainer": "Test Developer <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        config = {
            "version": "1.0",
            "groups": [
                {
                    "id": "general",
                    "label": "General",
                    "description": None,
                    "fields": [
                        {
                            "id": "VAR",
                            "label": "Variable",
                            "type": "string",
                            "default": "",
                            "required": False,
                            "description": None,
                        }
                    ],
                }
            ],
        }

        compose = {"version": "3.8", "services": {"app": {"image": "nginx:alpine"}}}

        writer.write_package(metadata, config, compose, conversion_context)

        # Check that long_description is properly formatted
        with open(output_dir / "metadata.yaml") as f:
            content = f.read()
            # Should contain the multiline string
            assert "long description" in content.lower()

    def test_yaml_list_formatting(
        self, tmp_path: Path, conversion_context: ConversionContext
    ) -> None:
        """Test that lists are formatted correctly."""
        output_dir = tmp_path / "output"
        writer = OutputWriter(output_dir)

        metadata = {
            "name": "Test App",
            "app_id": "test-app",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test Developer <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app", "implemented-in::docker", "use::browsing"],
            "debian_section": "net",
            "architecture": "all",
        }

        config = {
            "version": "1.0",
            "groups": [
                {
                    "id": "general",
                    "label": "General",
                    "description": None,
                    "fields": [
                        {
                            "id": "VAR",
                            "label": "Variable",
                            "type": "string",
                            "default": "",
                            "required": False,
                            "description": None,
                        }
                    ],
                }
            ],
        }

        compose = {"version": "3.8", "services": {"app": {"image": "nginx:alpine"}}}

        writer.write_package(metadata, config, compose, conversion_context)

        # Check that tags list is properly formatted
        with open(output_dir / "metadata.yaml") as f:
            metadata_yaml = yaml.safe_load(f)
            assert len(metadata_yaml["tags"]) == 3
