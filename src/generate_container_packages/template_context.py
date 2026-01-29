"""Template context builder for Jinja2 rendering."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generate_container_packages.loader import AppDefinition


class VolumeOwnershipError(Exception):
    """Raised when volume ownership cannot be determined due to invalid user field."""


@dataclass
class VolumeInfo:
    """Information about a bind mount volume including ownership."""

    path: str
    uid: int | None
    gid: int | None


def _parse_service_user(user: str | None) -> tuple[int, int | None] | None:
    """Parse the user field from docker compose config.

    Args:
        user: User field value (e.g., "1000:1000", "472:0", "1000", None, "")

    Returns:
        Tuple of (uid, gid) where gid may be None if not specified,
        or None if user is empty/None (meaning root)

    Raises:
        VolumeOwnershipError: If user field is malformed (e.g., ":", ":1000", "1000:")
            indicating undefined environment variables
    """
    if user is None or user == "":
        return None

    # Check for malformed user field (undefined env vars)
    if ":" in user:
        parts = user.split(":", 1)
        uid_str, gid_str = parts[0], parts[1]

        # Check for empty parts (indicates undefined env vars)
        if uid_str == "" or gid_str == "":
            raise VolumeOwnershipError(
                f"user field '{user}' contains undefined environment variables. "
                "Ensure PUID/PGID are defined in default_config."
            )

        try:
            uid = int(uid_str)
            gid = int(gid_str)
            return (uid, gid)
        except ValueError as e:
            raise VolumeOwnershipError(
                f"user field '{user}' contains non-numeric values"
            ) from e
    else:
        # UID only, no GID
        try:
            uid = int(user)
            return (uid, None)
        except ValueError as e:
            raise VolumeOwnershipError(
                f"user field '{user}' is not a valid numeric UID"
            ) from e


def _substitute_env_vars(value: str, env_vars: dict[str, str]) -> str:
    """Substitute environment variables in a string.

    Handles both ${VAR} and $VAR syntax, with optional default values ${VAR:-default}.

    Args:
        value: String potentially containing env var references
        env_vars: Dictionary of environment variable values

    Returns:
        String with env vars substituted
    """

    def replace_var(match: re.Match[str]) -> str:
        # Handle ${VAR:-default} or ${VAR}
        var_expr = match.group(1) or match.group(2)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
        else:
            var_name = var_expr
            default = ""
        return env_vars.get(var_name, default)

    # Match ${VAR:-default}, ${VAR}, or $VAR
    pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
    return re.sub(pattern, replace_var, value)


def _extract_volume_ownership(
    compose_config: dict[str, Any], default_config: dict[str, str] | None = None
) -> list[VolumeInfo]:
    """Extract volume paths with their ownership from compose config.

    This function parses the docker-compose services and extracts bind mount paths
    along with their owning UID:GID based on each service's `user` field.
    Environment variables in the user field are resolved using default_config.

    Args:
        compose_config: Parsed docker-compose.yml contents
        default_config: Default environment variables for substitution

    Returns:
        List of VolumeInfo objects with path and ownership (uid/gid may be None for root)

    Raises:
        VolumeOwnershipError: If a service has a malformed user field
    """
    volumes: list[VolumeInfo] = []
    seen_paths: set[str] = set()
    env_vars = default_config or {}

    services = compose_config.get("services", {})

    for _service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            continue

        # Parse user field for this service, resolving any env vars
        user_field = service_config.get("user")
        if user_field and isinstance(user_field, str):
            user_field = _substitute_env_vars(user_field, env_vars)
        ownership = _parse_service_user(user_field)

        if ownership is not None:
            uid, gid = ownership
        else:
            uid, gid = None, None

        # Extract volumes for this service
        service_volumes = service_config.get("volumes", [])

        for volume in service_volumes:
            source = _extract_volume_source(volume)
            if source and _is_bindable_path(source) and source not in seen_paths:
                seen_paths.add(source)
                volumes.append(VolumeInfo(path=source, uid=uid, gid=gid))

    return volumes


def _extract_volume_source(volume: dict[str, Any] | str) -> str | None:
    """Extract the source path from a volume specification.

    Args:
        volume: Volume specification (dict for long format, str for short format)

    Returns:
        Source path or None if not extractable
    """
    if isinstance(volume, dict):
        # Long format: {type: bind, source: ..., target: ...}
        if volume.get("type") == "bind":
            return volume.get("source")
        return None
    elif isinstance(volume, str):
        # Short format: "source:target" or "source:target:ro"
        parts = volume.split(":")
        if len(parts) >= 2:
            return parts[0]
    return None


def build_context(app_def: AppDefinition) -> dict[str, Any]:
    """Build template context from app definition.

    Args:
        app_def: Application definition with all parsed data

    Returns:
        Dictionary containing all template variables

    The context structure follows the format expected by all Jinja2 templates,
    with properly formatted strings for Debian packaging requirements.
    """
    metadata = app_def.metadata
    package_name = metadata["package_name"]

    web_ui = metadata.get("web_ui", {})
    has_web_ui = web_ui.get("enabled", False) if web_ui else False

    # Get routing config for SSO integration
    routing = metadata.get("routing")

    # Determine auth mode from routing config
    auth_mode = "forward_auth"  # Default
    if routing:
        auth_config = routing.get("auth")
        if isinstance(auth_config, dict):
            auth_mode = auth_config.get("mode", "forward_auth")
        elif isinstance(auth_config, str):
            auth_mode = auth_config
    is_oidc_app = auth_mode == "oidc"

    # Check if custom forward auth headers are configured
    has_custom_forward_auth = False
    if routing:
        auth_config = routing.get("auth")
        if isinstance(auth_config, dict):
            fa_config = auth_config.get("forward_auth", {})
            has_custom_forward_auth = bool(fa_config.get("headers"))
        else:
            fa_config = routing.get("forward_auth", {})
            has_custom_forward_auth = (
                bool(fa_config.get("headers")) if fa_config else False
            )

    # Check if routing.yml should be generated
    has_routing = routing is not None or has_web_ui

    context = {
        "package": _build_package_context(metadata),
        "service": _build_service_context(package_name, metadata, app_def.compose),
        "paths": _build_paths(package_name),
        "web_ui": web_ui,
        "has_web_ui": has_web_ui,
        "default_config": metadata.get("default_config", {}),
        "timestamp": app_def.timestamp,
        "timestamp_rfc2822": app_def.timestamp_rfc2822,
        "date_only": app_def.date_only,
        "tool_version": app_def.tool_version,
        "has_icon": app_def.icon_path is not None,
        "icon_extension": _get_icon_extension(app_def.icon_path),
        "has_screenshots": len(app_def.screenshot_paths) > 0,
        "screenshot_count": len(app_def.screenshot_paths),
        "has_assets": len(app_def.asset_files) > 0,
        "asset_files": [
            {"path": str(f.path), "executable": f.executable}
            for f in app_def.asset_files
        ],
        # Default data files (copied to data volume on first install)
        "has_default_data": len(app_def.default_data_files) > 0,
        "default_data_files": [
            {"path": str(f.path), "executable": f.executable}
            for f in app_def.default_data_files
        ],
        # SSO configuration
        "is_oidc_app": is_oidc_app,
        "has_custom_forward_auth": has_custom_forward_auth,
        # Routing configuration
        "routing": routing,
        "has_routing": has_routing,
        # System binaries to install to /usr/bin/
        "system_bin": metadata.get("system_bin", []) or [],
        "has_system_bin": bool(metadata.get("system_bin")),
        # File watchers for systemd path units
        "file_watchers": _build_file_watchers_context(metadata.get("file_watchers")),
        "has_file_watchers": bool(metadata.get("file_watchers")),
    }

    return context


def _build_file_watchers_context(
    file_watchers: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Build file watchers context for templates.

    Converts file_watchers from metadata format to template-friendly format.

    Args:
        file_watchers: List of file watcher configurations from metadata

    Returns:
        List of file watcher dicts ready for template rendering
    """
    if not file_watchers:
        return []

    result = []
    for watcher in file_watchers:
        # Convert nested on_change to flat structure for easier template access
        on_change = watcher.get("on_change", {})
        result.append(
            {
                "name": watcher["name"],
                "watch_path": watcher["watch_path"],
                "watch_type": watcher.get("watch_type", "directory_modified"),
                "restart_service": on_change.get("restart_service", False),
                "script": on_change.get("script"),
            }
        )
    return result


def _build_package_context(metadata: dict[str, Any]) -> dict[str, Any]:
    """Build package-level context from metadata.

    Args:
        metadata: Parsed metadata.yaml contents

    Returns:
        Dictionary with package metadata formatted for Debian control files
    """
    # app_id may not be present in test fixtures, derive from package_name if needed
    app_id = metadata.get("app_id")
    if app_id is None:
        package_name = metadata["package_name"]
        # Remove -container suffix if present
        if package_name.endswith("-container"):
            app_id = package_name[:-10]
        else:
            app_id = package_name

    return {
        "name": metadata["package_name"],
        "app_id": app_id,
        "version": metadata["version"],
        "architecture": metadata["architecture"],
        "section": metadata["debian_section"],
        "description": metadata["description"],
        "long_description": format_long_description(
            metadata.get("long_description", "")
        ),
        "homepage": metadata.get("homepage", ""),
        "maintainer": metadata["maintainer"],
        "license": metadata["license"],
        "tags": format_dependencies(metadata.get("tags", [])),
        "depends": format_dependencies(metadata.get("depends", [])),
        "recommends": format_dependencies(metadata.get("recommends", [])),
        "suggests": format_dependencies(metadata.get("suggests", [])),
        "provides": format_dependencies(metadata.get("provides", [])),
        "conflicts": format_dependencies(metadata.get("conflicts", [])),
        # Additional fields for templates
        "human_name": metadata["name"],
        "upstream_version": metadata.get("upstream_version", metadata["version"]),
    }


def _build_service_context(
    package_name: str, metadata: dict[str, Any], compose: dict[str, Any]
) -> dict[str, Any]:
    """Build systemd service context.

    Args:
        package_name: Debian package name
        metadata: Parsed metadata.yaml contents
        compose: Parsed docker-compose.yml contents

    Returns:
        Dictionary with systemd service configuration
    """
    default_config = metadata.get("default_config", {})
    return {
        "name": f"{package_name}.service",
        "description": f"{metadata['name']} Container",
        "working_directory": f"/var/lib/container-apps/{package_name}",
        "env_defaults_file": f"/etc/container-apps/{package_name}/env.defaults",
        "env_file": f"/etc/container-apps/{package_name}/env",
        "runtime_env_file": f"/run/container-apps/{package_name}/runtime.env",
        "volume_directories": _extract_volume_ownership(compose, default_config),
    }


def _extract_volume_directories(compose: dict[str, Any]) -> list[str]:
    """Extract volume source directories from docker-compose.yml.

    Parse the docker-compose services and extract bind mount source paths that
    should be created before starting the container. Only extracts paths that:
    1. Are bind mounts (not named volumes)
    2. Are absolute paths or contain allowed environment variables
    3. Don't reference system paths (like /dev, /sys, etc.)
    4. Don't contain path traversal attempts (..)

    Args:
        compose: Parsed docker-compose.yml contents

    Returns:
        Deduplicated list of volume source paths (may contain env var references)
        Empty list if no volumes or all are named volumes
    """
    directories = []

    # Get all services from compose file
    services = compose.get("services", {})

    for _service_name, service_config in services.items():
        volumes = service_config.get("volumes", [])

        for volume in volumes:
            # Handle different volume formats
            if isinstance(volume, dict):
                # Long format: {source: ..., target: ..., type: bind}
                if volume.get("type") == "bind":
                    source = volume.get("source", "")
                    if source and _is_bindable_path(source):
                        directories.append(source)
            elif isinstance(volume, str):
                # Short format: "source:target" or "source:target:ro"
                parts = volume.split(":")
                if len(parts) >= 2:
                    source = parts[0]
                    if source and _is_bindable_path(source):
                        directories.append(source)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for directory in directories:
        if directory not in seen:
            seen.add(directory)
            deduplicated.append(directory)

    return deduplicated


def _is_bindable_path(path: str) -> bool:
    """Check if a path should have its directory auto-created.

    Validates that the path is safe to create as a bind mount directory:
    1. Must be an absolute path or contain allowed environment variables
    2. Must not be a named volume (no slashes = named volume)
    3. Must not reference system paths (/dev, /sys, /proc, /run, /var/run, /tmp)
    4. Must not contain path traversal attempts (..)
    5. Environment variables must be from an allowed list for security
    6. Must not look like a file path (ending with common config file extensions)

    Args:
        path: Volume source path (may contain env vars like ${CONTAINER_DATA_ROOT})

    Returns:
        True if path should be created, False otherwise

    Examples:
        >>> _is_bindable_path("${CONTAINER_DATA_ROOT}/config")
        True
        >>> _is_bindable_path("/opt/myapp/data")
        True
        >>> _is_bindable_path("my-volume")
        False
        >>> _is_bindable_path("/dev/sda")
        False
        >>> _is_bindable_path("../etc/passwd")
        False
        >>> _is_bindable_path("${CONTAINER_DATA_ROOT}/nginx.conf")
        False
    """
    # Skip named volumes (no slashes means it's a named volume)
    if "/" not in path:
        return False

    # Prevent path traversal attacks
    if ".." in path:
        return False

    # Skip file paths - these should not have directories created
    # Common config file extensions that indicate a file mount, not a directory
    file_extensions = (
        ".conf",
        ".config",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".txt",
        ".ini",
        ".properties",
        ".toml",
        ".env",
        ".cfg",
        ".sock",
        ".socket",
        ".pid",
        ".log",
    )
    # Check if path ends with a file extension (case-insensitive)
    # Extract the basename (last path component) to check for extensions
    basename = path.rsplit("/", 1)[-1].lower()
    for ext in file_extensions:
        # Only match if there's a non-dot character before the extension
        # This allows hidden directories like ".config" but blocks files like "nginx.conf"
        if (
            basename.endswith(ext)
            and len(basename) > len(ext)
            and basename[-len(ext) - 1] != "."
        ):
            return False

    # Skip system paths that should never be created
    # Note: /var/run is a symlink to /run on systemd systems
    system_prefixes = ("/dev", "/sys", "/proc", "/run", "/var/run", "/tmp")
    for prefix in system_prefixes:
        if path.startswith(prefix):
            return False

    # If path contains environment variables, validate they're allowed
    if "$" in path:
        # Only allow specific safe environment variables
        allowed_env_vars = (
            "${CONTAINER_DATA_ROOT}",
            "${HOME}",
            "${USER}",
            "$CONTAINER_DATA_ROOT",
            "$HOME",
            "$USER",
        )
        # Check if path starts with or contains any allowed env var
        has_allowed_var = any(allowed_var in path for allowed_var in allowed_env_vars)
        if not has_allowed_var:
            # Reject paths with unknown/potentially dangerous env vars
            return False
        return True

    # Allow all other absolute paths (like /opt/myapp, /home/user/media, etc)
    return path.startswith("/")


def _build_paths(package_name: str) -> dict[str, str]:
    """Build standard installation paths.

    Args:
        package_name: Debian package name

    Returns:
        Dictionary with standard paths for package installation
    """
    return {
        "lib": f"/var/lib/container-apps/{package_name}",
        "etc": f"/etc/container-apps/{package_name}",
        "systemd": "/etc/systemd/system",
        "pixmaps": "/usr/share/pixmaps",
        "metainfo": "/usr/share/metainfo",
        "doc": f"/usr/share/doc/{package_name}",
    }


def _get_icon_extension(icon_path: Path | None) -> str:
    """Get icon file extension.

    Args:
        icon_path: Path to icon file (or None)

    Returns:
        File extension (e.g., 'svg', 'png') or empty string if no icon
    """
    if icon_path is None:
        return ""
    return icon_path.suffix.lstrip(".")


def format_long_description(text: str) -> str:
    """Format long description for Debian control file.

    Debian control file format requires:
    - First line is short description (handled separately in control template)
    - Subsequent lines must start with a space
    - Empty lines must be represented as a single space and period " ."

    Args:
        text: Long description text (may contain newlines)

    Returns:
        Formatted text with proper Debian control file formatting
    """
    if not text:
        return ""

    lines = text.strip().split("\n")
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if line:
            # Non-empty line: add leading space
            formatted_lines.append(f" {line}")
        else:
            # Empty line: use " ." notation
            formatted_lines.append(" .")

    return "\n".join(formatted_lines)


def format_dependencies(deps: list[str] | None) -> str:
    """Format dependency list for Debian control file.

    Args:
        deps: List of dependency package names

    Returns:
        Comma-separated dependency string, or empty string if no dependencies
    """
    if not deps:
        return ""
    return ", ".join(deps)
