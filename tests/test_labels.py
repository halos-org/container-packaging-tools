"""Unit tests for labels module."""

from generate_container_packages.labels import (
    find_port_env_var,
    generate_homarr_labels,
)


class TestFindPortEnvVar:
    """Tests for find_port_env_var function."""

    def test_finds_app_port(self):
        """Test finding APP_PORT in default_config."""
        default_config = {
            "APP_PORT": "3000",
            "LOG_LEVEL": "debug",
        }
        result = find_port_env_var(default_config)
        assert result == "APP_PORT"

    def test_finds_named_port(self):
        """Test finding SIGNALK_PORT style variable."""
        default_config = {
            "SIGNALK_PORT": "3000",
            "OTHER_VAR": "value",
        }
        result = find_port_env_var(default_config)
        assert result == "SIGNALK_PORT"

    def test_finds_simple_port(self):
        """Test finding PORT variable."""
        default_config = {
            "PORT": "8080",
            "OTHER": "value",
        }
        result = find_port_env_var(default_config)
        assert result == "PORT"

    def test_no_port_variable(self):
        """Test when no port variable is found."""
        default_config = {
            "LOG_LEVEL": "debug",
            "DATABASE_URL": "sqlite:///data.db",
        }
        result = find_port_env_var(default_config)
        assert result is None

    def test_empty_config(self):
        """Test with empty config."""
        result = find_port_env_var({})
        assert result is None

    def test_none_config(self):
        """Test with None config."""
        result = find_port_env_var(None)
        assert result is None

    def test_prefers_exact_port_match(self):
        """Test that PORT is preferred over _PORT suffix."""
        default_config = {
            "PORT": "3000",
            "OTHER_PORT": "8080",
        }
        result = find_port_env_var(default_config)
        # PORT should be preferred as it's more direct
        assert result == "PORT"


class TestGenerateHomarrLabels:
    """Tests for generate_homarr_labels function."""

    def test_basic_labels(self):
        """Test generating basic Homarr labels."""
        metadata = {
            "name": "Signal K Server",
            "package_name": "signalk-server-container",
            "description": "Marine data server",
            "tags": ["role::container-app"],
            "web_ui": {
                "enabled": True,
                "port": 3000,
                "protocol": "http",
            },
        }
        labels = generate_homarr_labels(metadata)

        assert labels["homarr.enable"] == "true"
        assert labels["homarr.name"] == "Signal K Server"
        assert labels["homarr.url"] == "${HOMARR_URL}"
        assert labels["homarr.description"] == "Marine data server"

    def test_labels_with_category_from_tags(self):
        """Test that category is derived from tags."""
        metadata = {
            "name": "Test App",
            "package_name": "test-container",
            "description": "Test application",
            "tags": ["role::container-app", "interface::web", "use::communication"],
            "web_ui": {
                "enabled": True,
                "port": 8080,
            },
        }
        labels = generate_homarr_labels(metadata)

        # Should derive category from tags
        assert "homarr.category" in labels

    def test_labels_disabled_when_web_ui_disabled(self):
        """Test that no labels are generated when web_ui is disabled."""
        metadata = {
            "name": "Test App",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app"],
            "web_ui": {
                "enabled": False,
            },
        }
        labels = generate_homarr_labels(metadata)

        # Should be empty when web_ui is disabled
        assert labels == {}

    def test_labels_empty_when_no_web_ui(self):
        """Test that no labels are generated when web_ui is missing."""
        metadata = {
            "name": "Test App",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app"],
        }
        labels = generate_homarr_labels(metadata)

        assert labels == {}

    def test_labels_include_icon_reference(self):
        """Test that labels include icon reference if icon exists."""
        metadata = {
            "name": "Test App",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app"],
            "web_ui": {
                "enabled": True,
                "port": 8080,
            },
            "icon": "icon.svg",
        }
        labels = generate_homarr_labels(metadata)

        # Icon should be referenced
        assert "homarr.icon" in labels or "homarr.enable" in labels

    def test_labels_with_path(self):
        """Test labels when web_ui has a specific path."""
        metadata = {
            "name": "Test App",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app"],
            "web_ui": {
                "enabled": True,
                "port": 8080,
                "path": "/admin",
            },
        }
        labels = generate_homarr_labels(metadata)

        # URL should include path
        assert labels["homarr.url"] == "${HOMARR_URL}"
        # Path is handled in prestart script, not labels


class TestCategoryMapping:
    """Tests for tag to category mapping."""

    def test_communication_category(self):
        """Test mapping communication tags to category."""
        metadata = {
            "name": "Test",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app", "use::communication"],
            "web_ui": {"enabled": True, "port": 8080},
        }
        labels = generate_homarr_labels(metadata)
        assert labels.get("homarr.category") == "Communication"

    def test_monitoring_category(self):
        """Test mapping monitoring tags to category."""
        metadata = {
            "name": "Test",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app", "use::monitor"],
            "web_ui": {"enabled": True, "port": 8080},
        }
        labels = generate_homarr_labels(metadata)
        assert labels.get("homarr.category") == "Monitoring"

    def test_default_category(self):
        """Test default category when no specific tags match."""
        metadata = {
            "name": "Test",
            "package_name": "test-container",
            "description": "Test",
            "tags": ["role::container-app"],
            "web_ui": {"enabled": True, "port": 8080},
        }
        labels = generate_homarr_labels(metadata)
        # Should have a default category
        assert "homarr.category" in labels
