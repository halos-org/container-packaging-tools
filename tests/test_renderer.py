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
        # Use the actual templates directory from the package
        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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
        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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

        # No custom prestart.sh -> rules must not install an app-prestart.sh hook
        rules_content = (debian_dir / "rules").read_text()
        assert "app-prestart.sh" not in rules_content

    def test_rules_installs_app_prestart_hook(self, tmp_path):
        """When the app ships a prestart.sh, rules installs it as app-prestart.sh
        beside docker-compose.yml in the package lib dir."""
        (tmp_path / "prestart.sh").write_text("#!/bin/bash\necho hook\n")

        metadata = {
            "name": "Hook App",
            "package_name": "hook-app-container",
            "version": "1.0.0",
            "description": "App with a custom prestart hook",
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
            input_dir=tmp_path,
            icon_path=None,
        )

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        rules_content = (output_dir / "debian" / "rules").read_text()
        assert "install -D -m 755 app-prestart.sh" in rules_content
        assert (
            "/var/lib/container-apps/hook-app-container/app-prestart.sh"
            in rules_content
        )

    def test_hook_install_dir_matches_prestart_source_dir(self, tmp_path):
        """The dir rules.j2 installs app-prestart.sh into must equal the dir the
        generated prestart.sh sources it from. They are built from independent
        literals (paths.lib vs prestart.py's lib_dir); if they ever drift the
        package builds green but the hook is never found at boot. Pin them here."""
        from generate_container_packages.prestart import generate_prestart_script
        from generate_container_packages.template_context import build_context

        (tmp_path / "prestart.sh").write_text("#!/bin/bash\necho hook\n")
        metadata = {
            "name": "Hook App",
            "package_name": "hook-app-container",
            "version": "1.0.0",
            "description": "App with a custom prestart hook",
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
            input_dir=tmp_path,
            icon_path=None,
            screenshot_paths=[],
        )

        # Directory the prestart sources the hook from
        script = generate_prestart_script(app_def)
        source_line = next(
            line for line in script.splitlines() if "app-prestart.sh" in line
        )
        source_dir = os.path.dirname(
            source_line.split('"')[1]
        )  # path inside [ -f "<path>" ]

        # Directory rules.j2 installs the hook into (== paths.lib)
        lib_dir = build_context(app_def)["paths"]["lib"]

        assert source_dir == lib_dir

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

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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
        # Non-routed app: no Breaks: line should appear.
        assert "Breaks:" not in content

    def test_rendered_control_file_breaks_for_routed_visible_app(self, tmp_path):
        """Routed + web_ui.enabled + web_ui.visible -> Breaks: line in control."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "app_id": "test-app",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Developer <dev@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "web",
            "architecture": "all",
            "routing": {"auth": {"mode": "none"}},
            "web_ui": {
                "enabled": True,
                "visible": True,
                "port": 8080,
                "protocol": "http",
                "path": "/",
            },
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose={"services": {"test-app": {"image": "test:latest"}}},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
        output_dir = tmp_path / "output"

        render_all_templates(app_def, output_dir, template_dir)

        control_file = output_dir / "debian" / "control"
        content = control_file.read_text()

        # The Breaks: line is present, both peers pinned, in injected order.
        assert (
            "Breaks: homarr-container-adapter (<< 0.4.6), "
            "halos-core-containers (<< 0.3.2)"
        ) in content

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

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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

        template_dir = (
            Path(__file__).parent.parent
            / "src"
            / "generate_container_packages"
            / "templates"
        )
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


class TestHalosDomainDistribution:
    """Unit 2: routed/web_ui apps inherit HALOS_DOMAIN from the producer via an
    EnvironmentFile, order against the producer service, and depend on the core
    release that ships it. Non-routed apps stay independent."""

    template_dir = (
        Path(__file__).parent.parent
        / "src"
        / "generate_container_packages"
        / "templates"
    )

    def _render(self, tmp_path, metadata, compose=None):
        app_def = AppDefinition(
            metadata=metadata,
            compose=compose or {},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
        )
        output_dir = tmp_path / "output"
        render_all_templates(app_def, output_dir, self.template_dir)
        return output_dir

    def test_web_ui_unit_inherits_domain_and_orders_on_producer(self, tmp_path):
        """A web_ui app's unit loads /run/halos/domain.env and orders against
        halos-resolve-domain.service."""
        metadata = {
            "name": "Web App",
            "package_name": "web-app-container",
            "app_id": "web-app",
            "version": "1.0.0",
            "description": "App with web UI",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "web_ui": {"enabled": True, "port": 8080, "protocol": "http"},
        }

        output_dir = self._render(tmp_path, metadata)
        content = (output_dir / "debian" / "web-app-container.service").read_text()

        assert "After=halos-resolve-domain.service" in content
        assert "Wants=halos-resolve-domain.service" in content
        assert "EnvironmentFile=-/run/halos/domain.env" in content

    def test_web_ui_domain_envfile_loaded_after_runtime_env(self, tmp_path):
        """domain.env must be the last EnvironmentFile so it wins over a stale
        HALOS_DOMAIN that an older runtime.env might still carry."""
        metadata = {
            "name": "Web App",
            "package_name": "web-app-container",
            "app_id": "web-app",
            "version": "1.0.0",
            "description": "App with web UI",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "web_ui": {"enabled": True, "port": 8080, "protocol": "http"},
        }

        output_dir = self._render(tmp_path, metadata)
        content = (output_dir / "debian" / "web-app-container.service").read_text()

        env_lines = [
            line for line in content.splitlines() if line.startswith("EnvironmentFile=")
        ]
        # domain.env must be the final EnvironmentFile so its HALOS_DOMAIN wins.
        assert env_lines[-1] == "EnvironmentFile=-/run/halos/domain.env"

    def test_web_ui_control_depends_on_producer_release(self, tmp_path):
        """A web_ui app's control depends on the core release shipping the
        producer."""
        metadata = {
            "name": "Web App",
            "package_name": "web-app-container",
            "app_id": "web-app",
            "version": "1.0.0",
            "description": "App with web UI",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "web_ui": {"enabled": True, "port": 8080, "protocol": "http"},
        }

        output_dir = self._render(tmp_path, metadata)
        content = (output_dir / "debian" / "control").read_text()

        assert "halos-core-containers (>= 0.5.0)" in content

    def test_non_routed_app_stays_independent_of_producer(self, tmp_path):
        """A non-web_ui / non-routing app gains no producer coupling: no
        ordering, no EnvironmentFile, no core dependency."""
        metadata = {
            "name": "Plain App",
            "package_name": "plain-app-container",
            "app_id": "plain-app",
            "version": "1.0.0",
            "description": "App with no web UI or routing",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        output_dir = self._render(tmp_path, metadata)
        service = (output_dir / "debian" / "plain-app-container.service").read_text()
        control = (output_dir / "debian" / "control").read_text()

        assert "halos-resolve-domain.service" not in service
        assert "/run/halos/domain.env" not in service
        assert "halos-core-containers" not in control

    def test_oidc_app_orders_on_both_authelia_and_producer(self, tmp_path):
        """An OIDC app (routing.auth.mode=oidc, the primary motivating case)
        orders against both Authelia and the domain producer, loads domain.env,
        and depends on the producer release."""
        metadata = {
            "name": "OIDC App",
            "package_name": "oidc-app-container",
            "app_id": "oidc-app",
            "version": "1.0.0",
            "description": "App with OIDC auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "routing": {"auth": {"mode": "oidc"}},
        }

        output_dir = self._render(tmp_path, metadata)
        service = (output_dir / "debian" / "oidc-app-container.service").read_text()
        control = (output_dir / "debian" / "control").read_text()

        assert "After=halos-authelia-container.service" in service
        assert "Wants=halos-authelia-container.service" in service
        assert "After=halos-resolve-domain.service" in service
        assert "Wants=halos-resolve-domain.service" in service
        assert "EnvironmentFile=-/run/halos/domain.env" in service
        assert "halos-core-containers (>= 0.5.0)" in control

    def test_routed_app_without_web_ui_gets_producer_coupling(self, tmp_path):
        """The routing-present / web_ui-absent branch of has_routing must gain
        the same producer wiring as a web_ui app (it still needs HALOS_DOMAIN)."""
        metadata = {
            "name": "Routed App",
            "package_name": "routed-app-container",
            "app_id": "routed-app",
            "version": "1.0.0",
            "description": "Routed app with no web UI",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "routing": {"auth": {"mode": "forward_auth"}},
        }

        output_dir = self._render(tmp_path, metadata)
        service = (output_dir / "debian" / "routed-app-container.service").read_text()
        control = (output_dir / "debian" / "control").read_text()

        assert "After=halos-resolve-domain.service" in service
        assert "Wants=halos-resolve-domain.service" in service
        assert "EnvironmentFile=-/run/halos/domain.env" in service
        assert "halos-core-containers (>= 0.5.0)" in control
