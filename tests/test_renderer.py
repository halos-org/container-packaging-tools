"""Unit tests for template renderer."""

import os
from pathlib import Path

import pytest

from generate_container_packages.loader import AppDefinition
from generate_container_packages.renderer import (
    render_all_templates,
    setup_jinja_environment,
    write_rendered_file,
)


class TestSetupJinjaEnvironment:
    """Tests for setup_jinja_environment function."""

    def test_valid_template_directory(self):
        """Test setting up environment with valid template directory."""
        # Use the actual templates directory from the project
        template_dir = Path(__file__).parent.parent / "templates"
        env = setup_jinja_environment(template_dir)

        assert env is not None
        assert env.loader is not None

    def test_invalid_template_directory(self):
        """Test error when template directory doesn't exist."""
        invalid_dir = Path("/nonexistent/templates")

        with pytest.raises(FileNotFoundError):
            setup_jinja_environment(invalid_dir)


class TestWriteRenderedFile:
    """Tests for write_rendered_file function."""

    def test_write_to_new_file(self, tmp_path):
        """Test writing rendered content to new file."""
        output_file = tmp_path / "test.txt"
        content = "Hello, World!"

        write_rendered_file(content, output_file)

        assert output_file.exists()
        assert output_file.read_text() == content

    def test_write_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created if needed."""
        output_file = tmp_path / "subdir" / "nested" / "test.txt"
        content = "Nested file content"

        write_rendered_file(content, output_file)

        assert output_file.exists()
        assert output_file.read_text() == content

    def test_overwrite_existing_file(self, tmp_path):
        """Test that existing file is overwritten."""
        output_file = tmp_path / "existing.txt"
        output_file.write_text("Old content")

        new_content = "New content"
        write_rendered_file(new_content, output_file)

        assert output_file.read_text() == new_content


class TestRenderAllTemplates:
    """Tests for render_all_templates function."""

    def test_render_minimal_app(self, tmp_path):
        """Test rendering templates for minimal app definition."""
        metadata = {
            "name": "Simple App",
            "package_name": "simple-app-container",
            "version": "1.0.0",
            "description": "A simple test app",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        # Use actual template directory
        template_dir = Path(__file__).parent.parent / "templates"
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        # Verify debian directory was created
        debian_dir = output_dir / "debian"
        assert debian_dir.exists()

        # Verify critical files were rendered
        assert (debian_dir / "control").exists()
        assert (debian_dir / "rules").exists()
        assert (debian_dir / "changelog").exists()
        assert (debian_dir / "copyright").exists()
        assert (debian_dir / "compat").exists()
        assert (debian_dir / "postinst").exists()
        assert (debian_dir / "prerm").exists()
        assert (debian_dir / "postrm").exists()
        assert (debian_dir / "simple-app-container.service").exists()
        assert (debian_dir / "simple-app-container.metainfo.xml").exists()

    def test_rendered_control_file_content(self, tmp_path):
        """Test that control file has correct content."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Developer <dev@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "web",
            "architecture": "all",
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        template_dir = Path(__file__).parent.parent / "templates"
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        control_file = output_dir / "debian" / "control"
        content = control_file.read_text()

        # Verify key content is present
        assert "Package: test-app-container" in content
        assert "Section: web" in content
        assert "Maintainer: Developer <dev@example.com>" in content
        assert "Description: A test application" in content
        assert "role::container-app" in content
        assert "Standards-Version: 4.5.0" in content

    def test_executable_permissions_set(self, tmp_path):
        """Test that debian/rules and scripts have executable permissions."""
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

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        template_dir = Path(__file__).parent.parent / "templates"
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        debian_dir = output_dir / "debian"

        # Check executable files
        executable_files = ["rules", "postinst", "prerm", "postrm"]

        for filename in executable_files:
            filepath = debian_dir / filename
            assert filepath.exists()
            # Check if file is executable (owner, group, or others)
            mode = os.stat(filepath).st_mode
            assert mode & 0o111  # At least one execute bit is set

    def test_render_with_icon(self, tmp_path):
        """Test rendering with icon file."""
        metadata = {
            "name": "Icon App",
            "package_name": "icon-app-container",
            "version": "1.0.0",
            "description": "App with icon",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        icon_path = Path("/tmp/test-icon.svg")
        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=icon_path,
        )

        template_dir = Path(__file__).parent.parent / "templates"
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        # Check that rules file references icon
        rules_file = output_dir / "debian" / "rules"
        content = rules_file.read_text()
        assert "icon.svg" in content or "Install icon" in content

    def test_render_with_web_ui(self, tmp_path):
        """Test rendering with web UI configuration."""
        metadata = {
            "name": "Web App",
            "package_name": "web-app-container",
            "version": "1.0.0",
            "description": "App with web UI",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "web_ui": {"enabled": True, "path": "/admin", "port": 8080},
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        template_dir = Path(__file__).parent.parent / "templates"
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        # Check that metainfo.xml includes web UI URL
        metainfo_file = output_dir / "debian" / "web-app-container.metainfo.xml"
        content = metainfo_file.read_text()
        assert "8080" in content or "webapp" in content

    def test_systemd_service_does_not_create_volume_directories(self, tmp_path):
        """Test that systemd service file does not handle volume directories.

        Volume directory creation and ownership is handled by postinst only.
        The systemd service should not contain mkdir/chown for volumes -
        if directories are missing, the service should fail fast rather than
        silently recreating them.
        """
        metadata = {
            "name": "Volume App",
            "package_name": "volume-app-container",
            "version": "1.0.0",
            "description": "App with volumes",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "default_config": {"PUID": "1000", "PGID": "1000"},
        }

        compose = {
            "services": {
                "app": {
                    "image": "test:latest",
                    "user": "${PUID}:${PGID}",
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                        "${CONTAINER_DATA_ROOT}/data:/app/data",
                    ],
                }
            }
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose=compose,
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        # Use the source templates directory
        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        # Read the generated systemd service file
        service_file = output_dir / "debian" / "volume-app-container.service"
        content = service_file.read_text()

        # The service file should NOT contain any volume directory handling
        assert "VolumeInfo(" not in content, "VolumeInfo repr leaked into template"
        assert "CONTAINER_DATA_ROOT" not in content, (
            "systemd service should not reference CONTAINER_DATA_ROOT - "
            "volume directory creation belongs in postinst only"
        )
        assert "/bin/mkdir" not in content, (
            "systemd service should not create directories - "
            "this is handled by postinst"
        )
        assert "/bin/chown" not in content, (
            "systemd service should not set ownership - this is handled by postinst"
        )
