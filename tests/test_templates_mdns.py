"""Tests for mDNS-related template rendering."""

from pathlib import Path

from generate_container_packages.loader import AppDefinition
from generate_container_packages.renderer import render_all_templates


class TestMdnsPostrm:
    """Tests for removal of the runtime-written avahi service file."""

    @staticmethod
    def _render(tmp_path, routing):
        metadata = {
            "name": "Mdns App",
            "app_id": "mdns-app",
            "package_name": "mdns-app-container",
            "version": "1.0.0",
            "description": "App advertising a DNS-SD service",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": routing,
        }
        app_def = AppDefinition(
            metadata=metadata,
            compose={"services": {"app": {}}},
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
        return (output_dir / "debian" / "postrm").read_text()

    def test_purge_removes_avahi_service_file(self, tmp_path):
        """An app declaring mdns services has its avahi file purged."""
        postrm = self._render(tmp_path, {"mdns": ["_signalk-wss._tcp"]})
        assert 'rm -f "/etc/avahi/services/halos-mdns-app.service"' in postrm

    def test_no_avahi_removal_without_mdns(self, tmp_path):
        """An app without mdns services gets no avahi removal line."""
        postrm = self._render(tmp_path, {})
        assert "/etc/avahi/services/" not in postrm
