"""Behaviour tests for the generated compose wrapper.

The wrapper runs every compose invocation of the unit, so these tests execute
it against a stub `docker` on PATH and assert on what the stub received,
rather than on the script's text.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from generate_container_packages.compose_wrapper import generate_compose_wrapper
from generate_container_packages.loader import AppDefinition
from generate_container_packages.template_context import build_context

PKG = "demo-app-container"
APP_ID = "demo-app"
BASE = ["compose", "-p", PKG, "-f", "docker-compose.yml"]

DOCKER_STUB = """#!/bin/sh
pwd > "$STUB_OUT/cwd"
: > "$STUB_OUT/argv"
for a in "$@"; do printf '%s\\0' "$a" >> "$STUB_OUT/argv"; done
env > "$STUB_OUT/env"
exit "${STUB_EXIT:-0}"
"""


def _metadata(*, routed: bool) -> dict:
    metadata = {
        "name": "Demo App",
        "package_name": PKG,
        "app_id": APP_ID,
        "version": "1.0.0",
        "description": "Demo app",
        "maintainer": "Test <test@example.com>",
        "license": "MIT",
        "tags": ["role::container-app"],
        "debian_section": "net",
        "architecture": "all",
    }
    if routed:
        metadata["web_ui"] = {"enabled": True, "port": 8080, "protocol": "http"}
    return metadata


def _render(metadata: dict) -> str:
    app_def = AppDefinition(
        metadata=metadata,
        compose={},
        config={},
        input_dir=Path("/test/dir"),
        icon_path=None,
    )
    return generate_compose_wrapper(build_context(app_def))


@dataclass
class Result:
    argv: list[str]
    cwd: str
    env: dict[str, str]
    stderr: str
    returncode: int


def _shells() -> list[str]:
    # Debian runs #!/bin/sh as dash; also run under the host sh.
    return [s for s in ("sh", "dash") if shutil.which(s)]


class Sandbox:
    """The wrapper installed in a tmp app dir, its /etc and /run under tmp."""

    def __init__(self, tmp_path: Path, shell: str, *, routed: bool = False):
        self.root = tmp_path
        self.shell = shell
        script = _render(_metadata(routed=routed))
        script = script.replace("/run/", f"{tmp_path}/run/")
        script = script.replace("/etc/container-apps", f"{tmp_path}/etc/container-apps")

        self.app_dir = tmp_path / "lib" / PKG
        self.app_dir.mkdir(parents=True)
        self.wrapper = self.app_dir / "compose"
        self.wrapper.write_text(script)
        self.wrapper.chmod(0o755)

        self.bin_dir = tmp_path / "bin"
        self.bin_dir.mkdir()
        stub = self.bin_dir / "docker"
        stub.write_text(DOCKER_STUB)
        stub.chmod(0o755)

        self.out = tmp_path / "out"
        self.out.mkdir()

        self.etc_dir = tmp_path / "etc" / "container-apps" / PKG
        self.run_dir = tmp_path / "run" / "container-apps" / PKG
        self.labels = tmp_path / "run" / "halos" / "routing-labels" / f"{APP_ID}.yml"
        self.domain_env = tmp_path / "run" / "halos" / "domain.env"
        self.fragments = self.app_dir / "compose.d"

    def write(self, path: Path, content: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def fragment(self, name: str) -> None:
        self.write(self.fragments / name, "services: {}\n")

    def run(
        self,
        *args: str,
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
        stub_exit: int = 0,
    ) -> Result:
        env = {
            "PATH": f"{self.bin_dir}:/usr/bin:/bin",
            "STUB_OUT": str(self.out),
            "STUB_EXIT": str(stub_exit),
            **(extra_env or {}),
        }
        proc = subprocess.run(
            [self.shell, str(self.wrapper), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd or self.root,
        )
        argv_raw = (self.out / "argv").read_text()
        recorded_env = dict(
            line.split("=", 1)
            for line in (self.out / "env").read_text().splitlines()
            if "=" in line
        )
        return Result(
            argv=argv_raw.split("\0")[:-1],
            cwd=(self.out / "cwd").read_text().strip(),
            env=recorded_env,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )


@pytest.fixture(params=_shells())
def shell(request) -> str:
    return request.param


class TestFileList:
    def test_no_compose_d_passes_only_the_shipped_file(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        assert box.run("up").argv == [*BASE, "up"]

    def test_routed_app_appends_labels_after_shipped_file(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell, routed=True)
        box.write(box.labels, "services: {}\n")

        assert box.run("up").argv == [*BASE, "-f", str(box.labels), "up"]

    def test_routed_app_without_labels_file_skips_it(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell, routed=True)
        result = box.run("up")

        assert result.returncode == 0
        assert result.argv == [*BASE, "up"]

    def test_unrouted_app_ignores_a_labels_file(self, tmp_path, shell):
        """Routing is decided at generation time, not by what is in /run."""
        box = Sandbox(tmp_path, shell)
        box.write(box.labels, "services: {}\n")

        assert box.run("up").argv == [*BASE, "up"]

    def test_fragments_follow_labels_in_byte_order(self, tmp_path, shell):
        """Byte order puts B.yml before a.yml; a UTF-8 collation would not."""
        box = Sandbox(tmp_path, shell, routed=True)
        box.write(box.labels, "services: {}\n")
        for name in ("a.yml", "20-b.yml", "10-a.yaml", "B.yml"):
            box.fragment(name)

        result = box.run("up", extra_env={"LC_ALL": "en_US.UTF-8"})

        assert result.argv == [
            *BASE,
            "-f",
            str(box.labels),
            "-f",
            "compose.d/10-a.yaml",
            "-f",
            "compose.d/20-b.yml",
            "-f",
            "compose.d/B.yml",
            "-f",
            "compose.d/a.yml",
            "up",
        ]

    def test_empty_compose_d_passes_no_glob(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragments.mkdir()

        assert box.run("up").argv == [*BASE, "up"]

    def test_fragment_name_with_space_is_one_argument(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragment("my fragment.yml")

        assert box.run("up").argv == [*BASE, "-f", "compose.d/my fragment.yml", "up"]

    def test_only_yml_and_yaml_files_are_passed(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragment("10-a.yml")
        box.fragment("foo.yml.dpkg-old")
        box.fragment("README")
        (box.fragments / "subdir.yml").mkdir()

        assert box.run("up").argv == [*BASE, "-f", "compose.d/10-a.yml", "up"]

    def test_runs_in_app_dir_from_any_cwd(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragment("10-a.yml")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        result = box.run("up", cwd=elsewhere)

        assert result.argv == [*BASE, "-f", "compose.d/10-a.yml", "up"]
        assert Path(result.cwd).resolve() == box.app_dir.resolve()


class TestFragmentLogging:
    def test_fragments_are_listed_on_stderr(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragment("20-b.yml")
        box.fragment("10-a.yaml")

        assert box.run("up").stderr == "compose.d fragments: 10-a.yaml 20-b.yml\n"

    def test_nothing_logged_without_fragments(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragments.mkdir()

        assert box.run("up").stderr == ""


class TestCheck:
    def _env_files(self, box: Sandbox) -> None:
        box.write(box.etc_dir / "env.defaults", "A=defaults\nB=defaults\nC=defaults\n")
        box.write(box.etc_dir / "env", "B=env\nC=env\n")
        box.write(box.run_dir / "runtime.env", "C=runtime\n")

    def test_check_validates_with_unit_environment(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell, routed=True)
        self._env_files(box)
        box.write(box.domain_env, "HALOS_DOMAIN=boat.example\n")
        box.write(box.labels, "services: {}\n")
        box.fragment("10-a.yml")

        result = box.run("check")

        assert result.argv == [
            *BASE,
            "-f",
            str(box.labels),
            "-f",
            "compose.d/10-a.yml",
            "config",
            "--quiet",
        ]
        assert result.env["HALOS_SYSTEMD_STARTED"] == "1"
        assert result.env["A"] == "defaults"
        assert result.env["B"] == "env"
        assert result.env["C"] == "runtime"
        assert result.env["HALOS_DOMAIN"] == "boat.example"
        assert result.stderr == "compose.d fragments: 10-a.yml\n"

    def test_check_on_unrouted_app_skips_domain_env(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        self._env_files(box)
        box.write(box.domain_env, "HALOS_DOMAIN=boat.example\n")

        result = box.run("check")

        assert result.argv == [*BASE, "config", "--quiet"]
        assert "HALOS_DOMAIN" not in result.env
        assert result.env["C"] == "runtime"

    def test_check_without_env_files_still_validates(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell, routed=True)

        result = box.run("check")

        assert result.returncode == 0
        assert result.argv == [*BASE, "config", "--quiet"]
        assert result.env["HALOS_SYSTEMD_STARTED"] == "1"

    def test_check_reports_validation_failure(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        assert box.run("check", stub_exit=15).returncode == 15


class TestPassthrough:
    def test_passthrough_does_not_set_sentinel(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.write(box.etc_dir / "env", "A=env\n")

        result = box.run("up")

        assert "HALOS_SYSTEMD_STARTED" not in result.env
        assert "A" not in result.env

    def test_passthrough_keeps_callers_sentinel(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        result = box.run("up", extra_env={"HALOS_SYSTEMD_STARTED": "1"})

        assert result.env["HALOS_SYSTEMD_STARTED"] == "1"

    def test_arguments_pass_through_verbatim(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        box.fragment("10-a.yml")

        result = box.run("exec", "app", "sh", "-c", "echo a  b")

        assert result.argv == [
            *BASE,
            "-f",
            "compose.d/10-a.yml",
            "exec",
            "app",
            "sh",
            "-c",
            "echo a  b",
        ]

    def test_exit_status_propagates(self, tmp_path, shell):
        box = Sandbox(tmp_path, shell)
        assert box.run("up", stub_exit=7).returncode == 7
