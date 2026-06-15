"""Tests for the prestart OIDC section generator (generate_oidc_section)."""

from generate_container_packages.oidc_snippet import generate_oidc_section

GRAFANA_OIDC = {
    "client_name": "Grafana",
    "token_endpoint_auth_method": "client_secret_basic",
    "redirect": {"style": "port", "path": "/login/generic_oauth"},
    "env": {
        "GRAFANA_OIDC_CLIENT_SECRET": "secret",
        "HALOS_EXTERNAL_PORT": "external_port",
    },
}

SIGNALK_OIDC = {
    "client_name": "Signal K Server",
    "token_endpoint_auth_method": "client_secret_post",
    "redirect": {
        "style": "path",
        "path": "/signalk-server/signalk/v1/auth/oidc/callback",
    },
    "env": {
        "SIGNALK_OIDC_CLIENT_SECRET": "secret",
        "SIGNALK_OIDC_ISSUER": "issuer",
        "SIGNALK_OIDC_REDIRECT_URI": "redirect",
    },
}


def _script(oidc, app_id, package_name="pkg-container"):
    return "\n".join(generate_oidc_section(oidc, app_id, package_name))


class TestPortBasedGrafana:
    def test_resolves_and_validates_external_port(self):
        s = _script(GRAFANA_OIDC, "grafana")
        # reads the registry keyed by app_id
        assert 'grep "^grafana=" /etc/halos/port-registry' in s
        # rejects empty / non-integer
        assert "*[!0-9]*)" in s
        assert "exit 1" in s

    def test_env_map_appends_secret_and_port(self):
        s = _script(GRAFANA_OIDC, "grafana")
        assert (
            'echo "GRAFANA_OIDC_CLIENT_SECRET=$(cat "$OIDC_SECRET_FILE")" >> "$RUNTIME_ENV"'
            in s
        )
        assert 'echo "HALOS_EXTERNAL_PORT=${EXTERNAL_PORT}" >> "$RUNTIME_ENV"' in s

    def test_snippet_port_based_redirect(self):
        s = _script(GRAFANA_OIDC, "grafana", "marine-grafana-container")
        # unquoted heredoc so ${EXTERNAL_PORT} expands at write time; HALOS_DOMAIN stays literal
        assert "cat > /etc/halos/oidc-clients.d/grafana.yml << EOF" in s
        assert (
            r"  - 'https://\${HALOS_DOMAIN}:${EXTERNAL_PORT}/login/generic_oauth'" in s
        )
        assert (
            "client_secret_file: /var/lib/container-apps/marine-grafana-container/data/oidc-secret"
            in s
        )
        assert "scopes: [openid, profile, email, groups]" in s
        assert "token_endpoint_auth_method: client_secret_basic" in s


class TestPathBasedSignalk:
    def test_no_port_resolution(self):
        s = _script(SIGNALK_OIDC, "signalk-server")
        assert "port-registry" not in s
        assert "EXTERNAL_PORT" not in s

    def test_env_map_issuer_and_redirect_expand_domain(self):
        s = _script(SIGNALK_OIDC, "signalk-server")
        # In runtime.env, HALOS_DOMAIN must EXPAND (container needs the real value)
        assert (
            'echo "SIGNALK_OIDC_ISSUER=https://${HALOS_DOMAIN}/sso" >> "$RUNTIME_ENV"'
            in s
        )
        assert (
            'echo "SIGNALK_OIDC_REDIRECT_URI=https://${HALOS_DOMAIN}'
            '/signalk-server/signalk/v1/auth/oidc/callback" >> "$RUNTIME_ENV"' in s
        )

    def test_snippet_path_based_redirect_literal_domain_no_port(self):
        s = _script(SIGNALK_OIDC, "signalk-server")
        # snippet keeps ${HALOS_DOMAIN} literal (merger expands), no port
        assert (
            r"  - 'https://\${HALOS_DOMAIN}/signalk-server/signalk/v1/auth/oidc/callback'"
            in s
        )
        assert ":${EXTERNAL_PORT}" not in s
        assert "token_endpoint_auth_method: client_secret_post" in s


class TestClientId:
    def test_client_id_defaults_to_app_id(self):
        s = _script(SIGNALK_OIDC, "signalk-server")
        assert "client_id: signalk-server" in s
        assert "oidc-clients.d/signalk-server.yml" in s

    def test_explicit_client_id_overrides(self):
        oidc = {**SIGNALK_OIDC, "client_id": "signalk"}
        s = _script(oidc, "signalk-server")
        assert "client_id: signalk" in s
        assert "oidc-clients.d/signalk.yml" in s


class TestEnvSources:
    def test_client_id_env_source_resolves(self):
        oidc = {
            "client_name": "App",
            "redirect": {"style": "path", "path": "/cb"},
            "env": {"APP_CLIENT_ID": "client_id"},
        }
        s = _script(oidc, "my-app", "my-app-container")
        assert 'echo "APP_CLIENT_ID=my-app" >> "$RUNTIME_ENV"' in s

    def test_issuer_env_source_resolves(self):
        oidc = {
            "client_name": "App",
            "redirect": {"style": "path", "path": "/cb"},
            "env": {"APP_ISSUER": "issuer"},
        }
        s = _script(oidc, "my-app")
        assert 'echo "APP_ISSUER=https://${HALOS_DOMAIN}/sso" >> "$RUNTIME_ENV"' in s
