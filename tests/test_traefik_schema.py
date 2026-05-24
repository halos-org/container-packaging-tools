"""Tests for Traefik configuration schema in metadata.yaml."""

import pytest
from pydantic import ValidationError

from schemas.metadata import (
    TraefikConfig,
    TraefikForwardAuth,
    TraefikOIDC,
)


class TestTraefikForwardAuth:
    """Tests for TraefikForwardAuth model."""

    def test_default_headers_empty(self) -> None:
        """Default headers should be an empty dict."""
        forward_auth = TraefikForwardAuth()
        assert forward_auth.headers == {}

    def test_custom_headers(self) -> None:
        """Custom headers should be accepted."""
        forward_auth = TraefikForwardAuth(
            headers={
                "Remote-User": "X-WEBAUTH-USER",
                "Remote-Groups": "X-WEBAUTH-GROUPS",
            }
        )
        assert forward_auth.headers["Remote-User"] == "X-WEBAUTH-USER"
        assert forward_auth.headers["Remote-Groups"] == "X-WEBAUTH-GROUPS"


class TestTraefikOIDC:
    """Tests for TraefikOIDC model."""

    def test_minimal_config(self) -> None:
        """Minimal OIDC config with just client_name."""
        oidc = TraefikOIDC(client_name="My App")
        assert oidc.client_name == "My App"
        assert oidc.scopes == ["openid", "profile", "email"]
        assert oidc.redirect_path == "/callback"
        assert oidc.consent_mode == "implicit"

    def test_full_config(self) -> None:
        """Full OIDC config with all fields."""
        oidc = TraefikOIDC(
            client_name="Grafana Dashboard",
            scopes=["openid", "profile", "email", "groups"],
            redirect_path="/api/auth/callback/oidc",
            consent_mode="explicit",
        )
        assert oidc.client_name == "Grafana Dashboard"
        assert oidc.scopes == ["openid", "profile", "email", "groups"]
        assert oidc.redirect_path == "/api/auth/callback/oidc"
        assert oidc.consent_mode == "explicit"

    def test_empty_client_name_error(self) -> None:
        """Empty client_name should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikOIDC(client_name="")
        assert "client_name" in str(exc_info.value)

    def test_invalid_consent_mode_error(self) -> None:
        """Invalid consent_mode should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikOIDC(client_name="My App", consent_mode="invalid")  # type: ignore[arg-type]
        assert "consent_mode" in str(exc_info.value)

    def test_pre_configured_consent_mode(self) -> None:
        """pre-configured consent mode should be valid."""
        oidc = TraefikOIDC(client_name="My App", consent_mode="pre-configured")
        assert oidc.consent_mode == "pre-configured"


class TestTraefikConfig:
    """Tests for TraefikConfig model."""

    def test_default_values(self) -> None:
        """Default values should use forward_auth."""
        config = TraefikConfig()
        assert config.auth == "forward_auth"
        assert config.forward_auth is None
        assert config.oidc is None
        assert config.host_port is None

    def test_forward_auth_config(self) -> None:
        """Valid forward_auth configuration."""
        config = TraefikConfig(
            auth="forward_auth",
            forward_auth=TraefikForwardAuth(headers={"Remote-User": "X-WEBAUTH-USER"}),
        )
        assert config.auth == "forward_auth"
        assert config.forward_auth is not None
        assert config.forward_auth.headers["Remote-User"] == "X-WEBAUTH-USER"

    def test_oidc_config(self) -> None:
        """Valid OIDC configuration."""
        config = TraefikConfig(
            auth="oidc",
            oidc=TraefikOIDC(
                client_name="Homarr Dashboard",
                scopes=["openid", "profile", "email", "groups"],
                redirect_path="/api/auth/callback/oidc",
            ),
        )
        assert config.auth == "oidc"
        assert config.oidc is not None
        assert config.oidc.client_name == "Homarr Dashboard"

    def test_none_auth_config(self) -> None:
        """Valid none authentication configuration."""
        config = TraefikConfig(auth="none")
        assert config.auth == "none"

    def test_oidc_requires_oidc_section(self) -> None:
        """auth=oidc without oidc section should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikConfig(auth="oidc")
        assert "oidc config required" in str(exc_info.value).lower()

    def test_host_port_config(self) -> None:
        """Valid host_port configuration for host networking apps."""
        config = TraefikConfig(
            auth="forward_auth",
            host_port=3000,
        )
        assert config.host_port == 3000

    def test_host_port_invalid_range_low(self) -> None:
        """host_port below 1 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikConfig(host_port=0)
        assert "host_port" in str(exc_info.value)

    def test_host_port_invalid_range_high(self) -> None:
        """host_port above 65535 should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikConfig(host_port=70000)
        assert "host_port" in str(exc_info.value)

    def test_invalid_auth_mode(self) -> None:
        """Invalid auth mode should fail."""
        with pytest.raises(ValidationError) as exc_info:
            TraefikConfig(auth="invalid")  # type: ignore[arg-type]
        assert "auth" in str(exc_info.value)

    def test_forward_auth_without_section_uses_default(self) -> None:
        """auth=forward_auth without forward_auth section uses default middleware."""
        config = TraefikConfig(auth="forward_auth")
        assert config.auth == "forward_auth"
        assert config.forward_auth is None  # None means use default authelia@file

    def test_oidc_with_forward_auth_section_ignored(self) -> None:
        """When auth=oidc, forward_auth section is allowed but unused."""
        config = TraefikConfig(
            auth="oidc",
            oidc=TraefikOIDC(client_name="My App"),
            forward_auth=TraefikForwardAuth(headers={"foo": "bar"}),
        )
        assert config.auth == "oidc"
        assert config.forward_auth is not None  # Allowed but unused
