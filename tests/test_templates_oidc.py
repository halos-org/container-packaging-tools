"""Tests for OIDC-related template rendering."""

from pathlib import Path

from generate_container_packages.loader import AppDefinition
from generate_container_packages.renderer import render_all_templates


class TestOIDCPostinst:
    """Tests for postinst OIDC secret generation."""

    def test_oidc_app_generates_secret(self, tmp_path):
        """OIDC app postinst should generate OIDC client secret."""
        metadata = {
            "name": "OIDC App",
            "app_id": "oidc-app",
            "package_name": "oidc-app-container",
            "version": "1.0.0",
            "description": "App with OIDC auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "oidc",
                "auth": "oidc",
                "oidc": {
                    "client_name": "OIDC App",
                    "redirect_path": "/callback",
                },
            },
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

        postinst = output_dir / "debian" / "postinst"
        content = postinst.read_text()

        # Verify OIDC secret generation
        assert "OIDC_SECRET_FILE=" in content
        assert "openssl rand -hex 32" in content
        assert "chmod 600" in content

    def test_non_oidc_app_no_secret(self, tmp_path):
        """Non-OIDC app postinst should not generate OIDC secret."""
        metadata = {
            "name": "Forward Auth App",
            "app_id": "fwd-app",
            "package_name": "fwd-app-container",
            "version": "1.0.0",
            "description": "App with forward auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "fwd",
                "auth": "forward_auth",
            },
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

        postinst = output_dir / "debian" / "postinst"
        content = postinst.read_text()

        # Verify no OIDC secret generation
        assert "OIDC_SECRET_FILE=" not in content
        assert "openssl rand" not in content


class TestOIDCPostrm:
    """Tests for postrm OIDC cleanup."""

    def test_oidc_app_removes_snippet(self, tmp_path):
        """OIDC app postrm should remove OIDC client snippet."""
        metadata = {
            "name": "OIDC App",
            "app_id": "oidc-app",
            "package_name": "oidc-app-container",
            "version": "1.0.0",
            "description": "App with OIDC auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "oidc",
                "auth": "oidc",
                "oidc": {
                    "client_name": "OIDC App",
                    "redirect_path": "/callback",
                },
            },
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

        postrm = output_dir / "debian" / "postrm"
        content = postrm.read_text()

        # Verify OIDC snippet removal
        assert "/etc/halos/oidc-clients.d/oidc-app.yml" in content
        assert "rm -f" in content

    def test_middleware_app_removes_middleware(self, tmp_path):
        """Forward auth app with custom headers postrm should remove middleware."""
        metadata = {
            "name": "Custom Headers App",
            "app_id": "grafana",
            "package_name": "grafana-container",
            "version": "1.0.0",
            "description": "App with custom forward auth headers",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
                "forward_auth": {
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                    },
                },
            },
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

        postrm = output_dir / "debian" / "postrm"
        content = postrm.read_text()

        # Verify middleware removal
        assert (
            "/var/lib/container-apps/traefik-container/dynamic/grafana.yml" in content
        )

    def test_non_oidc_app_no_cleanup(self, tmp_path):
        """Non-OIDC app postrm should not have OIDC cleanup."""
        metadata = {
            "name": "Simple App",
            "app_id": "simple",
            "package_name": "simple-container",
            "version": "1.0.0",
            "description": "Simple app without SSO",
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

        postrm = output_dir / "debian" / "postrm"
        content = postrm.read_text()

        # Verify no OIDC/middleware cleanup
        assert "/etc/halos/oidc-clients.d/" not in content
        assert "traefik-container/dynamic/" not in content


class TestOIDCSystemdService:
    """Tests for systemd service OIDC dependencies."""

    def test_oidc_app_depends_on_authelia(self, tmp_path):
        """OIDC app should depend on Authelia service."""
        metadata = {
            "name": "OIDC App",
            "app_id": "oidc-app",
            "package_name": "oidc-app-container",
            "version": "1.0.0",
            "description": "App with OIDC auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "oidc",
                "auth": "oidc",
                "oidc": {
                    "client_name": "OIDC App",
                    "redirect_path": "/callback",
                },
            },
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

        service = output_dir / "debian" / "oidc-app-container.service"
        content = service.read_text()

        # Verify Authelia dependency
        assert "After=halos-authelia-container.service" in content
        assert "Wants=halos-authelia-container.service" in content

    def test_non_oidc_app_no_authelia_dependency(self, tmp_path):
        """Non-OIDC app should not depend on Authelia service."""
        metadata = {
            "name": "Forward Auth App",
            "app_id": "fwd-app",
            "package_name": "fwd-app-container",
            "version": "1.0.0",
            "description": "App with forward auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "fwd",
                "auth": "forward_auth",
            },
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

        service = output_dir / "debian" / "fwd-app-container.service"
        content = service.read_text()

        # Verify no Authelia dependency
        assert "halos-authelia-container" not in content

    def test_no_traefik_config_no_authelia_dependency(self, tmp_path):
        """App without traefik config should not depend on Authelia."""
        metadata = {
            "name": "Simple App",
            "app_id": "simple",
            "package_name": "simple-container",
            "version": "1.0.0",
            "description": "Simple app without traefik",
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

        service = output_dir / "debian" / "simple-container.service"
        content = service.read_text()

        # Verify no Authelia dependency
        assert "halos-authelia-container" not in content


class TestOIDCRulesInstallation:
    """Tests for debian/rules OIDC file installation."""

    def test_oidc_app_installs_snippet(self, tmp_path):
        """OIDC app rules should install OIDC client snippet."""
        metadata = {
            "name": "OIDC App",
            "app_id": "oidc-app",
            "package_name": "oidc-app-container",
            "version": "1.0.0",
            "description": "App with OIDC auth",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "oidc",
                "auth": "oidc",
                "oidc": {
                    "client_name": "OIDC App",
                    "redirect_path": "/callback",
                },
            },
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

        rules = output_dir / "debian" / "rules"
        content = rules.read_text()

        # Verify OIDC snippet installation
        assert "oidc-client.yml" in content
        assert "/etc/halos/oidc-clients.d/oidc-app.yml" in content

    def test_middleware_app_installs_middleware(self, tmp_path):
        """Forward auth app with custom headers should install middleware."""
        metadata = {
            "name": "Custom Headers App",
            "app_id": "grafana",
            "package_name": "grafana-container",
            "version": "1.0.0",
            "description": "App with custom forward auth headers",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
                "forward_auth": {
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                    },
                },
            },
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

        rules = output_dir / "debian" / "rules"
        content = rules.read_text()

        # Verify middleware installation
        assert "traefik-middleware.yml" in content
        assert "traefik-container/dynamic/grafana.yml" in content
