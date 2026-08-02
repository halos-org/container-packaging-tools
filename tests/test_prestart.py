"""Unit tests for prestart script generation."""

import shutil
import subprocess
from unittest import mock

import pytest

from generate_container_packages.loader import AppDefinition
from generate_container_packages.prestart import (
    generate_prestart_script,
    get_homarr_url_expression,
)


class TestGetHomarrUrlExpression:
    """Tests for get_homarr_url_expression function."""

    def test_http_with_port_var(self):
        """Test URL expression with http protocol and port variable."""
        web_ui = {"enabled": True, "protocol": "http", "port": 3000}
        default_config = {"APP_PORT": "3000"}

        result = get_homarr_url_expression(web_ui, default_config)

        # Should use APP_PORT with fallback to 3000
        assert result is not None
        assert "http://" in result
        assert "${APP_PORT:-3000}" in result
        # Host comes from the inherited HALOS_DOMAIN, never a hardcoded .local
        assert "${HALOS_DOMAIN}" in result
        assert ".local" not in result

    def test_https_protocol(self):
        """Test URL expression with https protocol."""
        web_ui = {"enabled": True, "protocol": "https", "port": 8443}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert result is not None
        assert "https://" in result
        assert ":8443" in result

    def test_with_path(self):
        """Test URL expression with path."""
        web_ui = {"enabled": True, "protocol": "http", "port": 8080, "path": "/admin"}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert result is not None
        assert "/admin" in result

    def test_default_protocol_is_http(self):
        """Test that default protocol is http when not specified."""
        web_ui = {"enabled": True, "port": 8080}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert result is not None
        assert "http://" in result

    def test_disabled_web_ui_returns_none(self):
        """Test that disabled web_ui returns None."""
        web_ui = {"enabled": False, "port": 8080}
        default_config = {}

        result = get_homarr_url_expression(web_ui, default_config)

        assert result is None


class TestGeneratePrestartScript:
    """Tests for generate_prestart_script function."""

    def test_basic_script_structure(self):
        """Test that prestart script has correct basic structure."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Check shebang
        assert script.startswith("#!/bin/bash")
        # Check set -e for error handling
        assert "set -e" in script
        # Check runtime env directory
        assert "/run/container-apps/test-app-container" in script
        # runtime.env is created mode 600 before any write
        assert "install -m 600" in script
        # HOSTNAME is no longer written into runtime.env / the container env
        assert "HOSTNAME=" not in script

    def test_script_loads_env_files(self):
        """Test that script loads existing env files."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Should load env.defaults and env
        assert "/etc/container-apps/test-app-container/env.defaults" in script
        assert "/etc/container-apps/test-app-container/env" in script
        # Should use source/dot command
        assert ". " in script or "source " in script

    def test_script_generates_homarr_url(self):
        """Test that script generates HOMARR_URL when web_ui is enabled."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "default_config": {"APP_PORT": "3000"},
        }

        script = generate_prestart_script(app_def)

        # Should set HOMARR_URL built from the inherited HALOS_DOMAIN
        assert "HOMARR_URL=" in script
        assert "${HALOS_DOMAIN}" in script

    def test_script_does_not_resolve_halos_domain(self):
        """Generated prestart inherits HALOS_DOMAIN; it must not resolve or
        write it, and must not hardcode .local anywhere."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "default_config": {"APP_PORT": "3000"},
        }

        script = generate_prestart_script(app_def)

        # No self-resolution of HALOS_DOMAIN back into runtime.env (R3 feedback
        # loop) and no .local hardcoding (R2).
        assert 'HALOS_DOMAIN="${HOSTNAME}.local"' not in script
        assert "HALOS_DOMAIN=" not in script
        assert ".local" not in script

    def test_script_without_web_ui(self):
        """Test script when web_ui is not enabled."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": False},
        }

        script = generate_prestart_script(app_def)

        # HOSTNAME is not written; HOMARR_URL absent when web_ui disabled
        assert "HOSTNAME=" not in script
        assert "HOMARR_URL=" not in script
        # runtime.env is still created 600, and the no-web_ui branch must never
        # introduce a truncating write either.
        assert "install -m 600 /dev/null" in script
        assert '> "$RUNTIME_ENV"' not in script.replace('>> "$RUNTIME_ENV"', "")

    def test_script_without_web_ui_key(self):
        """Test script when web_ui key is missing."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
        }

        script = generate_prestart_script(app_def)

        # No HOSTNAME write, no HOMARR_URL when web_ui key is absent
        assert "HOSTNAME=" not in script
        assert "HOMARR_URL=" not in script

    def test_script_writes_to_runtime_env(self):
        """Test that script writes variables to runtime.env."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # Should write to runtime.env
        assert "runtime.env" in script
        # Should echo variables to file
        assert "echo" in script or ">>" in script

    def test_script_creates_runtime_directory(self):
        """Test that script creates the runtime directory."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
        }

        script = generate_prestart_script(app_def)

        # Should create directory with mkdir -p
        assert "mkdir -p" in script

    def test_script_is_executable_bash(self):
        """Test that script is valid executable bash syntax."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "signal-k-container",
            "name": "Signal K",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "default_config": {"SIGNALK_PORT": "3000"},
        }

        script = generate_prestart_script(app_def)

        # Basic bash syntax checks
        assert script.startswith("#!/bin/bash")
        # No unclosed quotes (basic check)
        assert script.count('"') % 2 == 0

    def test_runtime_env_created_600_before_any_write(self):
        """runtime.env is created mode 600 before the first content write, so the
        mode predates any (possibly secret-bearing) content and survives appends."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        # The 600 creation must appear, and precede any append to runtime.env
        assert "install -m 600 /dev/null" in script
        create_idx = script.index("install -m 600 /dev/null")
        first_append_idx = script.index('>> "$RUNTIME_ENV"')
        assert create_idx < first_append_idx
        # Framework writes use append, never truncate
        assert '> "$RUNTIME_ENV"' not in script.replace('>> "$RUNTIME_ENV"', "")

    def test_sources_app_prestart_hook(self):
        """Generated prestart sources an optional app-prestart.sh hook from the
        package lib dir, guarded so absence is a no-op."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
        }

        script = generate_prestart_script(app_def)

        hook = "/var/lib/container-apps/test-app-container/app-prestart.sh"
        # Guarded source, as a statement rather than an `&&` expression -- see
        # TestPrestartExitStatus for why the distinction matters.
        assert hook in script
        assert f'if [ -f "{hook}" ]; then' in script
        assert f'. "{hook}"' in script
        # The hook is sourced after the LAST runtime.env write (not merely after
        # the RUNTIME_ENV declaration), so framework scaffolding is fully in place.
        assert script.rindex('>> "$RUNTIME_ENV"') < script.index(hook)


class TestPrestartExitStatus:
    """The generated script runs as ExecStartPre, so its exit status gates the app.

    These tests execute the script instead of inspecting its text. A previous
    version ended with `[ -f <hook> ] && . <hook>`, which made a missing hook the
    script's exit status: every app that shipped no prestart.sh failed
    ExecStartPre and never started. Text assertions could not see that.
    """

    def _run(self, tmp_path, hook_body: str | None) -> subprocess.CompletedProcess:
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {"package_name": "test-app-container", "name": "Test App"}
        script = generate_prestart_script(app_def)

        # Redirect the framework's absolute paths into the sandbox.
        script = script.replace("/run/container-apps", f"{tmp_path}/run")
        script = script.replace("/etc/container-apps", f"{tmp_path}/etc")
        script = script.replace("/var/lib/container-apps", f"{tmp_path}/lib")

        hook_path = tmp_path / "lib/test-app-container/app-prestart.sh"
        if hook_body is not None:
            hook_path.parent.mkdir(parents=True, exist_ok=True)
            hook_path.write_text(hook_body)

        script_path = tmp_path / "prestart.sh"
        script_path.write_text(script)
        script_path.chmod(0o755)
        return subprocess.run(
            ["bash", str(script_path)], capture_output=True, text=True
        )

    def test_succeeds_when_no_hook_is_present(self, tmp_path):
        """An app that ships no prestart.sh must still start."""
        assert self._run(tmp_path, None).returncode == 0

    def test_succeeds_when_hook_is_present(self, tmp_path):
        assert self._run(tmp_path, "#!/bin/bash\ntrue\n").returncode == 0

    def test_hook_failure_still_propagates(self, tmp_path):
        """Absence is a no-op, but a hook that fails must fail the start."""
        assert self._run(tmp_path, "#!/bin/bash\nexit 3\n").returncode != 0


class TestOidcSectionWiring:
    """generate_prestart_script emits the OIDC section only for mode: oidc apps."""

    def _oidc_app(self, *, app_id="grafana", with_app_id=True):
        app_def = mock.Mock(spec=AppDefinition)
        meta = {
            "package_name": "marine-grafana-container",
            "name": "Grafana",
            "web_ui": {"enabled": True, "protocol": "http", "port": 3000},
            "routing": {
                "auth": {
                    "mode": "oidc",
                    "oidc": {
                        "client_name": "Grafana",
                        "token_endpoint_auth_method": "client_secret_basic",
                        "redirect": {"style": "port", "path": "/login/generic_oauth"},
                        "env": {
                            "GRAFANA_OIDC_CLIENT_SECRET": "secret",
                            "HALOS_EXTERNAL_PORT": "external_port",
                        },
                    },
                }
            },
        }
        if with_app_id:
            meta["app_id"] = app_id
        app_def.metadata = meta
        return app_def

    def test_oidc_app_emits_section(self):
        script = generate_prestart_script(self._oidc_app())
        assert "# --- OIDC client registration" in script
        assert "cat > /etc/halos/oidc-clients.d/grafana.yml << EOF" in script
        # the port-registry lookup keys on app_id
        assert 'grep "^grafana=" /etc/halos/port-registry' in script

    def test_app_id_falls_back_to_package_name(self):
        script = generate_prestart_script(self._oidc_app(with_app_id=False))
        # no app_id -> port-registry key and client_id use package_name
        assert 'grep "^marine-grafana-container=" /etc/halos/port-registry' in script

    def test_forward_auth_app_has_no_oidc_section(self):
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "name": "Test App",
            "web_ui": {"enabled": True, "protocol": "http", "port": 8080},
            "routing": {"auth": {"mode": "forward_auth"}},
        }
        script = generate_prestart_script(app_def)
        assert "OIDC client registration" not in script
        assert "oidc-clients.d" not in script

    def test_generated_oidc_prestart_is_valid_bash(self):
        """The assembled script (heredoc, case block, expansions) must parse."""
        if shutil.which("bash") is None:
            pytest.skip("bash not available")
        script = generate_prestart_script(self._oidc_app())
        result = subprocess.run(
            ["bash", "-n"], input=script, text=True, capture_output=True
        )
        assert result.returncode == 0, result.stderr
