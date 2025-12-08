"""Homarr Docker label generation for container apps."""

from typing import Any

# Mapping from debtags to Homarr categories
TAG_TO_CATEGORY = {
    "use::communication": "Communication",
    "use::monitor": "Monitoring",
    "use::organizing": "Organization",
    "use::editing": "Productivity",
    "use::viewing": "Media",
    "use::downloading": "Downloads",
    "use::storing": "Storage",
    "use::navigation": "Navigation",
    "use::analysing": "Analytics",
    "use::configuring": "Configuration",
    "use::learning": "Education",
    "use::gameplaying": "Games",
    "interface::web": "Web",
    "works-with::network-traffic": "Network",
    "works-with::db": "Database",
    "works-with::audio": "Audio",
    "works-with::video": "Video",
    "works-with::image": "Images",
}

DEFAULT_CATEGORY = "Applications"


def find_port_env_var(default_config: dict[str, str] | None) -> str | None:
    """Find a port environment variable from default_config.

    Searches for keys containing 'PORT' (case-insensitive).
    Prefers exact match for 'PORT', then keys ending with '_PORT'.

    Args:
        default_config: Default configuration dictionary

    Returns:
        Environment variable name containing port, or None if not found
    """
    if not default_config:
        return None

    # First, look for exact match "PORT"
    for key in default_config:
        if key.upper() == "PORT":
            return key

    # Then look for keys ending with _PORT
    for key in default_config:
        if key.upper().endswith("_PORT"):
            return key

    # Finally, look for any key containing PORT
    for key in default_config:
        if "PORT" in key.upper():
            return key

    return None


def get_category_from_tags(tags: list[str]) -> str:
    """Derive Homarr category from debtags.

    Args:
        tags: List of debtags

    Returns:
        Homarr category string
    """
    for tag in tags:
        if tag in TAG_TO_CATEGORY:
            return TAG_TO_CATEGORY[tag]
    return DEFAULT_CATEGORY


def generate_homarr_labels(metadata: dict[str, Any]) -> dict[str, str]:
    """Generate Homarr Docker labels from metadata.

    Args:
        metadata: Package metadata dictionary

    Returns:
        Dictionary of Homarr labels (empty if web_ui is disabled or missing)

    The generated labels use ${HOMARR_URL} variable reference which
    is expanded at container runtime from the prestart script output.
    """
    web_ui = metadata.get("web_ui")

    # Return empty dict if web_ui is not configured or disabled
    if not web_ui or not web_ui.get("enabled", False):
        return {}

    tags = metadata.get("tags", [])
    category = get_category_from_tags(tags)

    labels = {
        "homarr.enable": "true",
        "homarr.name": metadata.get("name", metadata.get("package_name", "Unknown")),
        "homarr.url": "${HOMARR_URL}",
        "homarr.description": metadata.get("description", ""),
        "homarr.category": category,
    }

    # Add icon reference if present
    if metadata.get("icon"):
        # Icons are installed to /usr/share/pixmaps/
        package_name = metadata.get("package_name", "")
        icon = metadata.get("icon", "")
        ext = icon.split(".")[-1] if "." in icon else "png"
        labels["homarr.icon"] = f"/usr/share/pixmaps/{package_name}.{ext}"

    return labels
