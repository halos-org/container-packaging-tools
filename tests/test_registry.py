"""Unit tests for app registry file generation."""

import pytest

from generate_container_packages.registry import (
    generate_registry_toml,
    get_category_from_tags,
)


class TestGetCategoryFromTags:
    """Tests for category derivation from debtags."""

    def test_communication_category(self):
        """Test use::communication tag maps to Communication category."""
        tags = ["role::container-app", "use::communication"]
        assert get_category_from_tags(tags) == "Communication"

    def test_monitoring_category(self):
        """Test use::monitor tag maps to Monitoring category."""
        tags = ["role::container-app", "use::monitor"]
        assert get_category_from_tags(tags) == "Monitoring"

    def test_default_category(self):
        """Test unknown tags return default category."""
        tags = ["role::container-app", "unknown::tag"]
        assert get_category_from_tags(tags) == "Applications"

    def test_empty_tags(self):
        """Test empty tags return default category."""
        assert get_category_from_tags([]) == "Applications"


class TestGenerateRegistryToml:
    """Tests for TOML registry file generation."""

    # Test hostname for URL generation
    TEST_HOSTNAME = "test.example.local"

    @pytest.fixture
    def minimal_metadata(self):
        """Minimal metadata for testing."""
        return {
            "name": "Test App",
            "package_name": "halos-test-app-container",
            "description": "A test application",
            "tags": ["role::container-app"],
            "web_ui": {
                "enabled": True,
                "port": 8080,
                "protocol": "http",
                "path": "/",
                "visible": True,
            },
        }

    @pytest.fixture
    def minimal_compose(self):
        """Minimal docker-compose for testing."""
        return {"services": {"test-app": {"image": "test:latest"}}}

    def test_no_web_ui_returns_none(self, minimal_compose):
        """Test that apps without web_ui return None."""
        metadata = {"name": "Test", "tags": []}
        result = generate_registry_toml(metadata, minimal_compose, self.TEST_HOSTNAME)
        assert result is None

    def test_disabled_web_ui_returns_none(self, minimal_compose):
        """Test that apps with disabled web_ui return None."""
        metadata = {"name": "Test", "tags": [], "web_ui": {"enabled": False}}
        result = generate_registry_toml(metadata, minimal_compose, self.TEST_HOSTNAME)
        assert result is None

    def test_basic_toml_generation(self, minimal_metadata, minimal_compose):
        """Test basic TOML generation with minimal metadata."""
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert 'name = "Test App"' in result
        assert f'url = "http://{self.TEST_HOSTNAME}:8080/"' in result
        assert 'description = "A test application"' in result
        assert 'category = "Applications"' in result
        assert "visible = true" in result
        assert 'container_name = "test-app"' in result

    def test_default_layout_values(self, minimal_metadata, minimal_compose):
        """Test default layout values when no layout specified."""
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "[layout]" in result
        assert "priority = 50" in result
        assert "width = 1" in result
        assert "height = 1" in result
        # x_offset and y_offset should not be present by default
        assert "x_offset" not in result
        assert "y_offset" not in result

    def test_custom_layout_priority(self, minimal_metadata, minimal_compose):
        """Test custom priority in layout."""
        minimal_metadata["layout"] = {"priority": 30}
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "priority = 30" in result
        assert "width = 1" in result  # default
        assert "height = 1" in result  # default

    def test_custom_layout_size(self, minimal_metadata, minimal_compose):
        """Test custom width and height in layout."""
        minimal_metadata["layout"] = {"width": 2, "height": 3}
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "priority = 50" in result  # default
        assert "width = 2" in result
        assert "height = 3" in result

    def test_custom_layout_position(self, minimal_metadata, minimal_compose):
        """Test explicit x_offset and y_offset in layout."""
        minimal_metadata["layout"] = {"x_offset": 5, "y_offset": 2}
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "x_offset = 5" in result
        assert "y_offset = 2" in result

    def test_full_custom_layout(self, minimal_metadata, minimal_compose):
        """Test full custom layout with all fields."""
        minimal_metadata["layout"] = {
            "priority": 20,
            "width": 2,
            "height": 2,
            "x_offset": 0,
            "y_offset": 0,
        }
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "priority = 20" in result
        assert "width = 2" in result
        assert "height = 2" in result
        assert "x_offset = 0" in result
        assert "y_offset = 0" in result

    def test_url_without_port_for_default_http(self, minimal_metadata, minimal_compose):
        """Test URL omits port 80 for HTTP."""
        minimal_metadata["web_ui"]["port"] = 80
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert f'url = "http://{self.TEST_HOSTNAME}/"' in result

    def test_url_without_port_for_default_https(
        self, minimal_metadata, minimal_compose
    ):
        """Test URL omits port 443 for HTTPS."""
        minimal_metadata["web_ui"]["port"] = 443
        minimal_metadata["web_ui"]["protocol"] = "https"
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert f'url = "https://{self.TEST_HOSTNAME}/"' in result

    def test_url_with_custom_path(self, minimal_metadata, minimal_compose):
        """Test URL includes custom path."""
        minimal_metadata["web_ui"]["path"] = "/app"
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert f'url = "http://{self.TEST_HOSTNAME}:8080/app"' in result

    def test_escapes_special_characters(self, minimal_metadata, minimal_compose):
        """Test that special characters in name/description are escaped."""
        minimal_metadata["name"] = 'Test "App"'
        minimal_metadata["description"] = 'A "test" application'
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert 'name = "Test \\"App\\""' in result
        assert 'description = "A \\"test\\" application"' in result

    def test_icon_url_from_metadata(self, minimal_metadata, minimal_compose):
        """Test icon URL is generated from metadata icon field."""
        minimal_metadata["icon"] = "icon.png"
        result = generate_registry_toml(minimal_metadata, minimal_compose, self.TEST_HOSTNAME)

        assert result is not None
        assert 'icon_url = "/usr/share/pixmaps/halos-test-app-container.png"' in result

    def test_no_container_name_without_services(self, minimal_metadata):
        """Test handling when no services in compose."""
        compose = {"services": {}}
        result = generate_registry_toml(minimal_metadata, compose, self.TEST_HOSTNAME)

        assert result is not None
        assert "# No container_name" in result
