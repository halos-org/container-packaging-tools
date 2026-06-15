"""Tests for env file permission hardening in postinst.

The env file at /etc/container-apps/<package>/env can hold secrets
(e.g. INFLUXDB_ADMIN_TOKEN), so it must be mode 600 — both on fresh
installs and corrected on upgrades of existing installs. The sibling
env.defaults carries shipped default credentials and is rewritten from
the template on every configure, so it must be hardened the same way.
"""

from pathlib import Path

from generate_container_packages.loader import AppDefinition
from generate_container_packages.renderer import render_all_templates

TEMPLATE_DIR = (
    Path(__file__).parent.parent / "src" / "generate_container_packages" / "templates"
)


def _render_postinst(tmp_path: Path) -> str:
    metadata = {
        "name": "Plain App",
        "app_id": "plain-app",
        "package_name": "plain-app-container",
        "version": "1.0.0",
        "description": "App without OIDC",
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

    output_dir = tmp_path / "output"
    render_all_templates(app_def, output_dir, TEMPLATE_DIR)

    return (output_dir / "debian" / "postinst").read_text()


class TestEnvFilePermissions:
    """postinst must restrict the env file to mode 600."""

    def test_env_file_chmod_600(self, tmp_path):
        """The env file is chmod 600 so secrets are not world-readable."""
        content = _render_postinst(tmp_path)

        assert 'chmod 600 "/etc/container-apps/plain-app-container/env"' in content

    def test_env_file_hardened_on_upgrade(self, tmp_path):
        """The chmod runs unconditionally (outside the first-install guard)
        so existing world-readable installs are corrected on upgrade."""
        content = _render_postinst(tmp_path)

        lines = content.splitlines()
        chmod_idx = next(
            i
            for i, line in enumerate(lines)
            if 'chmod 600 "/etc/container-apps/plain-app-container/env"' in line
        )
        # Locate the `if [ ! -f ... env ]` first-install guard and its `fi`.
        guard_idx = next(
            i
            for i, line in enumerate(lines)
            if '/etc/container-apps/plain-app-container/env" ]' in line
            and line.lstrip().startswith("if [ ! -f")
        )
        fi_idx = next(
            i for i in range(guard_idx + 1, len(lines)) if lines[i].strip() == "fi"
        )

        assert chmod_idx > fi_idx, (
            "chmod 600 must run outside the first-install guard so upgrades "
            "of existing installs are also hardened"
        )

    def test_env_defaults_chmod_600(self, tmp_path):
        """env.defaults holds shipped default credentials and is rewritten on
        every configure, so it must be hardened to 600 each time too."""
        content = _render_postinst(tmp_path)

        assert (
            "/etc/container-apps/plain-app-container/env.defaults" in content
        ), "postinst must reference env.defaults"

        chmod_line = next(
            line
            for line in content.splitlines()
            if line.lstrip().startswith("chmod 600")
            and "env.defaults" in line
        )
        assert (
            '"/etc/container-apps/plain-app-container/env.defaults"' in chmod_line
        ), "env.defaults must be chmod 600 alongside env"
