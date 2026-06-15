"""Tests for the declarative OIDC client config (routing.auth.oidc)."""

import pytest
from pydantic import ValidationError

from schemas.metadata import OidcConfig, OidcRedirect, RoutingAuth


class TestOidcConfig:
    """OidcConfig must round-trip both real consumers (grafana, signalk)."""

    def test_grafana_shape_port_based(self) -> None:
        """Grafana: port-based redirect, client_secret_basic, secret+external_port env."""
        cfg = OidcConfig(
            client_name="Grafana",
            token_endpoint_auth_method="client_secret_basic",
            redirect=OidcRedirect(style="port", path="/login/generic_oauth"),
            env={
                "GRAFANA_OIDC_CLIENT_SECRET": "secret",
                "HALOS_EXTERNAL_PORT": "external_port",
            },
        )
        assert cfg.redirect.style == "port"
        assert cfg.token_endpoint_auth_method == "client_secret_basic"
        assert cfg.env["HALOS_EXTERNAL_PORT"] == "external_port"
        # client_id defaults to None (generator fills from app_id)
        assert cfg.client_id is None
        # scopes default includes groups (both consumers need it)
        assert "groups" in cfg.scopes

    def test_signalk_shape_path_based(self) -> None:
        """Signal K: path-based redirect, client_secret_post, issuer/redirect/secret env."""
        cfg = OidcConfig(
            client_name="Signal K Server",
            token_endpoint_auth_method="client_secret_post",
            redirect=OidcRedirect(
                style="path",
                path="/signalk-server/signalk/v1/auth/oidc/callback",
            ),
            env={
                "SIGNALK_OIDC_CLIENT_SECRET": "secret",
                "SIGNALK_OIDC_ISSUER": "issuer",
                "SIGNALK_OIDC_REDIRECT_URI": "redirect",
            },
        )
        assert cfg.redirect.style == "path"
        assert cfg.token_endpoint_auth_method == "client_secret_post"
        assert set(cfg.env.values()) == {"secret", "issuer", "redirect"}

    def test_defaults(self) -> None:
        """Optional fields default sensibly."""
        cfg = OidcConfig(
            client_name="App",
            redirect=OidcRedirect(style="path", path="/cb"),
        )
        assert cfg.scopes == ["openid", "profile", "email", "groups"]
        assert cfg.consent_mode == "implicit"
        assert cfg.token_endpoint_auth_method == "client_secret_basic"
        assert cfg.env == {}

    def test_missing_client_name_errors(self) -> None:
        with pytest.raises(ValidationError) as exc:
            OidcConfig(redirect=OidcRedirect(style="path", path="/cb"))  # type: ignore[call-arg]
        assert "client_name" in str(exc.value)

    def test_redirect_path_must_be_absolute(self) -> None:
        with pytest.raises(ValidationError) as exc:
            OidcRedirect(style="path", path="login/cb")
        assert "must start with '/'" in str(exc.value)

    def test_invalid_redirect_style_errors(self) -> None:
        with pytest.raises(ValidationError):
            OidcRedirect(style="subdomain", path="/cb")  # type: ignore[arg-type]

    def test_invalid_env_source_errors(self) -> None:
        with pytest.raises(ValidationError):
            OidcConfig(
                client_name="App",
                redirect=OidcRedirect(style="path", path="/cb"),
                env={"FOO": "not_a_source"},  # type: ignore[dict-item]
            )


class TestRoutingAuthOidc:
    """RoutingAuth wires oidc and enforces it for mode: oidc."""

    def test_mode_oidc_requires_oidc_block(self) -> None:
        with pytest.raises(ValidationError) as exc:
            RoutingAuth(mode="oidc")
        assert "routing.auth.oidc is required" in str(exc.value)

    def test_mode_oidc_with_oidc_block_valid(self) -> None:
        auth = RoutingAuth(
            mode="oidc",
            oidc=OidcConfig(
                client_name="Grafana",
                redirect=OidcRedirect(style="port", path="/login/generic_oauth"),
            ),
        )
        assert auth.mode == "oidc"
        assert auth.oidc is not None

    def test_mode_none_without_oidc_unchanged(self) -> None:
        auth = RoutingAuth(mode="none")
        assert auth.oidc is None

    def test_mode_forward_auth_default_unaffected(self) -> None:
        auth = RoutingAuth()
        assert auth.mode == "forward_auth"
        assert auth.oidc is None
