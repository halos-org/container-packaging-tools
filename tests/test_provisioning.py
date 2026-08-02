"""Tests for the provisioning hook and its generated one-shot unit.

An app that ships `provision.sh` gets a `<package>-provision.service` that runs
long setup work outside the app unit's start path. The hook contract is
documented in AGENTS.md by #224; until then the unit template carries it.

Unit assertions parse directives into (section, key, value) rather than matching
raw text. Substring matching passed even with `ExecStart=` commented out, because
the templates explain themselves in comments that contain the same strings.
"""

from pathlib import Path

from generate_container_packages.builder import copy_source_files
from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates
from generate_container_packages.template_context import build_context

VALID_FIXTURES = Path("tests/fixtures/valid")
PROVISION_APP = VALID_FIXTURES / "provision-app"
SIMPLE_APP = VALID_FIXTURES / "simple-app"

PKG = "provision-test-app-container"
PROVISION_UNIT = f"{PKG}-provision.service"
LIB_DIR = f"/var/lib/container-apps/{PKG}"
ETC_DIR = f"/etc/container-apps/{PKG}"


def render_file(fixture_dir: Path, tmp_path: Path, name: str) -> str:
    """Render an app's templates and return one rendered file's content."""
    app_def = load_input_files(fixture_dir)
    render_all_templates(app_def, tmp_path)
    return (tmp_path / "debian" / name).read_text()


def parse_unit(content: str) -> list[tuple[str, str, str]]:
    """Parse a unit file into (section, key, value) triples.

    Comments are dropped, so a directive that is commented out does not count as
    present -- which raw substring matching could not distinguish.
    """
    triples: list[tuple[str, str, str]] = []
    section = ""
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            triples.append((section, key.strip(), value.strip()))
    return triples


def values(content: str, section: str, key: str) -> list[str]:
    """All values for a directive in a section (systemd allows repeats)."""
    return [v for s, k, v in parse_unit(content) if s == section and k == key]


def has_key(content: str, key: str) -> bool:
    """Whether a directive is set anywhere in the unit."""
    return any(k == key for _, k, _ in parse_unit(content))


class TestProvisionContext:
    """The hook is triggered by file presence, mirroring app-prestart.sh."""

    def test_has_provision_true_when_hook_present(self):
        assert build_context(load_input_files(PROVISION_APP))["has_provision"] is True

    def test_has_provision_false_when_hook_absent(self):
        assert build_context(load_input_files(SIMPLE_APP))["has_provision"] is False


class TestProvisionHookPackaging:
    """The hook keeps its source name and is installed executable."""

    def test_hook_copied_to_build_dir(self, tmp_path):
        copy_source_files(load_input_files(PROVISION_APP), tmp_path)

        hook = tmp_path / "provision.sh"
        assert hook.exists()
        assert hook.read_text() == (PROVISION_APP / "provision.sh").read_text()

    def test_mode_is_set_not_inherited(self, tmp_path):
        """The fixture is committed 755, so copying alone reproduces the bit.
        Copy a non-executable hook to prove the builder sets the mode itself."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        for name in ("metadata.yaml", "docker-compose.yml", "config.yml"):
            (app_dir / name).write_text((PROVISION_APP / name).read_text())
        hook = app_dir / "provision.sh"
        hook.write_text((PROVISION_APP / "provision.sh").read_text())
        hook.chmod(0o644)

        out = tmp_path / "out"
        out.mkdir()
        copy_source_files(load_input_files(app_dir), out)

        assert (out / "provision.sh").stat().st_mode & 0o777 == 0o755

    def test_no_hook_copied_when_absent(self, tmp_path):
        copy_source_files(load_input_files(SIMPLE_APP), tmp_path)

        assert not (tmp_path / "provision.sh").exists()


class TestProvisionUnitRendering:
    """The generated unit exists only when the app ships a hook."""

    def test_unit_rendered_when_hook_present(self, tmp_path):
        render_all_templates(load_input_files(PROVISION_APP), tmp_path)

        assert (tmp_path / "debian" / PROVISION_UNIT).exists()

    def test_no_unit_rendered_when_hook_absent(self, tmp_path):
        render_all_templates(load_input_files(SIMPLE_APP), tmp_path)

        assert list((tmp_path / "debian").glob("*-provision.service")) == []


class TestProvisionUnitSemantics:
    """Every directive here carries a failure mode it prevents."""

    def test_is_oneshot(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "Type") == ["oneshot"]

    def test_executes_the_hook_by_its_source_name(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "ExecStart") == [f"{LIB_DIR}/provision.sh"]

    def test_no_remain_after_exit(self, tmp_path):
        """Returning to inactive is what makes the hook re-run on each app start."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not has_key(content, "RemainAfterExit")

    def test_no_restart(self, tmp_path):
        """The retry is the next app start, not a restart loop."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not has_key(content, "Restart")

    def test_start_rate_limiting_disabled(self, tmp_path):
        """Inheriting systemd's default would let a crash-looping app exhaust this
        unit's start limit, after which starts are refused silently."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Unit", "StartLimitIntervalSec") == ["0"]

    def test_generous_start_timeout_backstop(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "TimeoutStartSec") == ["1800"]

    def test_stopping_the_app_stops_provisioning(self, tmp_path):
        """Without PartOf= the hook keeps writing to the app's data directory
        after the operator sees the app as stopped."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Unit", "PartOf") == [f"{PKG}.service"]

    def test_reaps_its_container_even_when_killed(self, tmp_path):
        """A start timeout kills the cgroup and takes the hook's own cleanup with
        it; ExecStopPost survives that path."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "ExecStopPost") == [
            "-docker rm -f ${HALOS_PROVISION_CONTAINER}"
        ]

    def test_reaper_reads_the_same_name_it_exports(self, tmp_path):
        """EnvironmentFile= is applied after Environment=, so an app env that sets
        this variable would otherwise redirect the hook while the reaper still
        removed the framework's name."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        exported = values(content, "Service", "Environment")
        assert exported == [f"HALOS_PROVISION_CONTAINER={PKG}-provision"]
        assert (
            "${HALOS_PROVISION_CONTAINER}"
            in values(content, "Service", "ExecStopPost")[0]
        )

    def test_ordered_after_docker(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "docker.service" in values(content, "Unit", "After")
        assert values(content, "Unit", "Requires") == ["docker.service"]

    def test_ordered_after_network_online(self, tmp_path):
        """docker.service being active says nothing about DNS or a route."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "network-online.target" in values(content, "Unit", "After")
        assert "network-online.target" in values(content, "Unit", "Wants")

    def test_loads_app_env_files_in_precedence_order(self, tmp_path):
        """env must load after env.defaults or packaged defaults would win over
        user config for the whole provisioning run."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "EnvironmentFile") == [
            f"-{ETC_DIR}/env.defaults",
            f"-{ETC_DIR}/env",
        ]

    def test_does_not_load_runtime_env(self, tmp_path):
        """Provisioning runs before the app's prestart writes runtime.env."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not any("runtime.env" in v for _, _, v in parse_unit(content))

    def test_working_directory_is_the_lib_dir(self, tmp_path):
        """So the hook can read docker-compose.yml and assets/."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert values(content, "Service", "WorkingDirectory") == [LIB_DIR]

    def test_has_no_install_section(self, tmp_path):
        """Pulled in by the app unit's Wants=; there is nothing to enable."""
        content = render_file(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not any(section == "Install" for section, _, _ in parse_unit(content))


class TestAppUnitOrdering:
    """The app declares the ordering; the provision unit stays standalone."""

    def test_app_unit_wants_and_orders_after_provision(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, f"{PKG}.service")
        assert PROVISION_UNIT in values(content, "Unit", "Wants")
        assert PROVISION_UNIT in values(content, "Unit", "After")

    def test_wants_not_requires(self, tmp_path):
        """A failed provision must never prevent the app from starting."""
        content = render_file(PROVISION_APP, tmp_path, f"{PKG}.service")
        assert PROVISION_UNIT not in values(content, "Unit", "Requires")

    def test_app_unit_unchanged_without_hook(self, tmp_path):
        content = render_file(SIMPLE_APP, tmp_path, "simple-test-app-container.service")
        assert not any("-provision.service" in v for _, _, v in parse_unit(content))


class TestInstallTimeStart:
    """postinst starts the service without blocking dpkg.

    Applies to every generated package, not only provisioned ones: debhelper's
    own start waits for the whole start transaction while dpkg holds its lock.
    """

    def test_debhelper_start_is_suppressed(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, "rules")
        assert "override_dh_installsystemd:" in content
        assert "dh_installsystemd --no-start" in content

    def test_postinst_starts_without_blocking(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, "postinst")
        assert f"systemctl restart --no-block {PKG}.service" in content

    def test_applies_to_apps_without_a_hook_too(self, tmp_path):
        rules = render_file(SIMPLE_APP, tmp_path, "rules")
        postinst = render_file(SIMPLE_APP, tmp_path, "postinst")
        assert "dh_installsystemd --no-start" in rules
        assert (
            "systemctl restart --no-block simple-test-app-container.service" in postinst
        )


class TestProvisionInstallRules:
    """debian/rules must install both the hook and the unit."""

    def test_rules_install_hook_and_unit(self, tmp_path):
        content = render_file(PROVISION_APP, tmp_path, "rules")
        assert "install -D -m 755 provision.sh" in content
        assert f"debian/{PKG}/{LIB_DIR}/provision.sh" in content
        assert f"debian/{PKG}-provision.service" in content
        assert f"/etc/systemd/system/{PROVISION_UNIT}" in content

    def test_rules_omit_provisioning_without_hook(self, tmp_path):
        content = render_file(SIMPLE_APP, tmp_path, "rules")
        assert "provision.sh" not in content
        assert "-provision.service" not in content

    def test_hook_and_assets_ship_together(self, tmp_path):
        """The hook reads its payload from assets/ at runtime, so both must be
        installed by the same rules file."""
        content = render_file(PROVISION_APP, tmp_path, "rules")
        assert f"debian/{PKG}/{LIB_DIR}/assets/seed.list" in content
        assert f"debian/{PKG}/{LIB_DIR}/provision.sh" in content


class TestHooklessOutputGolden:
    """Full-output comparison for an app that ships no hook.

    Substring-absence assertions cannot see whitespace, and the first version of
    this feature left a stray blank line in debian/rules for every hookless app
    while every test stayed green. Regenerate the goldens deliberately when
    output is meant to change:

        uv run python -c "..."   # see the block in this PR's description
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
        self._assert_matches_golden(tmp_path, "simple-test-app-container.service")


class TestProvisionTeardown:
    """prerm stops the provision unit before the app."""

    def test_prerm_stops_provision_unit_first(self, tmp_path):
        """Stopping the app first would let an in-flight run keep writing."""
        content = render_file(PROVISION_APP, tmp_path, "prerm")
        assert content.index(f"systemctl stop {PROVISION_UNIT}") < content.index(
            f"systemctl stop {PKG}.service"
        )

    def test_prerm_unchanged_without_hook(self, tmp_path):
        content = render_file(SIMPLE_APP, tmp_path, "prerm")
        assert "-provision.service" not in content
