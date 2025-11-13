"""Unit tests for Pydantic schema models."""

import pytest
from pydantic import ValidationError

from schemas.config import ConfigField, ConfigGroup, ConfigSchema
from schemas.metadata import PackageMetadata, WebUI


class TestWebUI:
    """Tests for WebUI nested model."""

    def test_valid_web_ui(self):
        """Test valid WebUI configuration."""
        data = {
            "enabled": True,
            "path": "/app",
            "port": 8080,
            "protocol": "http",
        }
        web_ui = WebUI(**data)  # type: ignore[arg-type]
        assert web_ui.enabled is True
        assert web_ui.path == "/app"
        assert web_ui.port == 8080
        assert web_ui.protocol == "http"

    def test_minimal_web_ui(self):
        """Test WebUI with only required field."""
        data = {"enabled": False}
        web_ui = WebUI(**data)  # type: ignore[arg-type]
        assert web_ui.enabled is False
        assert web_ui.path is None
        assert web_ui.port is None
        assert web_ui.protocol is None

    def test_invalid_port_too_low(self):
        """Test WebUI with port below valid range."""
        data = {"enabled": True, "port": 0}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)  # type: ignore[arg-type]
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_invalid_port_too_high(self):
        """Test WebUI with port above valid range."""
        data = {"enabled": True, "port": 70000}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)  # type: ignore[arg-type]
        assert "less than or equal to 65535" in str(exc_info.value)

    def test_invalid_protocol(self):
        """Test WebUI with invalid protocol."""
        data = {"enabled": True, "protocol": "ftp"}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)  # type: ignore[arg-type]
        assert "protocol" in str(exc_info.value).lower()


class TestPackageMetadata:
    """Tests for PackageMetadata model."""

    @pytest.fixture
    def valid_metadata(self):
        """Minimal valid metadata."""
        return {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Test Developer <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

    def test_valid_minimal_metadata(self, valid_metadata):
        """Test minimal valid metadata passes validation."""
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]  # type: ignore[arg-type]
        assert metadata.name == "Test App"
        assert metadata.package_name == "test-app-container"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test application"

    def test_valid_complete_metadata(self, valid_metadata):
        """Test complete metadata with all optional fields."""
        valid_metadata.update(
            {
                "upstream_version": "1.0.0",
                "long_description": "This is a longer description.",
                "homepage": "https://example.com",
                "icon": "icon.png",
                "screenshots": ["screenshot1.png", "screenshot2.png"],
                "depends": ["docker-ce"],
                "recommends": ["cockpit"],
                "suggests": ["nginx"],
                "web_ui": {
                    "enabled": True,
                    "path": "/",
                    "port": 8080,
                    "protocol": "http",
                },
                "default_config": {"PORT": "8080", "LOG_LEVEL": "info"},
            }
        )
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.upstream_version == "1.0.0"
        assert metadata.web_ui is not None
        assert metadata.web_ui.port == 8080
        assert metadata.default_config == {"PORT": "8080", "LOG_LEVEL": "info"}

    def test_missing_required_field(self, valid_metadata):
        """Test missing required field raises ValidationError."""
        del valid_metadata["name"]
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "name" in str(exc_info.value).lower()

    def test_invalid_package_name_pattern(self, valid_metadata):
        """Test invalid package name pattern raises ValidationError."""
        valid_metadata["package_name"] = "Test-App-Container"  # Uppercase not allowed
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "package_name" in str(exc_info.value).lower()

    def test_package_name_missing_container_suffix(self, valid_metadata):
        """Test package name without -container suffix raises ValidationError."""
        valid_metadata["package_name"] = "test-app"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "must end with '-container'" in str(exc_info.value)

    def test_invalid_version_format(self, valid_metadata):
        """Test invalid version format raises ValidationError."""
        valid_metadata["version"] = "v1.0"  # 'v' prefix not allowed
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "version" in str(exc_info.value).lower()

    def test_valid_version_with_debian_revision(self, valid_metadata):
        """Test version with Debian revision is valid (semver)."""
        valid_metadata["version"] = "1.2.3-1"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "1.2.3-1"

    def test_valid_version_without_patch(self, valid_metadata):
        """Test version without patch number is valid (semver)."""
        valid_metadata["version"] = "2.1"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "2.1"

    def test_valid_version_date_based(self, valid_metadata):
        """Test date-based version is valid (YYYYMMDD format)."""
        valid_metadata["version"] = "20250113"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "20250113"

    def test_valid_version_calver(self, valid_metadata):
        """Test CalVer version is valid (YYYY.MM.DD format)."""
        valid_metadata["version"] = "2025.01.13"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "2025.01.13"

    def test_valid_version_hybrid(self, valid_metadata):
        """Test hybrid version is valid (semver + git date)."""
        valid_metadata["version"] = "5.8.4+git20250113"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "5.8.4+git20250113"

    def test_valid_version_with_epoch(self, valid_metadata):
        """Test version with epoch is valid."""
        valid_metadata["version"] = "1:2.8.0"
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert metadata.version == "1:2.8.0"

    def test_invalid_version_empty(self, valid_metadata):
        """Test empty version raises ValidationError."""
        valid_metadata["version"] = ""
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "version" in str(exc_info.value).lower()

    def test_invalid_version_whitespace(self, valid_metadata):
        """Test whitespace-only version raises ValidationError."""
        valid_metadata["version"] = "   "
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "version" in str(exc_info.value).lower()

    def test_description_too_long(self, valid_metadata):
        """Test description exceeding 80 characters raises ValidationError."""
        valid_metadata["description"] = "x" * 81
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "80" in str(exc_info.value)

    def test_invalid_maintainer_email(self, valid_metadata):
        """Test invalid maintainer email format raises ValidationError."""
        valid_metadata["maintainer"] = (
            "Test Developer test@example.com"  # Missing angle brackets
        )
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "maintainer" in str(exc_info.value).lower()

    def test_missing_required_tag(self, valid_metadata):
        """Test missing role::container-app tag raises ValidationError."""
        valid_metadata["tags"] = ["implemented-in::docker"]  # Missing role tag
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "role::container-app" in str(exc_info.value)

    def test_tags_with_multiple_values(self, valid_metadata):
        """Test tags can have multiple values."""
        valid_metadata["tags"] = [
            "role::container-app",
            "implemented-in::docker",
            "interface::web",
        ]
        metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert len(metadata.tags) == 3
        assert "role::container-app" in metadata.tags

    def test_empty_tags_array(self, valid_metadata):
        """Test empty tags array raises ValidationError."""
        valid_metadata["tags"] = []
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "tags" in str(exc_info.value).lower()

    def test_invalid_debian_section(self, valid_metadata):
        """Test invalid debian_section raises ValidationError."""
        valid_metadata["debian_section"] = "invalid"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "debian_section" in str(exc_info.value).lower()

    def test_invalid_architecture(self, valid_metadata):
        """Test invalid architecture raises ValidationError."""
        valid_metadata["architecture"] = "x86"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "architecture" in str(exc_info.value).lower()

    def test_valid_architectures(self, valid_metadata):
        """Test all valid architecture values."""
        for arch in ["all", "amd64", "arm64", "armhf"]:
            valid_metadata["architecture"] = arch
            metadata = PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
            assert metadata.architecture == arch

    def test_invalid_homepage_url(self, valid_metadata):
        """Test invalid homepage URL raises ValidationError."""
        valid_metadata["homepage"] = "not-a-url"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)  # type: ignore[arg-type]
        assert "homepage" in str(exc_info.value).lower()

    def test_json_schema_export(self, valid_metadata):
        """Test that model can export JSON schema for documentation."""
        schema = PackageMetadata.model_json_schema()
        assert "properties" in schema
        assert "required" in schema
        assert "name" in schema["properties"]
        assert "package_name" in schema["properties"]


class TestConfigField:
    """Tests for ConfigField model."""

    def test_valid_config_field(self):
        """Test valid configuration field."""
        data = {
            "id": "APP_PORT",
            "label": "Application Port",
            "type": "integer",
            "default": 8080,
            "required": True,
            "min": 1024,
            "max": 65535,
            "description": "Port for the application",
        }

        field = ConfigField(**data)  # type: ignore[arg-type]
        assert field.id == "APP_PORT"
        assert field.type == "integer"
        assert field.min == 1024

    def test_enum_field_with_options(self):
        """Test enum field with valid options."""
        data = {
            "id": "LOG_LEVEL",
            "label": "Log Level",
            "type": "enum",
            "default": "info",
            "required": False,
            "options": ["debug", "info", "warning", "error"],
        }

        field = ConfigField(**data)  # type: ignore[arg-type]
        assert field.type == "enum"
        assert field.options is not None
        assert len(field.options) == 4

    def test_enum_field_without_options(self):
        """Test enum field without options raises ValidationError."""
        data = {
            "id": "LOG_LEVEL",
            "label": "Log Level",
            "type": "enum",
            "default": "info",
            "required": False,
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigField(**data)  # type: ignore[arg-type]
        assert "options" in str(exc_info.value).lower()

    def test_invalid_field_id_lowercase(self):
        """Test field ID with lowercase raises ValidationError."""
        data = {
            "id": "app_port",  # Should be UPPER_SNAKE_CASE
            "label": "Application Port",
            "type": "integer",
            "default": 8080,
            "required": True,
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigField(**data)  # type: ignore[arg-type]
        assert "id" in str(exc_info.value).lower()

    def test_invalid_field_id_hyphen(self):
        """Test field ID with hyphen raises ValidationError."""
        data = {
            "id": "APP-PORT",  # Should use underscore not hyphen
            "label": "Application Port",
            "type": "integer",
            "default": 8080,
            "required": True,
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigField(**data)  # type: ignore[arg-type]
        assert "id" in str(exc_info.value).lower()

    def test_all_field_types(self):
        """Test all valid field types."""

        types = ["string", "integer", "boolean", "enum", "path", "password"]
        for field_type in types:
            data = {
                "id": "TEST_FIELD",
                "label": "Test",
                "type": field_type,
                "default": "test",
                "required": False,
            }
            if field_type == "enum":
                data["options"] = ["test"]
            field = ConfigField(**data)  # type: ignore[arg-type]
            assert field.type == field_type


class TestConfigGroup:
    """Tests for ConfigGroup model."""

    def test_valid_config_group(self):
        """Test valid configuration group."""
        data = {
            "id": "general",
            "label": "General Settings",
            "description": "Basic settings",
            "fields": [
                {
                    "id": "APP_PORT",
                    "label": "Port",
                    "type": "integer",
                    "default": 8080,
                    "required": True,
                }
            ],
        }

        group = ConfigGroup(**data)  # type: ignore[arg-type]
        assert group.id == "general"
        assert len(group.fields) == 1

    def test_invalid_group_id_uppercase(self):
        """Test group ID with uppercase raises ValidationError."""
        data = {
            "id": "GENERAL",  # Should be lowercase_snake_case
            "label": "General",
            "fields": [
                {
                    "id": "PORT",
                    "label": "Port",
                    "type": "string",
                    "default": "8080",
                    "required": True,
                }
            ],
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigGroup(**data)  # type: ignore[arg-type]
        assert "id" in str(exc_info.value).lower()

    def test_invalid_group_id_hyphen(self):
        """Test group ID with hyphen raises ValidationError."""
        data = {
            "id": "general-settings",  # Should use underscore
            "label": "General",
            "fields": [
                {
                    "id": "PORT",
                    "label": "Port",
                    "type": "string",
                    "default": "8080",
                    "required": True,
                }
            ],
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigGroup(**data)  # type: ignore[arg-type]
        assert "id" in str(exc_info.value).lower()

    def test_empty_fields_array(self):
        """Test group with no fields raises ValidationError."""
        data = {"id": "general", "label": "General", "fields": []}

        with pytest.raises(ValidationError) as exc_info:
            ConfigGroup(**data)  # type: ignore[arg-type]
        assert "fields" in str(exc_info.value).lower()


class TestConfigSchema:
    """Tests for ConfigSchema model."""

    @pytest.fixture
    def valid_config_schema(self):
        """Minimal valid config schema."""
        return {
            "version": "1.0",
            "groups": [
                {
                    "id": "general",
                    "label": "General Settings",
                    "fields": [
                        {
                            "id": "APP_PORT",
                            "label": "Application Port",
                            "type": "integer",
                            "default": 8080,
                            "required": True,
                        }
                    ],
                }
            ],
        }

    def test_valid_config_schema(self, valid_config_schema):
        """Test valid configuration schema."""

        schema = ConfigSchema(**valid_config_schema)  # type: ignore[arg-type]
        assert schema.version == "1.0"
        assert len(schema.groups) == 1
        assert schema.groups[0].id == "general"

    def test_complex_config_schema(self, valid_config_schema):
        """Test complex configuration schema with multiple groups."""
        valid_config_schema["groups"].append(
            {
                "id": "database",
                "label": "Database Settings",
                "description": "Database connection",
                "fields": [
                    {
                        "id": "DB_URL",
                        "label": "Database URL",
                        "type": "string",
                        "default": "sqlite:///data/app.db",
                        "required": True,
                    },
                    {
                        "id": "DB_POOL_SIZE",
                        "label": "Connection Pool Size",
                        "type": "integer",
                        "default": 10,
                        "required": False,
                        "min": 1,
                        "max": 100,
                    },
                ],
            }
        )

        schema = ConfigSchema(**valid_config_schema)  # type: ignore[arg-type]
        assert len(schema.groups) == 2
        assert schema.groups[1].id == "database"
        assert len(schema.groups[1].fields) == 2

    def test_invalid_version(self, valid_config_schema):
        """Test invalid version format raises ValidationError."""
        valid_config_schema["version"] = "2.0"

        with pytest.raises(ValidationError) as exc_info:
            ConfigSchema(**valid_config_schema)  # type: ignore[arg-type]
        assert "version" in str(exc_info.value).lower()

    def test_empty_groups_array(self, valid_config_schema):
        """Test schema with no groups raises ValidationError."""
        valid_config_schema["groups"] = []

        with pytest.raises(ValidationError) as exc_info:
            ConfigSchema(**valid_config_schema)  # type: ignore[arg-type]
        assert "groups" in str(exc_info.value).lower()
