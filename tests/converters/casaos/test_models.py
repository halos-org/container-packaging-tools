"""Unit tests for CasaOS converter Pydantic models."""

from typing import Any

import pytest
from pydantic import ValidationError

from generate_container_packages.converters.casaos.models import (
    CasaOSApp,
    CasaOSEnvVar,
    CasaOSPort,
    CasaOSService,
    CasaOSVolume,
    ConversionContext,
)


class TestCasaOSEnvVar:
    """Tests for CasaOSEnvVar model."""

    def test_valid_env_var_minimal(self):
        """Test minimal valid environment variable."""
        data: dict[str, Any] = {
            "name": "API_KEY",
            "default": "changeme",
        }
        env_var = CasaOSEnvVar(**data)
        assert env_var.name == "API_KEY"
        assert env_var.default == "changeme"
        assert env_var.label is None
        assert env_var.description is None
        assert env_var.type is None

    def test_valid_env_var_full(self):
        """Test fully populated environment variable."""
        data: dict[str, Any] = {
            "name": "SERVER_PORT",
            "default": "8080",
            "label": "Server Port",
            "description": "Port for the web server",
            "type": "number",
        }
        env_var = CasaOSEnvVar(**data)
        assert env_var.name == "SERVER_PORT"
        assert env_var.default == "8080"
        assert env_var.label == "Server Port"
        assert env_var.description == "Port for the web server"
        assert env_var.type == "number"

    def test_invalid_empty_name(self):
        """Test that empty name is rejected."""
        data: dict[str, Any] = {"name": "", "default": "value"}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSEnvVar(**data)
        assert "name" in str(exc_info.value).lower()


class TestCasaOSPort:
    """Tests for CasaOSPort model."""

    def test_valid_port_minimal(self):
        """Test minimal valid port configuration."""
        data: dict[str, Any] = {
            "container": 80,
            "host": 8080,
        }
        port = CasaOSPort(**data)
        assert port.container == 80
        assert port.host == 8080
        assert port.protocol is None
        assert port.description is None

    def test_valid_port_with_protocol(self):
        """Test port with protocol specification."""
        data: dict[str, Any] = {
            "container": 443,
            "host": 8443,
            "protocol": "tcp",
            "description": "HTTPS port",
        }
        port = CasaOSPort(**data)
        assert port.container == 443
        assert port.host == 8443
        assert port.protocol == "tcp"
        assert port.description == "HTTPS port"

    def test_invalid_port_range_container(self):
        """Test that invalid container port is rejected."""
        data: dict[str, Any] = {"container": 0, "host": 8080}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSPort(**data)
        assert "container" in str(exc_info.value).lower()

    def test_invalid_port_range_host(self):
        """Test that invalid host port is rejected."""
        data: dict[str, Any] = {"container": 80, "host": 70000}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSPort(**data)
        assert "host" in str(exc_info.value).lower()

    def test_invalid_protocol(self):
        """Test that invalid protocol is rejected."""
        data: dict[str, Any] = {"container": 80, "host": 8080, "protocol": "invalid"}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSPort(**data)
        assert "protocol" in str(exc_info.value).lower()


class TestCasaOSVolume:
    """Tests for CasaOSVolume model."""

    def test_valid_volume_minimal(self):
        """Test minimal valid volume configuration."""
        data: dict[str, Any] = {
            "container": "/data",
            "host": "/mnt/data",
        }
        volume = CasaOSVolume(**data)
        assert volume.container == "/data"
        assert volume.host == "/mnt/data"
        assert volume.mode is None
        assert volume.description is None

    def test_valid_volume_with_mode(self):
        """Test volume with read-only mode."""
        data: dict[str, Any] = {
            "container": "/config",
            "host": "/app/config",
            "mode": "ro",
            "description": "Configuration directory",
        }
        volume = CasaOSVolume(**data)
        assert volume.container == "/config"
        assert volume.host == "/app/config"
        assert volume.mode == "ro"
        assert volume.description == "Configuration directory"

    def test_invalid_empty_container_path(self):
        """Test that empty container path is rejected."""
        data: dict[str, Any] = {"container": "", "host": "/mnt/data"}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSVolume(**data)
        assert "container" in str(exc_info.value).lower()

    def test_invalid_empty_host_path(self):
        """Test that empty host path is rejected."""
        data: dict[str, Any] = {"container": "/data", "host": ""}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSVolume(**data)
        assert "host" in str(exc_info.value).lower()


class TestCasaOSService:
    """Tests for CasaOSService model."""

    def test_valid_service_minimal(self):
        """Test minimal valid service configuration."""
        data: dict[str, Any] = {
            "name": "web",
            "image": "nginx:latest",
        }
        service = CasaOSService(**data)
        assert service.name == "web"
        assert service.image == "nginx:latest"
        assert service.environment == []
        assert service.ports == []
        assert service.volumes == []

    def test_valid_service_with_config(self):
        """Test service with full configuration."""
        data: dict[str, Any] = {
            "name": "app",
            "image": "myapp:1.0",
            "environment": [
                {"name": "DEBUG", "default": "false"},
            ],
            "ports": [
                {"container": 80, "host": 8080},
            ],
            "volumes": [
                {"container": "/data", "host": "/mnt/data"},
            ],
            "command": ["npm", "start"],
            "entrypoint": ["/entrypoint.sh"],
        }
        service = CasaOSService(**data)
        assert service.name == "app"
        assert service.image == "myapp:1.0"
        assert len(service.environment) == 1
        assert service.environment[0].name == "DEBUG"
        assert len(service.ports) == 1
        assert service.ports[0].container == 80
        assert len(service.volumes) == 1
        assert service.volumes[0].container == "/data"
        assert service.command == ["npm", "start"]
        assert service.entrypoint == ["/entrypoint.sh"]

    def test_invalid_empty_service_name(self):
        """Test that empty service name is rejected."""
        data: dict[str, Any] = {"name": "", "image": "nginx:latest"}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSService(**data)
        assert "name" in str(exc_info.value).lower()

    def test_invalid_empty_image(self):
        """Test that empty image is rejected."""
        data: dict[str, Any] = {"name": "web", "image": ""}
        with pytest.raises(ValidationError) as exc_info:
            CasaOSService(**data)
        assert "image" in str(exc_info.value).lower()


class TestCasaOSApp:
    """Tests for CasaOSApp model."""

    def test_valid_app_minimal(self):
        """Test minimal valid app definition."""
        data: dict[str, Any] = {
            "id": "my-app",
            "name": "My App",
            "tagline": "A simple app",
            "description": "This is my application",
            "category": "utilities",
            "services": [
                {"name": "main", "image": "myapp:latest"},
            ],
        }
        app = CasaOSApp(**data)
        assert app.id == "my-app"
        assert app.name == "My App"
        assert app.tagline == "A simple app"
        assert app.description == "This is my application"
        assert app.category == "utilities"
        assert len(app.services) == 1
        assert app.services[0].name == "main"
        assert app.icon is None
        assert app.screenshots == []
        assert app.tags == []

    def test_valid_app_full(self):
        """Test fully populated app definition."""
        data: dict[str, Any] = {
            "id": "jellyfin",
            "name": "Jellyfin",
            "tagline": "Media server",
            "description": "Free software media system",
            "category": "media",
            "developer": "Jellyfin Team",
            "homepage": "https://jellyfin.org",
            "icon": "https://example.com/icon.png",
            "screenshots": [
                "https://example.com/screen1.png",
                "https://example.com/screen2.png",
            ],
            "tags": ["media", "streaming", "video"],
            "services": [
                {
                    "name": "jellyfin",
                    "image": "jellyfin/jellyfin:latest",
                    "environment": [
                        {"name": "TZ", "default": "UTC"},
                    ],
                    "ports": [
                        {"container": 8096, "host": 8096},
                    ],
                    "volumes": [
                        {"container": "/config", "host": "/DATA/AppData/jellyfin"},
                        {"container": "/media", "host": "/media"},
                    ],
                },
            ],
        }
        app = CasaOSApp(**data)
        assert app.id == "jellyfin"
        assert app.name == "Jellyfin"
        assert app.tagline == "Media server"
        assert app.category == "media"
        assert app.developer == "Jellyfin Team"
        assert app.homepage == "https://jellyfin.org"
        assert app.icon == "https://example.com/icon.png"
        assert len(app.screenshots) == 2
        assert len(app.tags) == 3
        assert len(app.services) == 1
        assert len(app.services[0].environment) == 1
        assert len(app.services[0].ports) == 1
        assert len(app.services[0].volumes) == 2

    def test_invalid_empty_app_id(self):
        """Test that empty app ID is rejected."""
        data: dict[str, Any] = {
            "id": "",
            "name": "App",
            "tagline": "Tag",
            "description": "Desc",
            "category": "utils",
            "services": [{"name": "main", "image": "img:latest"}],
        }
        with pytest.raises(ValidationError) as exc_info:
            CasaOSApp(**data)
        assert "id" in str(exc_info.value).lower()

    def test_invalid_empty_services(self):
        """Test that app requires at least one service."""
        data: dict[str, Any] = {
            "id": "app",
            "name": "App",
            "tagline": "Tag",
            "description": "Desc",
            "category": "utils",
            "services": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            CasaOSApp(**data)
        assert "services" in str(exc_info.value).lower()

    def test_multiple_services(self):
        """Test app with multiple services."""
        data: dict[str, Any] = {
            "id": "multi-app",
            "name": "Multi Service App",
            "tagline": "Multiple services",
            "description": "App with database and web server",
            "category": "utilities",
            "services": [
                {"name": "web", "image": "nginx:latest"},
                {"name": "db", "image": "postgres:15"},
            ],
        }
        app = CasaOSApp(**data)
        assert len(app.services) == 2
        assert app.services[0].name == "web"
        assert app.services[1].name == "db"


class TestConversionContext:
    """Tests for ConversionContext model."""

    def test_valid_context_minimal(self):
        """Test minimal conversion context."""
        data: dict[str, Any] = {
            "source_format": "casaos",
            "app_id": "my-app",
        }
        context = ConversionContext(**data)
        assert context.source_format == "casaos"
        assert context.app_id == "my-app"
        assert context.warnings == []
        assert context.errors == []
        assert context.downloaded_assets == []

    def test_valid_context_with_warnings(self):
        """Test conversion context with warnings."""
        data: dict[str, Any] = {
            "source_format": "casaos",
            "app_id": "test-app",
            "warnings": ["Missing icon URL", "Unknown category"],
        }
        context = ConversionContext(**data)
        assert len(context.warnings) == 2
        assert "Missing icon URL" in context.warnings

    def test_valid_context_with_errors(self):
        """Test conversion context with errors."""
        data: dict[str, Any] = {
            "source_format": "casaos",
            "app_id": "test-app",
            "errors": ["Invalid port configuration"],
        }
        context = ConversionContext(**data)
        assert len(context.errors) == 1
        assert "Invalid port configuration" in context.errors

    def test_valid_context_with_assets(self):
        """Test conversion context tracking downloaded assets."""
        data: dict[str, Any] = {
            "source_format": "casaos",
            "app_id": "test-app",
            "downloaded_assets": [
                "/tmp/icon.png",
                "/tmp/screenshot1.png",
            ],
        }
        context = ConversionContext(**data)
        assert len(context.downloaded_assets) == 2
        assert "/tmp/icon.png" in context.downloaded_assets

    def test_invalid_empty_source_format(self):
        """Test that empty source format is rejected."""
        data: dict[str, Any] = {"source_format": "", "app_id": "app"}
        with pytest.raises(ValidationError) as exc_info:
            ConversionContext(**data)
        assert "source_format" in str(exc_info.value).lower()

    def test_invalid_empty_app_id(self):
        """Test that empty app ID is rejected."""
        data: dict[str, Any] = {"source_format": "casaos", "app_id": ""}
        with pytest.raises(ValidationError) as exc_info:
            ConversionContext(**data)
        assert "app_id" in str(exc_info.value).lower()
