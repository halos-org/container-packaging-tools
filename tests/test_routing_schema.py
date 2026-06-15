"""Tests for RoutingConfig schema validation."""

import pytest
from pydantic import ValidationError

from schemas.metadata import (
    OidcConfig,
    OidcRedirect,
    PackageMetadata,
    RoutingAuth,
    RoutingConfig,
)


class TestRoutingConfig:
    """Tests for RoutingConfig model validation."""

    def test_minimal_routing_config(self) -> None:
        """Minimal routing config should be valid."""
        config = RoutingConfig()
        assert config.auth is None  # Default to None, will be forward_auth at runtime

    def test_auth_modes(self) -> None:
        """forward_auth and none validate bare; oidc requires an oidc block."""
        for mode in ["forward_auth", "none"]:
            auth = RoutingAuth(mode=mode)  # type: ignore[arg-type]
            assert auth.mode == mode

        oidc_auth = RoutingAuth(
            mode="oidc",
            oidc=OidcConfig(
                client_name="App",
                redirect=OidcRedirect(style="path", path="/cb"),
            ),
        )
        assert oidc_auth.mode == "oidc"

    def test_invalid_auth_mode(self) -> None:
        """Invalid auth mode should fail validation."""
        with pytest.raises(ValidationError):
            RoutingAuth(mode="invalid")  # type: ignore[arg-type]

    def test_host_port_valid_range(self) -> None:
        """Host port in valid range should pass."""
        config = RoutingConfig(host_port=3000)
        assert config.host_port == 3000

        config = RoutingConfig(host_port=1)
        assert config.host_port == 1

        config = RoutingConfig(host_port=65535)
        assert config.host_port == 65535

    def test_host_port_invalid_range(self) -> None:
        """Host port outside valid range should fail."""
        with pytest.raises(ValidationError):
            RoutingConfig(host_port=0)

        with pytest.raises(ValidationError):
            RoutingConfig(host_port=65536)

        with pytest.raises(ValidationError):
            RoutingConfig(host_port=-1)

    def test_legacy_subdomain_field_silently_ignored(self) -> None:
        """RoutingConfig drops a leftover 'subdomain' key without raising.

        Old metadata.yaml files may still carry 'routing.subdomain' from before
        subdomain routing was retired. RoutingConfig has no explicit
        model_config, so Pydantic's default extra='ignore' silently drops the
        field. This test pins that backward-compat contract — a future
        maintainer who adds extra='forbid' would break old files.
        """
        config = RoutingConfig.model_validate(
            {"subdomain": "grafana", "host_port": 3000}
        )
        assert config.host_port == 3000
        assert not hasattr(config, "subdomain")


class TestRoutingAuth:
    """Tests for RoutingAuth model validation."""

    def test_default_mode(self) -> None:
        """Default auth mode should be forward_auth."""
        auth = RoutingAuth()
        assert auth.mode == "forward_auth"

    def test_forward_auth_with_headers(self) -> None:
        """Forward auth with custom headers should be valid."""
        auth = RoutingAuth(
            mode="forward_auth",
            forward_auth={"headers": {"Remote-User": "X-WEBAUTH-USER"}},
        )
        assert auth.mode == "forward_auth"
        assert auth.forward_auth is not None
        assert auth.forward_auth.headers["Remote-User"] == "X-WEBAUTH-USER"


class TestPackageMetadataWithRouting:
    """Tests for PackageMetadata with routing field."""

    @pytest.fixture
    def base_metadata(self) -> dict:
        """Base valid metadata for testing."""
        return {
            "name": "Test App",
            "app_id": "testapp",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "web",
            "architecture": "all",
        }

    def test_routing_field_accepted(self, base_metadata: dict) -> None:
        """routing field should be accepted in PackageMetadata."""
        base_metadata["routing"] = {
            "auth": {"mode": "forward_auth"},
        }
        metadata = PackageMetadata(**base_metadata)
        assert metadata.routing is not None
        assert metadata.routing.auth is not None
        assert metadata.routing.auth.mode == "forward_auth"

    def test_traefik_field_is_rejected(self, base_metadata: dict) -> None:
        """traefik field should be rejected (deprecated)."""
        base_metadata["traefik"] = {
            "auth": "forward_auth",
        }
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PackageMetadata(**base_metadata)

    def test_full_routing_config(self, base_metadata: dict) -> None:
        """Full routing config should be valid."""
        base_metadata["web_ui"] = {"enabled": True, "port": 3000}
        base_metadata["routing"] = {
            "auth": {
                "mode": "forward_auth",
                "forward_auth": {
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                        "Remote-Groups": "X-WEBAUTH-GROUPS",
                    },
                },
            },
            "host_port": None,
        }
        metadata = PackageMetadata(**base_metadata)
        assert metadata.routing is not None
        assert metadata.routing.auth is not None
        assert metadata.routing.auth.mode == "forward_auth"
        assert metadata.routing.auth.forward_auth is not None
        assert (
            metadata.routing.auth.forward_auth.headers["Remote-User"]
            == "X-WEBAUTH-USER"
        )
