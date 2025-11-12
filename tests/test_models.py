"""Unit tests for Pydantic schema models."""

import pytest
from pydantic import ValidationError

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
        web_ui = WebUI(**data)
        assert web_ui.enabled is True
        assert web_ui.path == "/app"
        assert web_ui.port == 8080
        assert web_ui.protocol == "http"

    def test_minimal_web_ui(self):
        """Test WebUI with only required field."""
        data = {"enabled": False}
        web_ui = WebUI(**data)
        assert web_ui.enabled is False
        assert web_ui.path is None
        assert web_ui.port is None
        assert web_ui.protocol is None

    def test_invalid_port_too_low(self):
        """Test WebUI with port below valid range."""
        data = {"enabled": True, "port": 0}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_invalid_port_too_high(self):
        """Test WebUI with port above valid range."""
        data = {"enabled": True, "port": 70000}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)
        assert "less than or equal to 65535" in str(exc_info.value)

    def test_invalid_protocol(self):
        """Test WebUI with invalid protocol."""
        data = {"enabled": True, "protocol": "ftp"}
        with pytest.raises(ValidationError) as exc_info:
            WebUI(**data)
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
        metadata = PackageMetadata(**valid_metadata)
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
        metadata = PackageMetadata(**valid_metadata)
        assert metadata.upstream_version == "1.0.0"
        assert metadata.web_ui is not None
        assert metadata.web_ui.port == 8080
        assert metadata.default_config == {"PORT": "8080", "LOG_LEVEL": "info"}

    def test_missing_required_field(self, valid_metadata):
        """Test missing required field raises ValidationError."""
        del valid_metadata["name"]
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "name" in str(exc_info.value).lower()

    def test_invalid_package_name_pattern(self, valid_metadata):
        """Test invalid package name pattern raises ValidationError."""
        valid_metadata["package_name"] = "Test-App-Container"  # Uppercase not allowed
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "package_name" in str(exc_info.value).lower()

    def test_package_name_missing_container_suffix(self, valid_metadata):
        """Test package name without -container suffix raises ValidationError."""
        valid_metadata["package_name"] = "test-app"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "must end with '-container'" in str(exc_info.value)

    def test_invalid_version_format(self, valid_metadata):
        """Test invalid version format raises ValidationError."""
        valid_metadata["version"] = "v1.0"  # 'v' prefix not allowed
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "version" in str(exc_info.value).lower()

    def test_valid_version_with_debian_revision(self, valid_metadata):
        """Test version with Debian revision is valid."""
        valid_metadata["version"] = "1.2.3-1"
        metadata = PackageMetadata(**valid_metadata)
        assert metadata.version == "1.2.3-1"

    def test_valid_version_without_patch(self, valid_metadata):
        """Test version without patch number is valid."""
        valid_metadata["version"] = "2.1"
        metadata = PackageMetadata(**valid_metadata)
        assert metadata.version == "2.1"

    def test_description_too_long(self, valid_metadata):
        """Test description exceeding 80 characters raises ValidationError."""
        valid_metadata["description"] = "x" * 81
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "80" in str(exc_info.value)

    def test_invalid_maintainer_email(self, valid_metadata):
        """Test invalid maintainer email format raises ValidationError."""
        valid_metadata["maintainer"] = "Test Developer test@example.com"  # Missing angle brackets
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "maintainer" in str(exc_info.value).lower()

    def test_missing_required_tag(self, valid_metadata):
        """Test missing role::container-app tag raises ValidationError."""
        valid_metadata["tags"] = ["implemented-in::docker"]  # Missing role tag
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "role::container-app" in str(exc_info.value)

    def test_tags_with_multiple_values(self, valid_metadata):
        """Test tags can have multiple values."""
        valid_metadata["tags"] = [
            "role::container-app",
            "implemented-in::docker",
            "interface::web",
        ]
        metadata = PackageMetadata(**valid_metadata)
        assert len(metadata.tags) == 3
        assert "role::container-app" in metadata.tags

    def test_empty_tags_array(self, valid_metadata):
        """Test empty tags array raises ValidationError."""
        valid_metadata["tags"] = []
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "tags" in str(exc_info.value).lower()

    def test_invalid_debian_section(self, valid_metadata):
        """Test invalid debian_section raises ValidationError."""
        valid_metadata["debian_section"] = "invalid"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "debian_section" in str(exc_info.value).lower()

    def test_invalid_architecture(self, valid_metadata):
        """Test invalid architecture raises ValidationError."""
        valid_metadata["architecture"] = "x86"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "architecture" in str(exc_info.value).lower()

    def test_valid_architectures(self, valid_metadata):
        """Test all valid architecture values."""
        for arch in ["all", "amd64", "arm64", "armhf"]:
            valid_metadata["architecture"] = arch
            metadata = PackageMetadata(**valid_metadata)
            assert metadata.architecture == arch

    def test_invalid_homepage_url(self, valid_metadata):
        """Test invalid homepage URL raises ValidationError."""
        valid_metadata["homepage"] = "not-a-url"
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(**valid_metadata)
        assert "homepage" in str(exc_info.value).lower()

    def test_json_schema_export(self, valid_metadata):
        """Test that model can export JSON schema for documentation."""
        schema = PackageMetadata.model_json_schema()
        assert "properties" in schema
        assert "required" in schema
        assert "name" in schema["properties"]
        assert "package_name" in schema["properties"]
