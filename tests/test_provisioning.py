"""Tests for the provisioning hook and its generated one-shot unit.

An app that ships `provision.sh` gets a `<package>-provision.service` that runs
long, one-time setup work outside the app unit's start path. See the hook
contract in AGENTS.md.
"""

from pathlib import Path

from generate_container_packages.builder import copy_source_files
from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates
from generate_container_packages.template_context import build_context

VALID_FIXTURES = Path("tests/fixtures/valid")
PROVISION_APP = VALID_FIXTURES / "provision-app"
SIMPLE_APP = VALID_FIXTURES / "simple-app"

PROVISION_UNIT = "provision-test-app-container-provision.service"
LIB_DIR = "/var/lib/container-apps/provision-test-app-container"


def render_unit(fixture_dir: Path, tmp_path: Path, unit_name: str) -> str:
    """Render an app's templates and return one rendered unit's content."""
    app_def = load_input_files(fixture_dir)
    render_all_templates(app_def, tmp_path)
    return (tmp_path / "debian" / unit_name).read_text()


def directives(content: str) -> list[str]:
    """Return a unit file's directive lines, ignoring comments and headers.

    Asserting on these rather than on the raw text keeps the tests indifferent
    to the explanatory comments the templates carry.
    """
    lines = (line.strip() for line in content.splitlines())
    return [
        line
        for line in lines
        if line and not line.startswith("#") and not line.startswith("[")
    ]


def has_directive(content: str, key: str) -> bool:
    """Whether the unit sets the given directive at all."""
    return any(line.startswith(f"{key}=") for line in directives(content))


class TestProvisionContext:
    """The hook is triggered by file presence, mirroring app-prestart.sh."""

    def test_has_provision_true_when_hook_present(self):
        context = build_context(load_input_files(PROVISION_APP))
        assert context["has_provision"] is True

    def test_has_provision_false_when_hook_absent(self):
        context = build_context(load_input_files(SIMPLE_APP))
        assert context["has_provision"] is False


class TestProvisionHookPackaging:
    """The hook keeps its source name and is installed executable."""

    def test_hook_copied_to_build_dir(self, tmp_path):
        app_def = load_input_files(PROVISION_APP)
        copy_source_files(app_def, tmp_path)

        hook = tmp_path / "provision.sh"
        assert hook.exists()
        assert hook.read_text() == (PROVISION_APP / "provision.sh").read_text()

    def test_hook_is_executable(self, tmp_path):
        app_def = load_input_files(PROVISION_APP)
        copy_source_files(app_def, tmp_path)

        assert (tmp_path / "provision.sh").stat().st_mode & 0o111

    def test_no_hook_copied_when_absent(self, tmp_path):
        app_def = load_input_files(SIMPLE_APP)
        copy_source_files(app_def, tmp_path)

        assert not (tmp_path / "provision.sh").exists()


class TestProvisionUnitRendering:
    """The generated unit exists only when the app ships a hook."""

    def test_unit_rendered_when_hook_present(self, tmp_path):
        app_def = load_input_files(PROVISION_APP)
        render_all_templates(app_def, tmp_path)

        assert (tmp_path / "debian" / PROVISION_UNIT).exists()

    def test_no_unit_rendered_when_hook_absent(self, tmp_path):
        app_def = load_input_files(SIMPLE_APP)
        render_all_templates(app_def, tmp_path)

        units = list((tmp_path / "debian").glob("*-provision.service"))
        assert units == []


class TestProvisionUnitSemantics:
    """Every property in the unit carries a failure mode it prevents."""

    def test_is_oneshot(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "Type=oneshot" in content

    def test_executes_the_hook_by_its_source_name(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert f"ExecStart={LIB_DIR}/provision.sh" in content

    def test_no_remain_after_exit(self, tmp_path):
        """Returning to inactive is what makes the hook re-run on each app start."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not has_directive(content, "RemainAfterExit")

    def test_no_restart(self, tmp_path):
        """The retry is the next app start, not a restart loop."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not has_directive(content, "Restart")

    def test_start_rate_limiting_disabled(self, tmp_path):
        """Inheriting systemd's default would let a crash-looping app exhaust
        the provision unit's start limit, after which starts are refused
        silently (the app only Wants= it)."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "StartLimitIntervalSec=0" in content

    def test_generous_start_timeout_backstop(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "TimeoutStartSec=1800" in content

    def test_reaps_its_container_even_when_killed(self, tmp_path):
        """The backstop SIGKILLs the cgroup, so the hook's own cleanup cannot
        run; ExecStopPost survives that path and removes the installer."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert (
            "ExecStopPost=-docker rm -f provision-test-app-container-provision"
            in content
        )

    def test_exports_the_container_name_to_the_hook(self, tmp_path):
        """The hook must name its container this, or the cleanup above misses it."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert (
            "Environment=HALOS_PROVISION_CONTAINER="
            "provision-test-app-container-provision" in content
        )

    def test_ordered_after_docker(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "After=docker.service" in content
        assert "Requires=docker.service" in content

    def test_ordered_after_network_online(self, tmp_path):
        """docker.service being active says nothing about DNS or a route: without
        this a device with working internet can look offline."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "Wants=network-online.target" in content
        assert "After=network-online.target" in content

    def test_loads_app_env_files(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert (
            "EnvironmentFile=-/etc/container-apps/provision-test-app-container/env.defaults"
            in content
        )
        assert (
            "EnvironmentFile=-/etc/container-apps/provision-test-app-container/env"
            in content
        )

    def test_does_not_load_runtime_env(self, tmp_path):
        """Provisioning runs before the app's prestart writes runtime.env."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert not any("runtime.env" in line for line in directives(content))

    def test_working_directory_is_the_lib_dir(self, tmp_path):
        """So the hook can read docker-compose.yml and assets/."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert f"WorkingDirectory={LIB_DIR}" in content

    def test_has_no_install_section(self, tmp_path):
        """Pulled in by the app unit's Wants=; there is nothing to enable."""
        content = render_unit(PROVISION_APP, tmp_path, PROVISION_UNIT)
        assert "[Install]" not in content


class TestAppUnitOrdering:
    """The app declares the ordering; the provision unit stays standalone."""

    def test_app_unit_wants_and_orders_after_provision(self, tmp_path):
        content = render_unit(
            PROVISION_APP, tmp_path, "provision-test-app-container.service"
        )
        assert f"Wants={PROVISION_UNIT}" in content
        assert f"After={PROVISION_UNIT}" in content

    def test_wants_not_requires(self, tmp_path):
        """A failed provision must never prevent the app from starting."""
        content = render_unit(
            PROVISION_APP, tmp_path, "provision-test-app-container.service"
        )
        assert f"Requires={PROVISION_UNIT}" not in content

    def test_app_unit_unchanged_without_hook(self, tmp_path):
        content = render_unit(SIMPLE_APP, tmp_path, "simple-test-app-container.service")
        assert "-provision.service" not in content


class TestProvisionInstallRules:
    """debian/rules must install both the hook and the unit."""

    def test_rules_install_hook_and_unit(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, "rules")
        assert "install -D -m 755 provision.sh" in content
        assert f"debian/provision-test-app-container/{LIB_DIR}/provision.sh" in content
        assert f"debian/{PROVISION_UNIT}" in content
        assert f"/etc/systemd/system/{PROVISION_UNIT}" in content

    def test_rules_omit_provisioning_without_hook(self, tmp_path):
        content = render_unit(SIMPLE_APP, tmp_path, "rules")
        assert "provision.sh" not in content
        assert "-provision.service" not in content


class TestProvisionTeardown:
    """prerm stops the provision unit before the app."""

    def test_prerm_stops_provision_unit(self, tmp_path):
        content = render_unit(PROVISION_APP, tmp_path, "prerm")
        assert f"systemctl stop {PROVISION_UNIT}" in content

    def test_prerm_unchanged_without_hook(self, tmp_path):
        content = render_unit(SIMPLE_APP, tmp_path, "prerm")
        assert "-provision.service" not in content
