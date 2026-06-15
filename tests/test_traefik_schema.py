"""Tests for Traefik configuration schema in metadata.yaml."""

from schemas.metadata import TraefikForwardAuth


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
