"""Init injection for container apps.

Injects `init: true` into all docker-compose services so Docker uses
tini as PID 1. This ensures proper SIGTERM forwarding to container
processes, preventing the 10-second SIGKILL timeout on shutdown.
"""

import copy
from typing import Any


def inject_init(compose: dict[str, Any]) -> dict[str, Any]:
    """Inject init: true into all docker-compose services.

    Args:
        compose: Original docker-compose dictionary

    Returns:
        Modified docker-compose dictionary with init: true added
    """
    compose = copy.deepcopy(compose)

    services = compose.get("services", {})
    for service_config in services.values():
        if not isinstance(service_config, dict):
            continue
        if "init" not in service_config:
            service_config["init"] = True

    return compose
