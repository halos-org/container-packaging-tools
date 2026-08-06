"""Whole-output guards for a generated package.

Both suites here predate the removal of the provisioning hook and outlived it:
neither is about provisioning, and both cover behaviour that applies to every
generated package. They were rehomed from tests/test_provisioning.py.
"""

from pathlib import Path

from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates

VALID_FIXTURES = Path("tests/fixtures/valid")
SIMPLE_APP = VALID_FIXTURES / "simple-app"
PKG = "simple-test-app-container"


def render_file(fixture_dir: Path, tmp_path: Path, name: str) -> str:
    """Render an app's templates and return one rendered file's content."""
    app_def = load_input_files(fixture_dir)
    render_all_templates(app_def, tmp_path)
    return (tmp_path / "debian" / name).read_text()


class TestInstallTimeStart:
    """postinst starts the service without blocking dpkg.

    debhelper's own start calls deb-systemd-invoke, which runs `systemctl start`
    without --no-block and so waits for the whole start transaction while dpkg
    holds its lock. A slow ExecStartPre then stalls the package transaction.
    """

    def test_debhelper_start_is_suppressed(self, tmp_path):
        content = render_file(SIMPLE_APP, tmp_path, "rules")
        assert "override_dh_installsystemd:" in content
        assert "dh_installsystemd --no-start" in content

    def test_postinst_starts_without_blocking(self, tmp_path):
        content = render_file(SIMPLE_APP, tmp_path, "postinst")
        assert f"systemctl restart --no-block {PKG}.service" in content


class TestOutputGolden:
    """Full-output comparison for the simple app.

    Substring-absence assertions cannot see whitespace, and an earlier feature
    left a stray blank line in debian/rules for every app while every test
    stayed green. This is also the guard that removing a conditional block does
    not shift the surrounding output. Regenerate deliberately, never to make a
    red test pass.
    """

    GOLDEN_DIR = VALID_FIXTURES.parent / "expected"

    def _assert_matches_golden(self, tmp_path: Path, name: str) -> None:
        rendered = render_file(SIMPLE_APP, tmp_path, name)
        expected = (self.GOLDEN_DIR / f"simple-app.{name}").read_text()
        assert rendered == expected

    def test_rules_unchanged(self, tmp_path):
        self._assert_matches_golden(tmp_path, "rules")

    def test_postinst_unchanged(self, tmp_path):
        self._assert_matches_golden(tmp_path, "postinst")

    def test_prerm_unchanged(self, tmp_path):
        self._assert_matches_golden(tmp_path, "prerm")

    def test_service_unit_unchanged(self, tmp_path):
        self._assert_matches_golden(tmp_path, f"{PKG}.service")
