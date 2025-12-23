"""Traefik label generation for container apps.

This module generates Docker labels for Traefik routing and SSO integration
based on the traefik section in metadata.yaml.
"""

import copy
from typing import Any


def generate_traefik_labels(
    metadata: dict[str, Any],
    compose: dict[str, Any],
) -> dict[str, str]:
    """Generate Traefik Docker labels from metadata.

    Args:
        metadata: Package metadata dictionary
        compose: Parsed docker-compose.yml

    Returns:
        Dictionary of Traefik labels (empty if traefik not configured)

    Raises:
        ValueError: If host networking is detected without host_port
    """
    traefik_config = metadata.get("traefik")
    web_ui = metadata.get("web_ui")
    app_id = metadata.get("app_id")

    # Default behavior: if web_ui.enabled but no traefik section,
    # create implicit forward_auth config
    if not traefik_config:
        if web_ui and web_ui.get("enabled"):
            traefik_config = {"auth": "forward_auth"}
        else:
            return {}

    # Get configuration values
    subdomain_raw = traefik_config.get("subdomain")
    subdomain: str = subdomain_raw if subdomain_raw is not None else (app_id or "")
    auth_mode = traefik_config.get("auth", "forward_auth")

    # Detect host networking
    is_host_network = _detect_host_networking(compose)
    host_port = traefik_config.get("host_port")

    # Determine the port to use
    if is_host_network:
        if host_port is None:
            # Try to infer from web_ui.port
            if web_ui and web_ui.get("port"):
                host_port = web_ui.get("port")
            else:
                raise ValueError(
                    f"App '{app_id}' uses host networking but no host_port specified. "
                    "Add traefik.host_port to metadata.yaml or ensure web_ui.port is set."
                )
    else:
        # For bridge networking, get port from web_ui
        port = web_ui.get("port", 80) if web_ui else 80

    # Build labels
    labels: dict[str, str] = {
        "traefik.enable": "true",
        f"traefik.http.routers.{app_id}.rule": _build_host_rule(subdomain),
        f"traefik.http.routers.{app_id}.entrypoints": "web,websecure",
        "halos.subdomain": subdomain,
    }

    # Add middleware based on auth mode
    if auth_mode == "forward_auth":
        forward_auth_config = traefik_config.get("forward_auth") or {}
        headers = (
            forward_auth_config.get("headers")
            if isinstance(forward_auth_config, dict)
            else None
        )
        if headers:
            # Per-app middleware with custom headers
            labels[f"traefik.http.routers.{app_id}.middlewares"] = (
                f"authelia-{app_id}@file"
            )
        else:
            # Default Authelia middleware
            labels[f"traefik.http.routers.{app_id}.middlewares"] = "authelia@file"
    # No middleware for oidc or none auth modes

    # Backend configuration
    if is_host_network:
        labels[f"traefik.http.services.{app_id}.loadbalancer.server.url"] = (
            f"http://host.docker.internal:{host_port}"
        )
    else:
        labels[f"traefik.http.services.{app_id}.loadbalancer.server.port"] = str(port)

    return labels


def _build_host_rule(subdomain: str) -> str:
    """Build Traefik Host rule for the subdomain.

    Args:
        subdomain: Subdomain for routing (empty string for root domain)

    Returns:
        Traefik Host rule string
    """
    if subdomain:
        return f"Host(`{subdomain}.${{HALOS_DOMAIN}}`)"
    else:
        # Empty subdomain means root domain
        return "Host(`${HALOS_DOMAIN}`)"


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


def inject_traefik_labels(
    compose: dict[str, Any],
    metadata: dict[str, Any],
    original_compose: dict[str, Any],
) -> dict[str, Any]:
    """Inject Traefik labels and network into docker-compose.

    This is the main integration point called by builder.py.

    Args:
        compose: docker-compose dictionary (may already have Homarr labels)
        metadata: Package metadata dictionary
        original_compose: Original docker-compose for host networking detection

    Returns:
        Modified docker-compose with Traefik labels and network added
    """
    # Generate traefik labels
    traefik_labels = generate_traefik_labels(metadata, original_compose)

    if not traefik_labels:
        return compose

    # Deep copy to avoid modifying original
    compose = copy.deepcopy(compose)

    # Detect host networking
    is_host_network = _detect_host_networking(original_compose)

    # Inject labels into the first/primary service
    services = compose.get("services", {})
    for service_config in services.values():
        if not isinstance(service_config, dict):
            continue

        # Get or create labels section
        existing_labels = service_config.get("labels", {})

        # Convert list format to dict if needed
        if isinstance(existing_labels, list):
            label_dict = {}
            for label in existing_labels:
                if "=" in label:
                    key, value = label.split("=", 1)
                    label_dict[key] = value
                else:
                    label_dict[label] = ""
            existing_labels = label_dict

        # Merge Traefik labels (don't overwrite existing)
        for key, value in traefik_labels.items():
            if key not in existing_labels:
                existing_labels[key] = value

        service_config["labels"] = existing_labels
        break  # Only add to first/primary service

    # Inject proxy network (for non-host-networking apps)
    compose = inject_proxy_network(compose, is_host_network)

    return compose


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
