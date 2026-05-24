"""Proxy-network injection for container apps.

Routing rules themselves are generated at runtime by the reverse proxy
from `/etc/halos/routing.d/{app_id}.yml` (see ``routing.py``); this module
only attaches container services to the shared proxy network so the proxy
can reach them.
"""

import copy
from typing import Any


def _detect_host_networking(compose: dict[str, Any]) -> bool:
    """Detect if any service uses host networking.

    Args:
        compose: Parsed docker-compose.yml

    Returns:
        True if any service uses network_mode: host
    """
    services = compose.get("services", {})
    for service_config in services.values():
        if isinstance(service_config, dict):
            if service_config.get("network_mode") == "host":
                return True
    return False


def inject_traefik_network(
    compose: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Inject Traefik network into docker-compose (if routing enabled).

    This is the main integration point called by builder.py.
    Traefik labels are NOT injected here - they're generated at runtime
    by the Traefik container based on routing.yml declarations.

    Args:
        compose: docker-compose dictionary
        metadata: Package metadata dictionary

    Returns:
        Modified docker-compose with network added (if needed)
    """
    routing_config = metadata.get("routing")
    web_ui = metadata.get("web_ui")

    # Check if routing is needed
    has_routing = routing_config is not None or (web_ui and web_ui.get("enabled"))

    if not has_routing:
        return compose

    # Detect host networking
    is_host_network = _detect_host_networking(compose)

    # Inject proxy network (for non-host-networking apps)
    return inject_proxy_network(compose, is_host_network)


def inject_proxy_network(
    compose: dict[str, Any],
    is_host_network: bool,
) -> dict[str, Any]:
    """Inject halos-proxy-network into docker-compose.

    Adds the shared Traefik network to the compose file and all services
    (unless using host networking).

    Args:
        compose: Original docker-compose dictionary
        is_host_network: Whether the app uses host networking

    Returns:
        Modified docker-compose dictionary with network added
    """
    if is_host_network:
        return compose

    # Deep copy to avoid modifying original
    compose = copy.deepcopy(compose)

    # Add network definition
    if "networks" not in compose:
        compose["networks"] = {}
    compose["networks"]["halos-proxy-network"] = {"external": True}

    # Add network to all services
    services = compose.get("services", {})
    for service_config in services.values():
        if not isinstance(service_config, dict):
            continue

        # Get or create networks list for service
        service_networks = service_config.get("networks", [])

        if isinstance(service_networks, list):
            # List format - append new network
            if "halos-proxy-network" not in service_networks:
                service_networks.append("halos-proxy-network")
            service_config["networks"] = service_networks
        elif isinstance(service_networks, dict):
            # Dict format - add new network entry
            if "halos-proxy-network" not in service_networks:
                service_networks["halos-proxy-network"] = {}
            service_config["networks"] = service_networks
        else:
            # No networks defined - create list
            service_config["networks"] = ["halos-proxy-network"]

    return compose
