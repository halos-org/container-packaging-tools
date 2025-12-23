"""Tests for OIDC client snippet generation."""

import yaml

from generate_container_packages.oidc_snippet import generate_oidc_snippet


class TestGenerateOIDCSnippet:
    """Tests for generate_oidc_snippet function."""

    def test_non_oidc_app_returns_none(self) -> None:
        """Apps without auth=oidc should return None."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
            },
        }
        result = generate_oidc_snippet(metadata)
        assert result is None

    def test_no_traefik_config_returns_none(self) -> None:
        """Apps without traefik config should return None."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
        }
        result = generate_oidc_snippet(metadata)
        assert result is None

    def test_oidc_app_generates_snippet(self) -> None:
        """OIDC apps should generate valid snippet."""
        metadata = {
            "app_id": "homarr",
            "package_name": "homarr-container",
            "traefik": {
                "subdomain": "",
                "auth": "oidc",
                "oidc": {
                    "client_name": "Homarr Dashboard",
                    "scopes": ["openid", "profile", "email", "groups"],
                    "redirect_path": "/api/auth/callback/oidc",
                    "consent_mode": "implicit",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        # Parse YAML (skip comment lines)
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        assert snippet["client_id"] == "homarr"
        assert snippet["client_name"] == "Homarr Dashboard"
        assert (
            snippet["client_secret_file"]
            == "/var/lib/container-apps/homarr-container/data/oidc-secret"
        )
        assert snippet["scopes"] == ["openid", "profile", "email", "groups"]
        assert snippet["consent_mode"] == "implicit"

    def test_redirect_uris_include_both_http_and_https(self) -> None:
        """Redirect URIs should include both HTTP and HTTPS."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
            "traefik": {
                "subdomain": "myapp",
                "auth": "oidc",
                "oidc": {
                    "client_name": "My App",
                    "redirect_path": "/callback",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        assert len(snippet["redirect_uris"]) == 2
        assert "http://myapp.${HALOS_DOMAIN}/callback" in snippet["redirect_uris"]
        assert "https://myapp.${HALOS_DOMAIN}/callback" in snippet["redirect_uris"]

    def test_empty_subdomain_uses_root_domain(self) -> None:
        """Empty subdomain should use root domain in redirect URIs."""
        metadata = {
            "app_id": "homarr",
            "package_name": "homarr-container",
            "traefik": {
                "subdomain": "",
                "auth": "oidc",
                "oidc": {
                    "client_name": "Homarr",
                    "redirect_path": "/api/auth/callback/oidc",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        # Root domain - no subdomain prefix
        assert (
            "http://${HALOS_DOMAIN}/api/auth/callback/oidc" in snippet["redirect_uris"]
        )

    def test_redirect_path_without_leading_slash(self) -> None:
        """Redirect path without leading slash should be normalized."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
            "traefik": {
                "subdomain": "myapp",
                "auth": "oidc",
                "oidc": {
                    "client_name": "My App",
                    "redirect_path": "callback",  # No leading slash
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        # Should still have proper path
        assert "http://myapp.${HALOS_DOMAIN}/callback" in snippet["redirect_uris"]

    def test_default_scopes(self) -> None:
        """Default scopes should be used if not specified."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
            "traefik": {
                "subdomain": "myapp",
                "auth": "oidc",
                "oidc": {
                    "client_name": "My App",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        assert snippet["scopes"] == ["openid", "profile", "email"]

    def test_snippet_has_header_comments(self) -> None:
        """Snippet should have header comments."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
            "traefik": {
                "subdomain": "myapp",
                "auth": "oidc",
                "oidc": {
                    "client_name": "My App",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        assert "# OIDC client configuration for myapp" in result
        assert "# Installed to /etc/halos/oidc-clients.d/myapp.yml" in result

    def test_subdomain_defaults_to_app_id(self) -> None:
        """When subdomain is None, app_id is used."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "traefik": {
                "auth": "oidc",
                "oidc": {
                    "client_name": "Grafana",
                },
            },
        }
        result = generate_oidc_snippet(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        snippet = yaml.safe_load("\n".join(content_lines))

        assert "http://grafana.${HALOS_DOMAIN}/callback" in snippet["redirect_uris"]
