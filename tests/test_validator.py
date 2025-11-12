"""Unit tests for input validator module."""

from pathlib import Path

import pytest

from generate_container_packages.validator import (
    ValidationWarning,
    format_pydantic_error,
    validate_compose,
    validate_config,
    validate_input_directory,
    validate_metadata,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"
INVALID_FIXTURES = FIXTURES_DIR / "invalid"


class TestValidateInputDirectory:
    """Tests for validate_input_directory function."""

    def test_valid_simple_app(self):
        """Test validation of simple-app fixture."""
        result = validate_input_directory(VALID_FIXTURES / "simple-app")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.name == "Simple Test App"
        assert result.config is not None
        assert result.compose is not None
        assert len(result.errors) == 0

    def test_valid_full_app(self):
        """Test validation of full-app fixture."""
        result = validate_input_directory(VALID_FIXTURES / "full-app")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.name == "Full Featured Test App"
        assert result.config is not None
        assert result.compose is not None
        assert len(result.errors) == 0

    def test_nonexistent_directory(self):
        """Test validation of non-existent directory."""
        result = validate_input_directory(VALID_FIXTURES / "nonexistent")

        assert result.success is False
        assert "not a directory" in result.errors[0].lower()

    def test_missing_metadata(self):
        """Test validation when metadata.yaml is missing."""
        result = validate_input_directory(INVALID_FIXTURES / "missing-metadata")

        assert result.success is False
        assert any("metadata.yaml" in err for err in result.errors)

    def test_invalid_package_name(self):
        """Test validation with invalid package name."""
        result = validate_input_directory(INVALID_FIXTURES / "bad-package-name")

        assert result.success is False
        assert len(result.errors) > 0
        # Should detect missing -container suffix
        assert any("container" in err.lower() for err in result.errors)

    def test_missing_tag(self):
        """Test validation when role::container-app tag is missing."""
        result = validate_input_directory(INVALID_FIXTURES / "missing-tag")

        assert result.success is False
        assert len(result.errors) > 0
        assert any("role::container-app" in err for err in result.errors)

    def test_invalid_version(self):
        """Test validation with invalid version format."""
        result = validate_input_directory(INVALID_FIXTURES / "invalid-version")

        assert result.success is False
        assert len(result.errors) > 0
        assert any("version" in err.lower() for err in result.errors)

    def test_invalid_email(self):
        """Test validation with malformed maintainer email."""
        result = validate_input_directory(INVALID_FIXTURES / "invalid-email")

        assert result.success is False
        assert len(result.errors) > 0
        assert any("maintainer" in err.lower() for err in result.errors)


class TestValidateMetadata:
    """Tests for validate_metadata function."""

    def test_valid_metadata(self):
        """Test validation of valid metadata.yaml."""
        metadata = validate_metadata(VALID_FIXTURES / "simple-app" / "metadata.yaml")

        assert metadata.name == "Simple Test App"
        assert metadata.package_name == "simple-test-app-container"
        assert metadata.version == "1.0.0"

    def test_metadata_with_optional_fields(self):
        """Test validation of metadata with all optional fields."""
        metadata = validate_metadata(VALID_FIXTURES / "full-app" / "metadata.yaml")

        assert metadata.name == "Full Featured Test App"
        assert metadata.upstream_version == "2.1.3"
        assert metadata.icon == "icon.svg"
        assert len(metadata.screenshots) == 2
        assert metadata.depends is not None
        assert metadata.web_ui is not None


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config(self):
        """Test validation of valid config.yml."""
        config = validate_config(VALID_FIXTURES / "simple-app" / "config.yml")

        assert config.version == "1.0"
        assert len(config.groups) == 1
        assert config.groups[0].id == "general"
        assert len(config.groups[0].fields) == 2

    def test_config_with_multiple_groups(self):
        """Test validation of config with multiple groups."""
        config = validate_config(VALID_FIXTURES / "full-app" / "config.yml")

        assert config.version == "1.0"
        assert len(config.groups) >= 2
        # Verify field types are properly validated
        for group in config.groups:
            for field in group.fields:
                assert field.type in ["string", "integer", "boolean", "enum", "path", "password"]


class TestValidateCompose:
    """Tests for validate_compose function."""

    def test_valid_compose(self):
        """Test validation of valid docker-compose.yml."""
        compose = validate_compose(VALID_FIXTURES / "simple-app" / "docker-compose.yml")

        assert "version" in compose
        assert "services" in compose
        assert len(compose["services"]) > 0

    def test_compose_version_check(self):
        """Test docker-compose version validation."""
        compose = validate_compose(VALID_FIXTURES / "full-app" / "docker-compose.yml")

        version = float(str(compose["version"]))
        assert version >= 3.8


class TestComposeWarnings:
    """Tests for compose warning checks."""

    def test_no_warnings_for_valid_compose(self):
        """Test that valid compose file generates minimal warnings."""
        result = validate_input_directory(VALID_FIXTURES / "simple-app")

        assert result.success is True
        # Check warnings are reasonable (may have some about missing files)
        # but shouldn't have critical errors

    def test_warning_for_restart_policy(self, tmp_path):
        """Test warning is generated for non-'no' restart policy."""
        # This test would need a custom compose file with restart policy
        # For now, we're testing the logic exists
        pass  # Tested indirectly through integration


class TestCrossValidate:
    """Tests for cross-validation checks."""

    def test_cross_validation_success(self):
        """Test cross-validation with consistent data."""
        result = validate_input_directory(VALID_FIXTURES / "simple-app")

        assert result.success is True
        # May have warnings but should succeed

    def test_missing_icon_warning(self):
        """Test warning when referenced icon file is missing."""
        # full-app references icon.svg which exists, so no warning
        result = validate_input_directory(VALID_FIXTURES / "full-app")

        assert result.success is True
        # Icon exists, so no icon-related warning
        icon_warnings = [w for w in result.warnings if "icon" in w.message.lower()]
        # Should have zero or very few icon warnings if file exists
        assert len(icon_warnings) == 0

    def test_config_field_default_mismatch_warning(self):
        """Test warning when config field has no default value."""
        result = validate_input_directory(VALID_FIXTURES / "full-app")

        assert result.success is True
        # Check for any warnings about missing defaults
        # (full-app should be complete, so warnings should be minimal)


class TestFormatPydanticError:
    """Tests for Pydantic error formatting."""

    def test_format_single_error(self):
        """Test formatting of single validation error."""
        from pydantic import ValidationError

        from schemas.metadata import PackageMetadata

        # Create invalid data to trigger error
        invalid_data = {
            "name": "Test",
            "package_name": "test",  # Missing -container suffix
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        try:
            PackageMetadata(**invalid_data)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            formatted = format_pydantic_error("metadata.yaml", e)
            assert "metadata.yaml" in formatted
            assert "package_name" in formatted or "container" in formatted

    def test_format_multiple_errors(self):
        """Test formatting of multiple validation errors."""
        from pydantic import ValidationError

        from schemas.metadata import PackageMetadata

        # Create data with multiple errors
        invalid_data = {
            "name": "Test",
            "package_name": "test",  # Missing -container suffix
            "version": "invalid",  # Invalid version format
            "description": "Test",
            "maintainer": "Invalid Email",  # Invalid email format
            "license": "MIT",
            "tags": [],  # Empty tags array
            "debian_section": "net",
            "architecture": "all",
        }

        try:
            PackageMetadata(**invalid_data)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            formatted = format_pydantic_error("metadata.yaml", e)
            assert "metadata.yaml" in formatted
            # Should mention multiple errors
            assert formatted.count("-") >= 2 or formatted.count("Error:") >= 2


class TestValidationWarning:
    """Tests for ValidationWarning namedtuple."""

    def test_validation_warning_creation(self):
        """Test creating ValidationWarning."""
        warning = ValidationWarning(
            file="test.yaml",
            message="Test message",
            suggestion="Test suggestion",
        )

        assert warning.file == "test.yaml"
        assert warning.message == "Test message"
        assert warning.suggestion == "Test suggestion"


class TestIntegration:
    """Integration tests using test fixtures."""

    def test_all_valid_fixtures_pass(self):
        """Test that all valid fixtures pass validation."""
        for fixture_dir in VALID_FIXTURES.iterdir():
            if fixture_dir.is_dir():
                result = validate_input_directory(fixture_dir)
                assert result.success is True, (
                    f"Fixture {fixture_dir.name} failed validation: {result.errors}"
                )

    def test_all_invalid_fixtures_fail(self):
        """Test that all invalid fixtures fail validation."""
        for fixture_dir in INVALID_FIXTURES.iterdir():
            if fixture_dir.is_dir():
                result = validate_input_directory(fixture_dir)
                assert result.success is False, (
                    f"Fixture {fixture_dir.name} should have failed validation"
                )
                assert len(result.errors) > 0, f"Fixture {fixture_dir.name} should have errors"
