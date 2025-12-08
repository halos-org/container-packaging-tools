"""Unit tests for prestart script generation."""

from unittest import mock

from generate_container_packages.loader import AppDefinition
from generate_container_packages.prestart import (
    generate_prestart_script,
    get_homarr_url_expression,
)


class TestGetHomarrUrlExpression:
    """Tests for get_homarr_url_expression function."""

    def test_http_with_port_var(self):
        """Test URL expression with http protocol and port variable."""
        web_ui = {"enabled": True, "protocol": "http", "port": 3000}
        default_config = {"APP_PORT": "3000"}

        result = get_homarr_url_expression(web_ui, default_config)

        # Should use APP_PORT with fallback to 3000
        assert "http://" in result
        assert "${APP_PORT:-3000}" in result
        assert "${HOSTNAME}.local" in result

    def test_https_protocol(self):
        """Test URL expression with https protocol."""
        web_ui = {"enabled": True, "protocol": "https", "port": 8443}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert "https://" in result
        assert ":8443" in result

    def test_with_path(self):
        """Test URL expression with path."""
        web_ui = {"enabled": True, "protocol": "http", "port": 8080, "path": "/admin"}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert "/admin" in result

    def test_default_protocol_is_http(self):
        """Test that default protocol is http when not specified."""
        web_ui = {"enabled": True, "port": 8080}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert "http://" in result

    def test_disabled_web_ui_returns_none(self):
        """Test that disabled web_ui returns None."""
        web_ui = {"enabled": False, "port": 8080}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert result is None


class TestGeneratePrestartScript:
    """Tests for generate_prestart_script function."""

    def test_basic_script_structure(self):
        """Test that prestart script has correct basic structure."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Check shebang
        assert script.startswith("#!/bin/bash")
        # Check set -e for error handling
        assert "set -e" in script
        # Check runtime env directory
        assert "/run/container-apps/test-app-container" in script
        # Check HOSTNAME is set
        assert "HOSTNAME=" in script
        assert "hostname -s" in script

    def test_script_loads_env_files(self):
        """Test that script loads existing env files."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Should load env.defaults and env
        assert "/etc/container-apps/test-app-container/env.defaults" in script
        assert "/etc/container-apps/test-app-container/env" in script
        # Should use source/dot command
        assert ". " in script or "source " in script

    def test_script_generates_homarr_url(self):
        """Test that script generates HOMARR_URL when web_ui is enabled."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "default_config": {"APP_PORT": "3000"},
        }

        script = generate_prestart_script(app_def)

        # Should set HOMARR_URL
        assert "HOMARR_URL=" in script
        assert "${HOSTNAME}.local" in script

    def test_script_without_web_ui(self):
        """Test script when web_ui is not enabled."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": False},
        }

        script = generate_prestart_script(app_def)

        # Should still set HOSTNAME
        assert "HOSTNAME=" in script
        # Should NOT set HOMARR_URL
        assert "HOMARR_URL=" not in script

    def test_script_without_web_ui_key(self):
        """Test script when web_ui key is missing."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
        }

        script = generate_prestart_script(app_def)

        # Should still generate a valid script with HOSTNAME
        assert "HOSTNAME=" in script
        assert "HOMARR_URL=" not in script

    def test_script_writes_to_runtime_env(self):
        """Test that script writes variables to runtime.env."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Should write to runtime.env
        assert "runtime.env" in script
        # Should echo variables to file
        assert "echo" in script or ">>" in script

    def test_script_creates_runtime_directory(self):
        """Test that script creates the runtime directory."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
        }

        script = generate_prestart_script(app_def)

        # Should create directory with mkdir -p
        assert "mkdir -p" in script

    def test_script_is_executable_bash(self):
        """Test that script is valid executable bash syntax."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "signal-k-container",
            "name": "Signal K",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "default_config": {"SIGNALK_PORT": "3000"},
        }

        script = generate_prestart_script(app_def)

        # Basic bash syntax checks
        assert script.startswith("#!/bin/bash")
        # No unclosed quotes (basic check)
        assert script.count('"') % 2 == 0
