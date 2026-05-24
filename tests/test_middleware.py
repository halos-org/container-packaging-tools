"""Tests for per-app ForwardAuth middleware generation."""

import yaml

from generate_container_packages.middleware import generate_forwardauth_middleware


class TestGenerateForwardAuthMiddleware:
    """Tests for generate_forwardauth_middleware function."""

    def test_no_routing_config_returns_none(self) -> None:
        """Apps without routing config should return None."""
        metadata = {
            "app_id": "myapp",
            "package_name": "myapp-container",
        }
        result = generate_forwardauth_middleware(metadata)
        assert result is None

    def test_no_forward_auth_section_returns_none(self) -> None:
        """Apps without forward_auth section should return None."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": {
                    "mode": "forward_auth",
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)
        assert result is None

    def test_no_custom_headers_returns_none(self) -> None:
        """Apps with empty headers should return None."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": {
                    "mode": "forward_auth",
                    "forward_auth": {
                        "headers": {},
                    },
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)
        assert result is None

    def test_oidc_app_returns_none(self) -> None:
        """OIDC apps should return None (no middleware needed)."""
        metadata = {
            "app_id": "homarr",
            "package_name": "homarr-container",
            "routing": {
                "auth": {
                    "mode": "oidc",
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)
        assert result is None

    def test_none_auth_returns_none(self) -> None:
        """None auth apps should return None."""
        metadata = {
            "app_id": "avnav",
            "package_name": "avnav-container",
            "routing": {
                "auth": {
                    "mode": "none",
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)
        assert result is None

    def test_custom_headers_generates_middleware(self) -> None:
        """Apps with custom headers should generate middleware."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": {
                    "mode": "forward_auth",
                    "forward_auth": {
                        "headers": {
                            "Remote-User": "X-WEBAUTH-USER",
                            "Remote-Groups": "X-WEBAUTH-GROUPS",
                        },
                    },
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)

        assert result is not None
        # Parse YAML (skip comment lines)
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        middleware = yaml.safe_load("\n".join(content_lines))

        assert "http" in middleware
        assert "middlewares" in middleware["http"]
        assert "authelia-grafana" in middleware["http"]["middlewares"]

        config = middleware["http"]["middlewares"]["authelia-grafana"]["forwardAuth"]
        assert config["address"] == "http://authelia:9091/api/authz/forward-auth"
        assert config["trustForwardHeader"] is True

    def test_auth_response_headers_from_mapping(self) -> None:
        """Auth response headers should come from header mapping values."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": {
                    "mode": "forward_auth",
                    "forward_auth": {
                        "headers": {
                            "Remote-User": "X-WEBAUTH-USER",
                            "Remote-Groups": "X-WEBAUTH-GROUPS",
                        },
                    },
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)

        assert result is not None
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        middleware = yaml.safe_load("\n".join(content_lines))

        config = middleware["http"]["middlewares"]["authelia-grafana"]["forwardAuth"]
        response_headers = config["authResponseHeaders"]

        # The response headers should be the mapped names (Authelia headers)
        assert "Remote-User" in response_headers
        assert "Remote-Groups" in response_headers

    def test_middleware_has_header_comments(self) -> None:
        """Middleware should have header comments."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": {
                    "mode": "forward_auth",
                    "forward_auth": {
                        "headers": {"Remote-User": "X-WEBAUTH-USER"},
                    },
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)

        assert result is not None
        assert "# Per-app ForwardAuth middleware for grafana" in result
        assert "# Installed to /etc/halos/traefik-dynamic.d/grafana.yml" in result

    def test_flat_format_generates_middleware(self) -> None:
        """Flat format (auth as string) should generate middleware."""
        metadata = {
            "app_id": "grafana",
            "package_name": "grafana-container",
            "routing": {
                "auth": "forward_auth",  # string, not dict
                "forward_auth": {  # at routing level
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                    },
                },
            },
        }
        result = generate_forwardauth_middleware(metadata)

        assert result is not None
        assert "authelia-grafana" in result
        # Parse and verify structure
        content_lines = [
            line for line in result.split("\n") if line and not line.startswith("#")
        ]
        middleware = yaml.safe_load("\n".join(content_lines))
        assert "http" in middleware
        assert "authelia-grafana" in middleware["http"]["middlewares"]
