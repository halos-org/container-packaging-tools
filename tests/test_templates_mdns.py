"""Tests for mDNS-related template rendering."""

from pathlib import Path

from generate_container_packages.loader import AppDefinition
from generate_container_packages.renderer import render_all_templates


class TestMdnsPostrm:
    """Tests for removal of the runtime-written avahi service file."""

    @staticmethod
    def _render(tmp_path, routing, filename="postrm"):
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
        if filename == "service":
            return (output_dir / "debian" / "mdns-app-container.service").read_text()
        return (output_dir / "debian" / filename).read_text()

    MDNS = {"mdns": [{"type": "_signalk-wss._tcp"}]}

    def test_both_remove_and_purge_drop_the_record(self, tmp_path):
        """A stale record answers for a dead port, so plain remove clears it too."""
        postrm = self._render(tmp_path, self.MDNS)
        rm_line = 'rm -f "/etc/avahi/services/halos-mdns-app.service"'
        assert postrm.count(rm_line) == 2, (
            "the removal belongs in the purge branch and the remove branch; "
            "case takes the first match, so purge never falls through"
        )

    def test_no_avahi_removal_without_mdns(self, tmp_path):
        """An app without mdns services gets no avahi removal line."""
        postrm = self._render(tmp_path, {})
        assert "/etc/avahi/services/" not in postrm

    def test_unit_withdraws_the_record_on_stop(self, tmp_path):
        """The record is withdrawn when the app stops, not only when it is removed."""
        unit = self._render(tmp_path, self.MDNS, filename="service")
        assert (
            "ExecStopPost=-/usr/bin/configure-container-routing "
            "--mdns-withdraw mdns-app" in unit
        )

    def test_no_withdrawal_hook_without_mdns(self, tmp_path):
        """An app that advertises nothing gets no withdrawal hook."""
        unit = self._render(tmp_path, {}, filename="service")
        assert "--mdns-withdraw" not in unit


class TestMdnsCoreVersionFloor:
    """An app that advertises needs a core release that reads the mdns key."""

    @staticmethod
    def _depends(routing):
        from generate_container_packages.template_context import build_context

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
        return build_context(app_def)["package"]["depends"]

    def test_mdns_app_requires_the_mdns_aware_core(self):
        """An older core ignores the mdns key, so the app would advertise nothing."""
        depends = self._depends({"mdns": [{"type": "_signalk-wss._tcp"}]})
        assert "halos-core-containers (>= 0.8.0)" in depends

    def test_routed_app_keeps_the_producer_floor(self):
        """An app that advertises nothing stays on the HALOS_DOMAIN producer floor."""
        depends = self._depends({})
        assert "halos-core-containers (>= 0.5.0)" in depends
