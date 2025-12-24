"""Tests for generic routing.yml generation."""

import pytest
import yaml

from generate_container_packages.routing import generate_routing_yml


class TestGenerateRoutingYml:
    """Tests for generate_routing_yml function."""

    def test_no_routing_or_traefik_config_returns_none(self) -> None:
        """Apps without routing or traefik config should return None."""
        metadata = {
            "app_id": "myapp",
            "name": "My App",
        }
        compose: dict = {"services": {"app": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")
        assert result is None

    def test_no_routing_no_web_ui_returns_none(self) -> None:
        """Apps without routing config and without web_ui get no routing.yml."""
        metadata = {"app_id": "myapp"}
        compose: dict = {"services": {"app": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")
        assert result is None

    def test_web_ui_enabled_generates_routing(self) -> None:
        """Apps with web_ui.enabled get routing.yml with default forward_auth."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
        }
        compose: dict = {"services": {"app": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        assert result is not None
        routing = yaml.safe_load(result)

        assert routing["app_id"] == "myapp"
        assert routing["package_name"] == "myapp-container"
        assert routing["routing"]["subdomain"] == "myapp"
        assert routing["routing"]["backend"]["type"] == "container"
        assert routing["routing"]["backend"]["port"] == 8080
        assert routing["auth"]["mode"] == "forward_auth"
        assert routing["network"]["join_proxy_network"] is True

    def test_routing_config_basic(self) -> None:
        """Basic routing config generates correct YAML."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "grafana",
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "marine-grafana-container")

        assert result is not None
        routing = yaml.safe_load(result)

        assert routing["app_id"] == "grafana"
        assert routing["package_name"] == "marine-grafana-container"
        assert routing["routing"]["subdomain"] == "grafana"
        assert routing["routing"]["backend"]["type"] == "container"
        assert routing["routing"]["backend"]["service"] == "grafana"
        assert routing["routing"]["backend"]["port"] == 3000
        assert routing["routing"]["entry_points"] == ["http", "https"]

    def test_traefik_config_backwards_compat(self) -> None:
        """traefik: key works as backwards compatibility for routing:."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "traefik": {
                "subdomain": "grafana",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "marine-grafana-container")

        assert result is not None
        routing = yaml.safe_load(result)

        assert routing["app_id"] == "grafana"
        assert routing["routing"]["subdomain"] == "grafana"
        assert routing["auth"]["mode"] == "forward_auth"

    def test_forward_auth_mode(self) -> None:
        """Forward auth apps get auth.mode=forward_auth."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "grafana",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["auth"]["mode"] == "forward_auth"
        assert "forward_auth" not in routing["auth"]  # No custom headers

    def test_forward_auth_with_custom_headers(self) -> None:
        """Forward auth with custom headers includes header mapping."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "grafana",
                "auth": "forward_auth",
                "forward_auth": {
                    "headers": {
                        "Remote-User": "X-WEBAUTH-USER",
                        "Remote-Groups": "X-WEBAUTH-GROUPS",
                    },
                },
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["auth"]["mode"] == "forward_auth"
        assert routing["auth"]["forward_auth"]["headers"] == {
            "Remote-User": "X-WEBAUTH-USER",
            "Remote-Groups": "X-WEBAUTH-GROUPS",
        }

    def test_oidc_mode(self) -> None:
        """OIDC apps get auth.mode=oidc."""
        metadata = {
            "app_id": "homarr",
            "web_ui": {"enabled": True, "port": 7575},
            "routing": {
                "subdomain": "",
                "auth": "oidc",
                "oidc": {
                    "client_name": "Homarr Dashboard",
                },
            },
        }
        compose: dict = {"services": {"homarr": {}}}
        result = generate_routing_yml(metadata, compose, "homarr-container")

        routing = yaml.safe_load(result)
        assert routing["auth"]["mode"] == "oidc"

    def test_none_auth_mode(self) -> None:
        """None auth apps get auth.mode=none."""
        metadata = {
            "app_id": "avnav",
            "web_ui": {"enabled": True, "port": 8080},
            "routing": {
                "subdomain": "avnav",
                "auth": "none",
            },
        }
        compose: dict = {"services": {"avnav": {}}}
        result = generate_routing_yml(metadata, compose, "avnav-container")

        routing = yaml.safe_load(result)
        assert routing["auth"]["mode"] == "none"

    def test_empty_subdomain_for_root_domain(self) -> None:
        """Empty subdomain indicates root domain."""
        metadata = {
            "app_id": "homarr",
            "web_ui": {"enabled": True, "port": 7575},
            "routing": {
                "subdomain": "",
                "auth": "oidc",
                "oidc": {"client_name": "Homarr"},
            },
        }
        compose: dict = {"services": {"homarr": {}}}
        result = generate_routing_yml(metadata, compose, "homarr-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["subdomain"] == ""

    def test_custom_subdomain(self) -> None:
        """Custom subdomain is used."""
        metadata = {
            "app_id": "signalk-server",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "signalk",
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"signalk": {}}}
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["subdomain"] == "signalk"

    def test_default_subdomain_from_app_id(self) -> None:
        """When subdomain is None, app_id is used as default."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
            "routing": {
                "auth": "forward_auth",
            },
        }
        compose: dict = {"services": {"app": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["subdomain"] == "myapp"


class TestRoutingBackendDetection:
    """Tests for backend auto-detection from compose."""

    def test_bridge_networking_backend_type_container(self) -> None:
        """Bridge networking apps have backend.type=container."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {"subdomain": "grafana"},
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["type"] == "container"

    def test_host_networking_backend_type_host(self) -> None:
        """Host networking apps have backend.type=host."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "signalk",
                "host_port": 3000,
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["type"] == "host"
        assert routing["routing"]["backend"]["port"] == 3000

    def test_first_service_used_as_backend_service(self) -> None:
        """First service in compose is used as backend.service."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"primary": {}, "secondary": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["service"] == "primary"

    def test_port_from_web_ui(self) -> None:
        """Backend port is taken from web_ui.port."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 9999},
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"app": {}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 9999

    def test_host_port_override_for_host_networking(self) -> None:
        """host_port overrides web_ui.port for host networking apps."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "signalk",
                "host_port": 3001,  # Different from web_ui.port
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3001


class TestRoutingNetwork:
    """Tests for network configuration in routing.yml."""

    def test_bridge_network_join_proxy_network_true(self) -> None:
        """Bridge networking apps have join_proxy_network=true."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {"subdomain": "grafana"},
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["network"]["join_proxy_network"] is True

    def test_host_network_join_proxy_network_false(self) -> None:
        """Host networking apps have join_proxy_network=false."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "signalk",
                "host_port": 3000,
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["network"]["join_proxy_network"] is False


class TestRoutingYmlFormat:
    """Tests for routing.yml output format."""

    def test_has_header_comment(self) -> None:
        """routing.yml should have descriptive header comment."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {"subdomain": "grafana"},
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        assert result is not None
        assert "# Generic routing declaration for grafana" in result
        assert "# Installed to /etc/halos/routing.d/grafana.yml" in result

    def test_valid_yaml_output(self) -> None:
        """Output should be valid YAML."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "grafana",
                "auth": "forward_auth",
                "forward_auth": {
                    "headers": {"Remote-User": "X-WEBAUTH-USER"},
                },
            },
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        # Should parse without errors
        routing = yaml.safe_load(result)
        assert isinstance(routing, dict)
        assert "app_id" in routing
        assert "routing" in routing
        assert "auth" in routing
        assert "network" in routing

    def test_entry_points_as_list(self) -> None:
        """entry_points should be a list."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {"subdomain": "grafana"},
        }
        compose: dict = {"services": {"grafana": {}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert isinstance(routing["routing"]["entry_points"], list)
        assert "http" in routing["routing"]["entry_points"]
        assert "https" in routing["routing"]["entry_points"]


class TestRoutingEdgeCases:
    """Tests for edge cases in routing.yml generation."""

    def test_missing_web_ui_port_with_routing_raises_error(self) -> None:
        """Routing without web_ui.port should raise an error."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True},  # No port
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"app": {}}}

        with pytest.raises(ValueError) as exc_info:
            generate_routing_yml(metadata, compose, "myapp-container")
        assert "port" in str(exc_info.value).lower()

    def test_host_networking_without_host_port_infers_from_web_ui(self) -> None:
        """Host networking without host_port should infer from web_ui.port."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {
                "subdomain": "signalk",
                # No host_port - should use web_ui.port
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3000
        assert routing["routing"]["backend"]["type"] == "host"

    def test_host_networking_without_any_port_raises_error(self) -> None:
        """Host networking without any port should raise an error."""
        metadata = {
            "app_id": "signalk",
            "routing": {
                "subdomain": "signalk",
            },
        }
        compose: dict = {"services": {"signalk": {"network_mode": "host"}}}

        with pytest.raises(ValueError) as exc_info:
            generate_routing_yml(metadata, compose, "signalk-container")
        assert "port" in str(exc_info.value).lower()

    def test_empty_services_raises_error(self) -> None:
        """Compose with no services should raise an error."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {}}

        with pytest.raises(ValueError) as exc_info:
            generate_routing_yml(metadata, compose, "myapp-container")
        assert "service" in str(exc_info.value).lower()


class TestContainerPortExtraction:
    """Tests for extracting container port from docker-compose port mappings."""

    def test_container_port_preferred_over_web_ui_port(self) -> None:
        """Container port from docker-compose is preferred over web_ui.port."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3001},  # Host port
            "routing": {"subdomain": "grafana"},
        }
        # docker-compose maps 3001:3000, so container port is 3000
        compose: dict = {"services": {"grafana": {"ports": ["3001:3000"]}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3000

    def test_container_port_with_env_var_host(self) -> None:
        """Container port extracted correctly when host uses env var."""
        metadata = {
            "app_id": "grafana",
            "web_ui": {"enabled": True, "port": 3001},
            "routing": {"subdomain": "grafana"},
        }
        # Host port uses env var, container port is 3000
        compose: dict = {"services": {"grafana": {"ports": ["${PORT:-3001}:3000"]}}}
        result = generate_routing_yml(metadata, compose, "grafana-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3000

    def test_container_port_with_protocol(self) -> None:
        """Container port extracted correctly when protocol is specified."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 8080},
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"app": {"ports": ["8080:80/tcp"]}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 80

    def test_container_port_simple_format(self) -> None:
        """Container port extracted when only container port is specified."""
        metadata = {
            "app_id": "myapp",
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"app": {"ports": ["8080"]}}}
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 8080

    def test_container_port_long_syntax(self) -> None:
        """Container port extracted from long syntax port definition."""
        metadata = {
            "app_id": "myapp",
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {
            "services": {"app": {"ports": [{"target": 3000, "published": 3001}]}}
        }
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3000

    def test_fallback_to_web_ui_port_when_no_ports(self) -> None:
        """Falls back to web_ui.port when no ports in docker-compose."""
        metadata = {
            "app_id": "myapp",
            "web_ui": {"enabled": True, "port": 9999},
            "routing": {"subdomain": "myapp"},
        }
        compose: dict = {"services": {"app": {}}}  # No ports
        result = generate_routing_yml(metadata, compose, "myapp-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 9999

    def test_host_networking_ignores_compose_ports(self) -> None:
        """Host networking uses host_port, not container port extraction."""
        metadata = {
            "app_id": "signalk",
            "web_ui": {"enabled": True, "port": 3000},
            "routing": {"subdomain": "signalk", "host_port": 3000},
        }
        # Host networking - ports in compose are ignored
        compose: dict = {
            "services": {"signalk": {"network_mode": "host", "ports": ["9999:8888"]}}
        }
        result = generate_routing_yml(metadata, compose, "signalk-container")

        routing = yaml.safe_load(result)
        assert routing["routing"]["backend"]["port"] == 3000
        assert routing["routing"]["backend"]["type"] == "host"
