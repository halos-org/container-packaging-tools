"""Unit tests for file loader module."""

from pathlib import Path

import pytest

from generate_container_packages.loader import (
    AppDefinition,
    find_optional_files,
    load_input_files,
    load_yaml,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"


class TestAppDefinition:
    """Tests for AppDefinition class."""

    def test_app_definition_creation(self):
        """Test creating AppDefinition instance."""
        metadata = {"name": "Test App"}
        compose = {"version": "3.8"}
        config = {"version": "1.0"}
        input_dir = Path("/test/dir")

        app_def = AppDefinition(
            metadata=metadata,
            compose=compose,
            config=config,
            input_dir=input_dir,
        )

        assert app_def.metadata == metadata
        assert app_def.compose == compose
        assert app_def.config == config
        assert app_def.input_dir == input_dir
        assert app_def.icon_path is None
        assert app_def.screenshot_paths == []
        assert app_def.timestamp is not None
        assert app_def.tool_version is not None

    def test_app_definition_with_optional_files(self):
        """Test AppDefinition with icon and screenshots."""
        metadata = {"name": "Test App"}
        compose = {"version": "3.8"}
        config = {"version": "1.0"}
        input_dir = Path("/test/dir")
        icon_path = Path("/path/to/icon.svg")
        screenshot_paths = [Path("/path/to/screenshot1.png")]

        app_def = AppDefinition(
            metadata=metadata,
            compose=compose,
            config=config,
            input_dir=input_dir,
            icon_path=icon_path,
            screenshot_paths=screenshot_paths,
        )

        assert app_def.icon_path == icon_path
        assert len(app_def.screenshot_paths) == 1
        assert app_def.screenshot_paths[0] == screenshot_paths[0]

    def test_timestamp_format(self):
        """Test that timestamp is ISO 8601 format."""
        metadata = {"name": "Test App"}
        compose = {"version": "3.8"}
        config = {"version": "1.0"}
        input_dir = Path("/test/dir")

        app_def = AppDefinition(
            metadata=metadata,
            compose=compose,
            config=config,
            input_dir=input_dir,
        )

        # Should be ISO 8601 format (contains T and Z or +)
        assert "T" in app_def.timestamp
        assert "Z" in app_def.timestamp or "+" in app_def.timestamp


class TestLoadInputFiles:
    """Tests for load_input_files function."""

    def test_load_simple_app(self):
        """Test loading simple-app fixture."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        assert app_def.metadata is not None
        assert app_def.metadata["name"] == "Simple Test App"
        assert app_def.compose is not None
        assert app_def.config is not None
        assert app_def.icon_path is not None
        assert app_def.icon_path.name == "icon.png"

    def test_load_full_app(self):
        """Test loading full-app fixture."""
        app_def = load_input_files(VALID_FIXTURES / "full-app")

        assert app_def.metadata is not None
        assert app_def.metadata["name"] == "Full Featured Test App"
        assert app_def.compose is not None
        assert app_def.config is not None
        # Should have SVG icon
        assert app_def.icon_path is not None
        assert app_def.icon_path.suffix == ".svg"
        # Should have screenshots
        assert len(app_def.screenshot_paths) >= 2

    def test_load_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        with pytest.raises(FileNotFoundError):
            load_input_files(VALID_FIXTURES / "nonexistent")

    def test_metadata_structure_preserved(self):
        """Test that metadata structure is preserved."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        # Check nested structure
        assert "web_ui" in app_def.metadata
        assert app_def.metadata["web_ui"]["enabled"] is True
        assert app_def.metadata["web_ui"]["port"] == 8080

    def test_compose_structure_preserved(self):
        """Test that docker-compose structure is preserved."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        assert "services" in app_def.compose
        assert "app" in app_def.compose["services"]
        assert "image" in app_def.compose["services"]["app"]

    def test_config_structure_preserved(self):
        """Test that config structure is preserved."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        assert "groups" in app_def.config
        assert len(app_def.config["groups"]) > 0
        assert "fields" in app_def.config["groups"][0]


class TestLoadYaml:
    """Tests for load_yaml function."""

    def test_load_valid_yaml(self):
        """Test loading valid YAML file."""
        data = load_yaml(VALID_FIXTURES / "simple-app" / "metadata.yaml")

        assert isinstance(data, dict)
        assert "name" in data
        assert "version" in data

    def test_load_nonexistent_file(self):
        """Test loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_yaml(VALID_FIXTURES / "nonexistent.yaml")

    def test_utf8_encoding(self):
        """Test that UTF-8 encoding is handled correctly."""
        # All fixtures should load without encoding errors
        data = load_yaml(VALID_FIXTURES / "full-app" / "metadata.yaml")

        assert isinstance(data, dict)
        # Should handle descriptions with various characters
        assert "description" in data


class TestFindOptionalFiles:
    """Tests for find_optional_files function."""

    def test_find_icon_files(self):
        """Test finding icon files."""
        files = find_optional_files(
            VALID_FIXTURES / "simple-app",
            ["icon.svg", "icon.png"],
        )

        assert len(files) > 0
        assert any(f.name == "icon.png" for f in files)

    def test_find_screenshot_files(self):
        """Test finding screenshot files."""
        files = find_optional_files(
            VALID_FIXTURES / "full-app",
            ["screenshot*.png", "screenshot*.jpg"],
        )

        assert len(files) >= 2
        # Screenshots should be sorted
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_no_matching_files(self):
        """Test when no files match patterns."""
        files = find_optional_files(
            VALID_FIXTURES / "simple-app",
            ["nonexistent*.txt"],
        )

        assert len(files) == 0

    def test_multiple_patterns(self):
        """Test with multiple glob patterns."""
        files = find_optional_files(
            VALID_FIXTURES / "full-app",
            ["*.svg", "*.png"],
        )

        # Should find both icon.svg and screenshot files
        assert len(files) >= 3
        # Should be unique and sorted
        assert len(files) == len(set(files))

    def test_directories_excluded(self):
        """Test that directories are excluded from results."""
        # Even if a pattern would match a directory, it should not be included
        files = find_optional_files(
            VALID_FIXTURES,
            ["*"],
        )

        # All results should be files, not directories
        for file_path in files:
            assert file_path.is_file()


class TestIntegration:
    """Integration tests for loader module."""

    def test_load_all_valid_fixtures(self):
        """Test that all valid fixtures can be loaded."""
        for fixture_dir in VALID_FIXTURES.iterdir():
            if fixture_dir.is_dir():
                app_def = load_input_files(fixture_dir)

                assert app_def.metadata is not None, (
                    f"Failed to load metadata from {fixture_dir.name}"
                )
                assert app_def.compose is not None, (
                    f"Failed to load compose from {fixture_dir.name}"
                )
                assert app_def.config is not None, f"Failed to load config from {fixture_dir.name}"
                assert app_def.timestamp is not None
                assert app_def.tool_version is not None

    def test_loader_after_validation(self):
        """Test that loader works with validated data."""
        from generate_container_packages.validator import validate_input_directory

        # Validate first
        validation_result = validate_input_directory(VALID_FIXTURES / "simple-app")
        assert validation_result.success is True
        assert validation_result.metadata is not None

        # Then load
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        # Data should match between validator and loader
        assert app_def.metadata["name"] == validation_result.metadata.name
        assert app_def.metadata["version"] == validation_result.metadata.version
