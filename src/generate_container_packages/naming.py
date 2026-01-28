"""Package naming utilities for container applications.

This module provides functions for computing package names from components,
deriving app_id from directory names, and expanding dependency references.

Package naming follows the pattern: {prefix}-{app_id}-{suffix}
where prefix is optional and suffix defaults to "container".
"""

import re
import unicodedata


def compute_package_name(
    app_id: str,
    prefix: str | None = None,
    suffix: str = "container",
) -> str:
    """Compute full package name from components.

    The resulting name follows the pattern: {prefix}-{app_id}-{suffix}
    Empty or None values for prefix/suffix are omitted from the result.

    Args:
        app_id: Base application identifier (e.g., "signalk-server")
        prefix: Optional source prefix (e.g., "marine", "halos", "casaos").
            Both None and empty string result in no prefix.
        suffix: Package suffix (default: "container").
            Empty string results in no suffix.

    Returns:
        Full package name (e.g., "marine-signalk-server-container")

    Examples:
        >>> compute_package_name("grafana", prefix="marine")
        "marine-grafana-container"
        >>> compute_package_name("homarr", prefix=None)
        "homarr-container"
        >>> compute_package_name("homarr", prefix="")
        "homarr-container"
        >>> compute_package_name("myapp", prefix="halos", suffix="")
        "halos-myapp"
    """
    parts = []

    if prefix:
        parts.append(prefix)

    parts.append(app_id)

    if suffix:
        parts.append(suffix)

    return "-".join(parts)


def derive_app_id(directory_name: str) -> str:
    """Derive app_id from directory name.

    Normalizes the directory name to a valid app_id by:
    - Converting to lowercase
    - Replacing spaces, underscores, and dots with hyphens
    - Removing or converting special characters
    - Collapsing consecutive hyphens
    - Stripping leading/trailing hyphens

    Args:
        directory_name: The directory name to normalize

    Returns:
        Normalized app_id suitable for use in package names

    Raises:
        ValueError: If the result would be empty

    Examples:
        >>> derive_app_id("SignalK")
        "signalk"
        >>> derive_app_id("signal_k_server")
        "signal-k-server"
        >>> derive_app_id("My Cool App")
        "my-cool-app"
    """
    if not directory_name:
        raise ValueError("Cannot derive app_id from empty directory name")

    # Normalize unicode characters (convert accented chars to ASCII equivalents)
    normalized = unicodedata.normalize("NFKD", directory_name)
    # Remove non-ASCII characters after normalization
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    result = ascii_only.lower()

    # Replace spaces, underscores, and dots with hyphens
    result = result.replace(" ", "-")
    result = result.replace("_", "-")
    result = result.replace(".", "-")

    # Replace any remaining non-alphanumeric characters (except hyphens) with hyphens
    result = re.sub(r"[^a-z0-9-]", "-", result)

    # Collapse consecutive hyphens
    result = re.sub(r"-+", "-", result)

    # Strip leading/trailing hyphens
    result = result.strip("-")

    if not result:
        raise ValueError(
            f"Cannot derive app_id from '{directory_name}': "
            "result would be empty after normalization"
        )

    return result


def expand_dependency(dep: str, prefix: str | None = None) -> str:
    """Expand a single dependency reference.

    Dependencies starting with @ are expanded to full package names using
    the current prefix. Other dependencies are returned unchanged.

    Args:
        dep: Dependency string (e.g., "@influxdb" or "docker.io (>= 20.10)")
        prefix: Optional prefix for @ references. If None or empty string,
            the expanded name will have no prefix (e.g., "influxdb-container").

    Returns:
        Expanded dependency string

    Raises:
        ValueError: If @ is followed by empty string

    Examples:
        >>> expand_dependency("@influxdb", prefix="marine")
        "marine-influxdb-container"
        >>> expand_dependency("@influxdb", prefix=None)
        "influxdb-container"
        >>> expand_dependency("docker.io (>= 20.10)", prefix="marine")
        "docker.io (>= 20.10)"
        >>> expand_dependency("casaos-redis-container", prefix="marine")
        "casaos-redis-container"
    """
    if not dep.startswith("@"):
        # Not a same-store reference, return unchanged
        return dep

    # Extract the app_id after @
    app_id = dep[1:]

    if not app_id:
        raise ValueError("Cannot expand '@' without an app_id")

    # Expand to full package name with current prefix
    return compute_package_name(app_id, prefix=prefix)


def expand_dependencies(
    deps: list[str] | None,
    prefix: str | None = None,
) -> list[str] | None:
    """Expand a list of dependency references.

    Args:
        deps: List of dependency strings, or None
        prefix: Optional prefix for @ references

    Returns:
        List of expanded dependency strings, or None if input was None

    Examples:
        >>> expand_dependencies(["docker.io", "@influxdb"], prefix="marine")
        ["docker.io", "marine-influxdb-container"]
    """
    if deps is None:
        return None

    return [expand_dependency(dep, prefix=prefix) for dep in deps]
