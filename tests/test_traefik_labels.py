"""Tests for Traefik label generation."""

import pytest

from generate_container_packages.traefik import (
    _extract_container_port,
    generate_traefik_labels,
    inject_proxy_network,
)


class TestGenerateTraefikLabels:
    """Tests for generate_traefik_labels function."""

    def test_no_traefik_config_no_web_ui_returns_empty(self) -> None:
        """Apps without traefik config and without web_ui get no labels."""
        metadata = {"app_id": "myapp"}
        compose: dict = {"services": {"app": {}}}
        labels = generate_traefik_labels(metadata, compose)
        assert labels == {}

    def test_no_traefik_config_with_web_ui_enabled_gets_default_labels(self) -> None:
        """Apps with web_ui.enabled but no traefik config get default forward_auth."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
        }
        compose: dict = {"services": {"app": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert labels["traefik.enable"] == "true"
        assert "myapp.${HALOS_DOMAIN}" in labels["traefik.http.routers.myapp.rule"]
        assert labels["traefik.http.routers.myapp.middlewares"] == "authelia@file"
        assert labels["traefik.http.services.myapp.loadbalancer.server.port"] == "8080"
        assert labels["halos.subdomain"] == "myapp"

    def test_forward_auth_labels(self) -> None:
        """Forward auth apps get authelia@file middleware."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert labels["traefik.enable"] == "true"
        assert "grafana.${HALOS_DOMAIN}" in labels["traefik.http.routers.grafana.rule"]
        assert labels["traefik.http.routers.grafana.entrypoints"] == "web,websecure"
        assert labels["traefik.http.routers.grafana.middlewares"] == "authelia@file"
        assert (
            labels["traefik.http.services.grafana.loadbalancer.server.port"] == "3000"
        )
        assert labels["halos.subdomain"] == "grafana"

    def test_forward_auth_with_custom_headers_per_app_middleware(self) -> None:
        """Forward auth with custom headers uses per-app middleware."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
                "forward_auth": {
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                        "Remote-Groups": "X-WEBAUTH-GROUPS",
                    }
                },
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert (
            labels["traefik.http.routers.grafana.middlewares"]
            == "authelia-grafana@file"
        )

    def test_oidc_labels_no_middleware(self) -> None:
        """OIDC apps don't get middleware (they handle auth themselves)."""
        metadata = {
            "app_id": "homarr",
            "web_ui": {"enabled": True, "port": 7575},
            "traefik": {
                "subdomain": "",
                "auth": "oidc",
                "oidc": {
                    "client_name": "Homarr Dashboard",
                    "scopes": ["openid", "profile", "email", "groups"],
                    "redirect_path": "/api/auth/callback/oidc",
                },
            },
        }
        compose: dict = {"services": {"homarr": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert labels["traefik.enable"] == "true"
        # Empty subdomain means root domain
        assert "${HALOS_DOMAIN}`)" in labels["traefik.http.routers.homarr.rule"]
        # No middleware key should be present for OIDC apps
        assert "traefik.http.routers.homarr.middlewares" not in labels
        assert labels["halos.subdomain"] == ""

    def test_none_auth_labels_no_middleware(self) -> None:
        """None auth apps don't get middleware."""
        metadata = {
            "app_id": "avnav",
            "web_ui": {"enabled": True, "port": 8080},
            "traefik": {
                "subdomain": "avnav",
                "auth": "none",
            },
        }
        compose: dict = {"services": {"avnav": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert labels["traefik.enable"] == "true"
        assert "avnav.${HALOS_DOMAIN}" in labels["traefik.http.routers.avnav.rule"]
        assert "traefik.http.routers.avnav.middlewares" not in labels

    def test_custom_subdomain(self) -> None:
        """Custom subdomain is used in routing rule."""
        metadata = {
            "app_id": "signalk-server",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "signalk",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"signalk": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert (
            "signalk.${HALOS_DOMAIN}"
            in labels["traefik.http.routers.signalk-server.rule"]
        )
        assert labels["halos.subdomain"] == "signalk"

    def test_default_subdomain_from_app_id(self) -> None:
        """When subdomain is None, app_id is used."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
            "traefik": {
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"app": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert "myapp.${HALOS_DOMAIN}" in labels["traefik.http.routers.myapp.rule"]
        assert labels["halos.subdomain"] == "myapp"

    def test_host_networking_backend_url(self) -> None:
        """Host networking apps use host.docker.internal URL."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "signalk",
                "auth": "forward_auth",
                "host_port": 3000,
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        labels = generate_traefik_labels(metadata, compose)

        assert (
            labels["traefik.http.services.signalk.loadbalancer.server.url"]
            == "http://host.docker.internal:3000"
        )
        # No port label when using URL
        assert "traefik.http.services.signalk.loadbalancer.server.port" not in labels

    def test_host_networking_without_host_port_infers_from_web_ui(self) -> None:
        """Host networking without host_port infers from web_ui.port."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "signalk",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        labels = generate_traefik_labels(metadata, compose)

        assert (
            labels["traefik.http.services.signalk.loadbalancer.server.url"]
            == "http://host.docker.internal:3000"
        )

    def test_host_networking_without_port_raises_error(self) -> None:
        """Host networking without host_port or web_ui.port raises error."""
        metadata = {
            "app_id": "signalk",
            "traefik": {
                "subdomain": "signalk",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}

        with pytest.raises(ValueError) as exc_info:
            generate_traefik_labels(metadata, compose)
        assert "host_port" in str(exc_info.value).lower()

    def test_bridge_networking_service_port(self) -> None:
        """Bridge networking apps use service port label."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        labels = generate_traefik_labels(metadata, compose)

        assert (
            labels["traefik.http.services.grafana.loadbalancer.server.port"] == "3000"
        )
        assert "traefik.http.services.grafana.loadbalancer.server.url" not in labels

    def test_bridge_networking_uses_container_port_from_compose(self) -> None:
        """Bridge networking uses container port from docker-compose, not web_ui.port."""
        metadata = {
            "app_id": "avnav",
            "web_ui": {"enabled": True, "port": 8082},  # Host port (wrong for Traefik)
            "traefik": {
                "subdomain": "avnav",
                "auth": "none",
            },
        }
        # docker-compose: ports: ["${PORT:-3011}:8080"] -> container port is 8080
        compose: dict = {"services": {"avnav": {"ports": ["${PORT:-3011}:8080"]}}}
        labels = generate_traefik_labels(metadata, compose)

        # Should use container port 8080, not web_ui.port 8082
        assert labels["traefik.http.services.avnav.loadbalancer.server.port"] == "8080"

    def test_bridge_networking_falls_back_to_web_ui_port(self) -> None:
        """Bridge networking falls back to web_ui.port when no ports in compose."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 9000},
            "traefik": {
                "subdomain": "myapp",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"myapp": {}}}  # No ports defined
        labels = generate_traefik_labels(metadata, compose)

        # Should fall back to web_ui.port
        assert labels["traefik.http.services.myapp.loadbalancer.server.port"] == "9000"


class TestExtractContainerPort:
    """Tests for _extract_container_port helper function."""

    def test_simple_host_container_format(self) -> None:
        """Extract container port from host:container format."""
        compose = {"services": {"app": {"ports": ["3011:8080"]}}}
        assert _extract_container_port(compose) == 8080

    def test_env_var_host_container_format(self) -> None:
        """Extract container port when host is env var."""
        compose = {"services": {"app": {"ports": ["${PORT:-3011}:8080"]}}}
        assert _extract_container_port(compose) == 8080

    def test_container_port_only(self) -> None:
        """Extract port when only container port specified."""
        compose = {"services": {"app": {"ports": ["8080"]}}}
        assert _extract_container_port(compose) == 8080

    def test_with_protocol_suffix(self) -> None:
        """Extract port with protocol suffix like /tcp."""
        compose = {"services": {"app": {"ports": ["3011:8080/tcp"]}}}
        assert _extract_container_port(compose) == 8080

    def test_long_syntax_dict_format(self) -> None:
        """Extract port from long syntax dict format."""
        compose = {
            "services": {
                "app": {
                    "ports": [{"target": 8080, "published": 3011, "protocol": "tcp"}]
                }
            }
        }
        assert _extract_container_port(compose) == 8080

    def test_integer_port(self) -> None:
        """Extract port when specified as integer."""
        compose = {"services": {"app": {"ports": [8080]}}}
        assert _extract_container_port(compose) == 8080

    def test_no_ports_returns_none(self) -> None:
        """Return None when no ports defined."""
        compose = {"services": {"app": {}}}
        assert _extract_container_port(compose) is None

    def test_empty_ports_returns_none(self) -> None:
        """Return None when ports list is empty."""
        compose = {"services": {"app": {"ports": []}}}
        assert _extract_container_port(compose) is None


class TestInjectProxyNetwork:
    """Tests for inject_proxy_network function."""

    def test_adds_network_to_compose(self) -> None:
        """Network is added to compose when not host networking."""
        compose = {"services": {"app": {}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "networks" in result
        assert "halos-proxy-network" in result["networks"]
        assert result["networks"]["halos-proxy-network"]["external"] is True

    def test_adds_network_to_service(self) -> None:
        """Service gets network reference added."""
        compose = {"services": {"app": {}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "networks" in result["services"]["app"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]

    def test_host_network_no_changes(self) -> None:
        """Host networking apps don't get network added."""
        compose = {"services": {"app": {"network_mode": "host"}}}
        result = inject_proxy_network(compose, is_host_network=True)

        assert "networks" not in result or "halos-proxy-network" not in result.get(
            "networks", {}
        )

    def test_preserves_existing_networks(self) -> None:
        """Existing networks are preserved."""
        compose = {
            "services": {"app": {"networks": ["existing-net"]}},
            "networks": {"existing-net": {}},
        }
        result = inject_proxy_network(compose, is_host_network=False)

        assert "existing-net" in result["networks"]
        assert "halos-proxy-network" in result["networks"]
        assert "existing-net" in result["services"]["app"]["networks"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]

    def test_converts_list_networks_to_list_with_new_network(self) -> None:
        """List-format service networks get new network appended."""
        compose = {"services": {"app": {"networks": ["existing"]}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "existing" in result["services"]["app"]["networks"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]
