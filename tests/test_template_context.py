"""Unit tests for template context builder."""

from pathlib import Path

from generate_container_packages.loader import AppDefinition
from generate_container_packages.template_context import (
    build_context,
    format_dependencies,
    format_long_description,
)


class TestBuildContext:
    """Tests for build_context function."""

    def test_minimal_app_context(self):
        """Test context building with minimal app definition."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        app_def = AppDefinition(
            metadata=metadata, compose={}, config={}, icon_path=None, screenshot_paths=[]
        )

        context = build_context(app_def)

        # Verify package context
        assert context["package"]["name"] == "test-app-container"
        assert context["package"]["version"] == "1.0.0"
        assert context["package"]["human_name"] == "Test App"
        assert context["package"]["description"] == "A test application"
        assert context["package"]["architecture"] == "all"
        assert context["package"]["section"] == "net"
        assert context["package"]["maintainer"] == "Test <test@example.com>"
        assert context["package"]["license"] == "MIT"

        # Verify service context
        assert context["service"]["name"] == "test-app-container.service"
        assert context["service"]["description"] == "Test App Container"
        assert (
            context["service"]["working_directory"] == "/var/lib/container-apps/test-app-container"
        )
        assert context["service"]["env_file"] == "/etc/container-apps/test-app-container/.env"

        # Verify paths
        assert context["paths"]["lib"] == "/var/lib/container-apps/test-app-container"
        assert context["paths"]["etc"] == "/etc/container-apps/test-app-container"
        assert context["paths"]["systemd"] == "/etc/systemd/system"

        # Verify optional fields
        assert context["has_icon"] is False
        assert context["icon_extension"] == ""
        assert context["has_screenshots"] is False

    def test_full_app_context_with_icon(self):
        """Test context building with all optional fields."""
        metadata = {
            "name": "Full Test App",
            "package_name": "full-test-app-container",
            "version": "2.1.0",
            "upstream_version": "2.1.3",
            "description": "A full-featured test application",
            "long_description": "This is a longer description.\n\nWith multiple paragraphs.",
            "homepage": "https://example.com",
            "maintainer": "Developer <dev@example.com>",
            "license": "Apache-2.0",
            "tags": ["role::container-app", "field::marine"],
            "debian_section": "web",
            "architecture": "all",
            "depends": ["docker-ce", "python3"],
            "recommends": ["nginx"],
            "suggests": ["postgresql"],
            "web_ui": {"enabled": True, "path": "/admin", "port": 8080},
            "default_config": {"HTTP_PORT": "8080", "DEBUG": "false"},
        }

        icon_path = Path("/tmp/icon.svg")
        screenshot_paths = [Path("/tmp/screen1.png"), Path("/tmp/screen2.png")]

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            icon_path=icon_path,
            screenshot_paths=screenshot_paths,
        )

        context = build_context(app_def)

        # Verify optional fields
        assert context["package"]["homepage"] == "https://example.com"
        assert context["package"]["upstream_version"] == "2.1.3"
        assert "longer description" in context["package"]["long_description"]
        assert context["package"]["depends"] == "docker-ce, python3"
        assert context["package"]["recommends"] == "nginx"
        assert context["package"]["suggests"] == "postgresql"
        assert context["package"]["tags"] == "role::container-app, field::marine"

        # Verify icon/screenshot flags
        assert context["has_icon"] is True
        assert context["icon_extension"] == "svg"
        assert context["has_screenshots"] is True
        assert context["screenshot_count"] == 2

        # Verify web_ui passed through
        assert context["web_ui"]["enabled"] is True
        assert context["web_ui"]["port"] == 8080

        # Verify default_config passed through
        assert context["default_config"]["HTTP_PORT"] == "8080"

    def test_png_icon_extension(self):
        """Test icon extension detection for PNG files."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        icon_path = Path("/tmp/icon.png")
        app_def = AppDefinition(metadata=metadata, compose={}, config={}, icon_path=icon_path)

        context = build_context(app_def)

        assert context["has_icon"] is True
        assert context["icon_extension"] == "png"


class TestFormatLongDescription:
    """Tests for format_long_description function."""

    def test_empty_description(self):
        """Test formatting empty description."""
        result = format_long_description("")
        assert result == ""

    def test_single_line(self):
        """Test formatting single line description."""
        result = format_long_description("This is a single line.")
        assert result == " This is a single line."

    def test_multiple_lines(self):
        """Test formatting multi-line description."""
        text = "First line.\nSecond line.\nThird line."
        result = format_long_description(text)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == " First line."
        assert lines[1] == " Second line."
        assert lines[2] == " Third line."

    def test_empty_lines_become_dot(self):
        """Test that empty lines become single space-period."""
        text = "Paragraph one.\n\nParagraph two."
        result = format_long_description(text)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == " Paragraph one."
        assert lines[1] == " ."
        assert lines[2] == " Paragraph two."

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "  Line with spaces  \n  Another line  "
        result = format_long_description(text)

        lines = result.split("\n")
        assert lines[0] == " Line with spaces"
        assert lines[1] == " Another line"


class TestFormatDependencies:
    """Tests for format_dependencies function."""

    def test_none_dependencies(self):
        """Test formatting None dependencies."""
        result = format_dependencies(None)
        assert result == ""

    def test_empty_list(self):
        """Test formatting empty list."""
        result = format_dependencies([])
        assert result == ""

    def test_single_dependency(self):
        """Test formatting single dependency."""
        result = format_dependencies(["docker-ce"])
        assert result == "docker-ce"

    def test_multiple_dependencies(self):
        """Test formatting multiple dependencies."""
        result = format_dependencies(["docker-ce", "python3", "nginx"])
        assert result == "docker-ce, python3, nginx"
