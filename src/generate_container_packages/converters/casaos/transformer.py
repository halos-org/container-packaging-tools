"""Metadata transformer for CasaOS to HaLOS conversion.

Transforms CasaOS application definitions into HaLOS package format,
including category mapping, field type inference, path transformation,
and package naming.
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from generate_container_packages.utils import compute_file_hash

from .models import CasaOSApp, CasaOSEnvVar, ConversionContext


class MetadataTransformer:
    """Transforms CasaOS app definitions to HaLOS format.

    Loads mapping configuration files and applies transformations:
    - Category mapping (CasaOS → Debian sections)
    - Field type inference with validation rules
    - Field grouping (network, authentication, storage, etc.)
    - Path transformation (CasaOS → HaLOS conventions)
    - Package naming (casaos-{app}-container format)
    """

    def __init__(self, mappings_dir: Path) -> None:
        """Initialize transformer with mapping configurations.

        Args:
            mappings_dir: Directory containing mapping YAML files
                (categories.yaml, field_types.yaml, paths.yaml)

        Raises:
            FileNotFoundError: If mapping directory or required files don't exist
            ValueError: If mapping files contain invalid YAML or missing required keys
        """
        self.mappings_dir = Path(mappings_dir)

        # Verify mappings directory exists
        if not self.mappings_dir.exists():
            raise FileNotFoundError(
                f"Mappings directory not found: {self.mappings_dir}\n"
                f"Expected directory with categories.yaml, field_types.yaml, and paths.yaml"
            )

        # Load mapping files with error handling
        required_files = ["categories.yaml", "field_types.yaml", "paths.yaml"]
        for filename in required_files:
            filepath = self.mappings_dir / filename
            if not filepath.exists():
                raise FileNotFoundError(
                    f"Required mapping file not found: {filepath}\n"
                    f"Expected files in {self.mappings_dir}: {', '.join(required_files)}"
                )

        try:
            with open(self.mappings_dir / "categories.yaml") as f:
                self._category_data = yaml.safe_load(f)
                if not isinstance(self._category_data, dict):
                    raise ValueError("categories.yaml must contain a dictionary")
                if "mappings" not in self._category_data:
                    raise ValueError("categories.yaml must contain 'mappings' key")

            with open(self.mappings_dir / "field_types.yaml") as f:
                self._field_type_data = yaml.safe_load(f)
                if not isinstance(self._field_type_data, dict):
                    raise ValueError("field_types.yaml must contain a dictionary")
                if "patterns" not in self._field_type_data:
                    raise ValueError("field_types.yaml must contain 'patterns' key")

            with open(self.mappings_dir / "paths.yaml") as f:
                self._path_data = yaml.safe_load(f)
                if not isinstance(self._path_data, dict):
                    raise ValueError("paths.yaml must contain a dictionary")
                if "transforms" not in self._path_data:
                    raise ValueError("paths.yaml must contain 'transforms' key")

        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML in mapping file: {e}\n"
                f"Check syntax in {self.mappings_dir}"
            ) from e

        # Pre-compile regex patterns for field type inference
        self._compiled_patterns: list[dict[str, Any]] = []
        for pattern_def in self._field_type_data["patterns"]:
            self._compiled_patterns.append(
                {
                    "regex": re.compile(pattern_def["pattern"]),
                    "type": pattern_def["type"],
                    "validation": pattern_def.get("validation", {}),
                    "group": pattern_def.get("group", "configuration"),
                }
            )

    def transform(
        self,
        casaos_app: CasaOSApp,
        context: ConversionContext,
        source_file_path: Path | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Transform CasaOS app to HaLOS format.

        This method generates dictionaries that conform to HaLOS schemas
        but does NOT perform validation. The caller is responsible for
        validating the output against PackageMetadata and ConfigSchema
        using Pydantic models.

        The returned dictionaries may be incomplete (missing required fields
        like maintainer, license, version) as these are typically added by
        the caller based on additional context not available in CasaOS metadata.

        Args:
            casaos_app: Parsed CasaOS application
            context: Conversion context for tracking warnings/errors
            source_file_path: Path to source docker-compose.yml (for hash computation)
            source_url: URL to upstream repository (for source tracking)

        Returns:
            Dictionary with keys:
                - metadata: dict for PackageMetadata (requires additional fields)
                - config: dict for ConfigSchema (should validate as-is)
                - compose: dict with cleaned docker-compose (no x-casaos)

        Note:
            Validation responsibility:
            - Caller must validate metadata dict with PackageMetadata.model_validate()
            - Caller must validate config dict with ConfigSchema.model_validate()
            - Caller should add missing required fields (maintainer, license, etc.)
        """
        # Generate package name
        package_name = self._generate_package_name(casaos_app.name)

        # Map category
        debian_section = self._map_category(casaos_app.category)

        # Collect all environment variables from all services
        all_env_vars: list[CasaOSEnvVar] = []
        for service in casaos_app.services:
            all_env_vars.extend(service.environment)

        # Transform environment variables to config fields with grouping
        config_groups = self._create_config_groups(all_env_vars)

        # Build source_metadata if source tracking parameters provided
        source_metadata = None
        if source_file_path and source_url:
            source_metadata = {
                "type": context.source_format,
                "app_id": context.app_id,
                "source_url": source_url,
                "upstream_hash": compute_file_hash(source_file_path),
                "conversion_timestamp": datetime.now(UTC).isoformat(),
            }

        # Handle description fields according to Debian conventions
        # - description: one-line synopsis (max 80 chars)
        # - long_description: extended description (multiple lines, preserved as-is)
        description = casaos_app.tagline
        long_description = casaos_app.description

        if len(description) > 80:
            # Synopsis too long - try to create meaningful short version
            # and preserve full tagline in long_description
            synopsis = self._create_synopsis(description)
            # Prepend full tagline to long_description
            if long_description:
                long_description = f"{description}\n\n{long_description}"
            else:
                long_description = description
            description = synopsis

        # Extract version from primary service Docker image
        # Use scoring system to find best matching service:
        # - Exact match gets highest score
        # - Services starting with app.id get high score
        # - Shorter names preferred (main service usually has simpler name)
        # - Avoid database services (postgres, mysql, redis, etc.)
        primary_service = None
        app_id_lower = casaos_app.id.lower()
        best_score = -1

        # Keywords that suggest a supporting/database service (not main)
        support_keywords = {"postgres", "postgresql", "mysql", "mariadb", "redis", "memcached", "mongo", "mongodb", "db", "database"}
        # Keywords that suggest main service
        main_keywords = {"server", "app", "web", "api", "frontend", "backend", "service"}

        for service in casaos_app.services:
            service_lower = service.name.lower()
            score = 0

            # Exact match: highest priority
            if service_lower == app_id_lower:
                score = 1000
            # Starts with app.id (e.g., "immich-server" for "immich")
            elif service_lower.startswith(app_id_lower + "-") or service_lower.startswith(app_id_lower + "_"):
                score = 100
                # Bonus for main keywords
                for keyword in main_keywords:
                    if keyword in service_lower:
                        score += 50
                        break
                # Penalty for support/database keywords
                for keyword in support_keywords:
                    if keyword in service_lower:
                        score -= 200  # Heavy penalty for database services
                        break
                # Prefer shorter names (main service usually simpler)
                # Subtract length as penalty (max 50 chars considered)
                score -= min(len(service.name), 50)
            # Contains app.id as word boundary
            elif app_id_lower in service_lower:
                idx = service_lower.find(app_id_lower)
                before_ok = idx == 0 or not service_lower[idx-1].isalnum()
                after_idx = idx + len(app_id_lower)
                after_ok = after_idx >= len(service_lower) or not service_lower[after_idx].isalnum()
                if before_ok and after_ok:
                    score = 50

            if score > best_score:
                best_score = score
                primary_service = service

        # Fallback to first service if no matches
        if primary_service is None and casaos_app.services:
            primary_service = casaos_app.services[0]

        # Try to extract version from primary service image
        version = None
        if primary_service:
            version = self._extract_version_from_image(primary_service.image)

        # Update source_metadata to track version extraction
        if source_metadata and version:
            source_metadata["version_source"] = "auto-extracted"
            source_metadata["docker_image"] = primary_service.image

        # Build metadata dictionary
        metadata = {
            "name": casaos_app.name,
            "package_name": package_name,
            "description": description,
            "long_description": long_description,
            "debian_section": debian_section,
            "homepage": casaos_app.homepage,
            "icon": casaos_app.icon,
            "screenshots": casaos_app.screenshots if casaos_app.screenshots else None,
            "source_metadata": source_metadata,
        }

        # Set version if extracted
        if version:
            metadata["version"] = version

        # Build config dictionary
        config = {"version": "1.0", "groups": config_groups}

        # Build compose dictionary (clean x-casaos metadata)
        compose = self._build_clean_compose(casaos_app)

        return {"metadata": metadata, "config": config, "compose": compose}

    def _map_category(self, casaos_category: str) -> str:
        """Map CasaOS category to Debian section.

        Args:
            casaos_category: CasaOS category name

        Returns:
            Debian section name (falls back to 'misc' if not found)
        """
        if not casaos_category:
            return self._category_data.get("default", "misc")

        mappings = self._category_data.get("mappings", {})
        return mappings.get(casaos_category, self._category_data.get("default", "misc"))

    def _create_synopsis(self, text: str, max_length: int = 80) -> str:
        """Create a short synopsis from a longer description.

        Attempts to intelligently shorten text to fit Debian synopsis requirements
        by extracting the first sentence or clause, or truncating at word boundary.

        Args:
            text: Original description text
            max_length: Maximum length for synopsis (default 80)

        Returns:
            Shortened synopsis that fits within max_length
        """
        if len(text) <= max_length:
            return text

        # Try to find first sentence (ending with . ! ?)
        for delimiter in [". ", "! ", "? "]:
            if delimiter in text[: max_length + 20]:
                first_sentence = text.split(delimiter)[0] + delimiter.rstrip()
                if len(first_sentence) <= max_length:
                    return first_sentence

        # Try to break at clause boundaries (comma, semicolon, dash)
        for delimiter in [", ", "; ", " - ", " – "]:
            pos = text[:max_length].rfind(delimiter)
            if pos > max_length * 0.6:  # At least 60% of target length
                return text[:pos]

        # Fall back to breaking at last complete word
        truncate_pos = text[: max_length - 3].rfind(" ")
        if truncate_pos > 0:
            return text[:truncate_pos] + "..."

        # Last resort: hard truncate
        return text[: max_length - 3] + "..."

    def _normalize_env_var_name(self, name: str) -> str:
        """Normalize environment variable name to valid shell format.

        Converts variable names to UPPER_SNAKE_CASE by:
        - Converting to uppercase
        - Replacing dots with underscores
        - Ensuring first character is uppercase letter

        Args:
            name: Original environment variable name

        Returns:
            Normalized variable name in UPPER_SNAKE_CASE format
        """
        # Replace dots and other invalid characters with underscores
        normalized = name.replace(".", "_").replace("-", "_")
        # Convert to uppercase
        normalized = normalized.upper()
        # Ensure it starts with a letter (prepend ENV_ if it starts with number)
        if normalized and not normalized[0].isalpha():
            normalized = "ENV_" + normalized
        return normalized

    def _infer_field_type(
        self, env_var: CasaOSEnvVar
    ) -> tuple[str, dict[str, Any], str]:
        """Infer HaLOS field type from environment variable.

        Args:
            env_var: CasaOS environment variable definition

        Returns:
            Tuple of (field_type, validation_rules, group_hint)
        """
        # Try pattern matching first
        for pattern_def in self._compiled_patterns:
            if pattern_def["regex"].match(env_var.name):
                return (
                    pattern_def["type"],
                    pattern_def["validation"],
                    pattern_def["group"],
                )

        # Fall back to CasaOS type hint
        defaults = self._field_type_data.get("defaults", {})
        casaos_type = env_var.type or ""
        field_type = defaults.get(casaos_type, defaults.get("fallback", "string"))

        # Determine group based on type
        if field_type == "password":
            group = "authentication"
        elif field_type == "path":
            group = "storage"
        else:
            group = "configuration"

        return field_type, {}, group

    def _extract_version_from_image(self, image_tag: str) -> str | None:
        """Extract semantic version from Docker image tag.

        Handles various version patterns found in Docker images:
        - Standard versions: image:1.2.3 → 1.2.3
        - v-prefix: image:v1.2.3 → 1.2.3
        - Pre-release: image:1.2.3-rc1 → 1.2.3~rc1 (Debian format)
        - Build suffixes: image:1.2.3-alpine → 1.2.3
        - Date versions: image:250228 → 250228
        - Digest refs: image:1.2.3@sha256:... → 1.2.3

        Pre-release versions (rc, beta, alpha, pre, dev) are converted to
        Debian format using tilde for proper version ordering:
        1.2.3~rc1 < 1.2.3~rc2 < 1.2.3

        Skips non-versioned tags:
        - :latest tags
        - Branch tags (main, master, stable, develop, dev)
        - No tag (implicit latest)
        - Non-semantic versions

        Args:
            image_tag: Full Docker image reference (e.g., "linuxserver/sonarr:4.0.15")

        Returns:
            Extracted version string or None if cannot extract/should skip

        Examples:
            >>> _extract_version_from_image("linuxserver/sonarr:4.0.15")
            "4.0.15"
            >>> _extract_version_from_image("tailscale:v1.90.8")
            "1.90.8"
            >>> _extract_version_from_image("app:1.2.3-rc1")
            "1.2.3~rc1"
            >>> _extract_version_from_image("homebridge:latest")
            None
        """
        # Remove digest reference if present (e.g., @sha256:...)
        if "@" in image_tag:
            image_tag = image_tag.split("@")[0]

        # Check if there's a tag
        if ":" not in image_tag:
            return None  # No tag = implicit :latest

        # Extract tag part (everything after last :)
        tag = image_tag.split(":")[-1]

        # Skip branch tags and latest
        skip_tags = {"latest", "main", "master", "stable", "develop", "dev", "nightly", "edge"}
        if tag.lower() in skip_tags:
            return None

        # Strip v-prefix if present
        if tag.startswith("v") and len(tag) > 1 and tag[1].isdigit():
            tag = tag[1:]

        # Handle hyphens: pre-release versions vs build suffixes
        # - Pre-release (rc, beta, alpha, pre): convert to tilde (1.2.3-rc1 → 1.2.3~rc1)
        # - Numeric suffixes: keep as-is (2024.10-1 → 2024.10-1)
        # - Build suffixes: strip (1.2.3-alpine → 1.2.3)
        if "-" in tag:
            parts = tag.split("-", 1)  # Split at first hyphen only
            base_version = parts[0]
            suffix = parts[1] if len(parts) > 1 else ""

            # Pre-release keywords (case-insensitive)
            prerelease_keywords = {"rc", "beta", "alpha", "pre", "dev"}

            # Check if suffix starts with a pre-release keyword
            suffix_lower = suffix.lower()
            is_prerelease = any(
                suffix_lower.startswith(keyword)
                for keyword in prerelease_keywords
            )

            if is_prerelease:
                # Convert hyphen to tilde for Debian pre-release ordering
                tag = f"{base_version}~{suffix}"
            elif suffix and suffix[0].isdigit():
                # Numeric suffix - keep as-is (e.g., "2024.10-1")
                tag = f"{base_version}-{suffix}"
            else:
                # Non-numeric, non-prerelease suffix - strip it (e.g., "1.2.3-alpine" → "1.2.3")
                tag = base_version

        # Validate that we have something that looks like a version
        # Must start with a digit and contain only allowed characters
        # (digits, dots, hyphens, tildes for Debian pre-release versions)
        if not tag or not tag[0].isdigit():
            return None

        # Check if tag contains at least one digit (could be date or version)
        if not any(c.isdigit() for c in tag):
            return None

        return tag

    def _create_config_groups(
        self, env_vars: list[CasaOSEnvVar]
    ) -> list[dict[str, Any]]:
        """Create config groups from environment variables.

        Groups fields by their inferred group hint.

        Args:
            env_vars: List of environment variables

        Returns:
            List of config group dictionaries
        """
        # Group fields by group hint
        groups_dict: dict[str, list[dict[str, Any]]] = {}

        for env_var in env_vars:
            field_type, validation, group_hint = self._infer_field_type(env_var)

            # Normalize variable name to valid shell format
            normalized_name = self._normalize_env_var_name(env_var.name)

            # Build field dictionary
            field = {
                "id": normalized_name,
                "label": env_var.label or env_var.name,
                "type": field_type,
                "default": env_var.default,
                "required": False,  # CasaOS doesn't specify required, default to False
                "description": env_var.description,
            }

            # Add validation rules if present
            if "min" in validation:
                field["min"] = validation["min"]
            if "max" in validation:
                field["max"] = validation["max"]

            # Add to appropriate group
            if group_hint not in groups_dict:
                groups_dict[group_hint] = []
            groups_dict[group_hint].append(field)

        # Convert to list of groups with proper structure
        group_labels = self._field_type_data.get("groups", {})
        groups = []

        for group_id, fields in groups_dict.items():
            groups.append(
                {
                    "id": group_id,
                    "label": group_labels.get(
                        group_id, group_id.replace("_", " ").title()
                    ),
                    "description": None,
                    "fields": fields,
                }
            )

        return groups

    def _transform_path(self, path: str, app_id: str) -> str:
        """Transform CasaOS path to HaLOS convention.

        Path transformation follows this order:
        1. Variable substitution ({app} and {app_id} → actual app_id)
        2. Check preserved paths (system paths like /etc, /var, etc.)
        3. Apply transformation rules (first match wins)
        4. Default behavior (prepend ${CONTAINER_DATA_ROOT})

        Note: Variables are substituted BEFORE checking preserved paths.
        This means preserved path templates cannot contain {app} variables.
        If you need templated preserved paths, add them after substitution.

        Transformation rules are evaluated in order from the mappings file.
        The first rule that matches is applied, subsequent rules are skipped.
        Order matters - more specific rules should come before general ones.

        Args:
            path: CasaOS volume path (may contain {app} or {app_id} variables)
            app_id: Application identifier for variable substitution

        Returns:
            Transformed HaLOS path

        Examples:
            >>> _transform_path("/DATA/AppData/myapp/config", "myapp")
            "${CONTAINER_DATA_ROOT}/config"

            >>> _transform_path("/etc/nginx/nginx.conf", "myapp")
            "/etc/nginx/nginx.conf"  # Preserved

            >>> _transform_path("/custom/path", "myapp")
            "${CONTAINER_DATA_ROOT}/custom/path"  # Default
        """
        # First, replace {app}, {app_id}, or $AppID variables in the incoming path
        # This allows patterns like "/DATA/AppData/{app}/" or "/DATA/AppData/$AppID" to match actual paths
        path = path.replace("{app}", app_id)
        path = path.replace("{app_id}", app_id)
        path = path.replace("$AppID", app_id)

        # Check if path should be preserved (system paths like /etc, /var, etc.)
        preserved_paths = self._path_data.get("special_cases", {}).get("preserve", [])
        for preserved in preserved_paths:
            if path.startswith(preserved):
                return path

        # Apply transformation rules in order (FIRST MATCH WINS)
        # More specific rules should be placed before general ones in paths.yaml
        transforms = self._path_data.get("transforms", [])
        for transform in transforms:
            from_pattern = transform["from"]
            to_pattern = transform["to"]

            # Also replace variables in pattern for matching
            from_pattern_with_app = (
                from_pattern.replace("{app}", app_id)
                .replace("{app_id}", app_id)
                .replace("$AppID", app_id)
            )

            # Handle exact matches and prefix matches
            if path == from_pattern_with_app:
                return to_pattern
            elif path.startswith(from_pattern_with_app):
                # Replace the prefix
                return to_pattern + path[len(from_pattern_with_app) :]

        # Default behavior: prepend CONTAINER_DATA_ROOT
        default_action = self._path_data.get("default", {}).get("action", "")
        if default_action == "prepend_data_root":
            return f"${{CONTAINER_DATA_ROOT}}{path}"

        return path

    def _generate_package_name(self, app_name: str) -> str:
        """Generate package name with casaos- prefix.

        Args:
            app_name: CasaOS application name

        Returns:
            Debian-compatible package name: casaos-{app}-container

        Raises:
            ValueError: If generated package name would be invalid
        """
        # Convert to lowercase
        name = app_name.lower()

        # Replace spaces with hyphens (preserve existing hyphens)
        name = name.replace(" ", "-")

        # Replace special characters with hyphens
        # Keep only alphanumeric, hyphens, underscores, and dots
        name = re.sub(r"[^a-z0-9._-]", "-", name)

        # Replace underscores and dots with hyphens
        name = name.replace("_", "-")
        name = name.replace(".", "-")

        # Collapse multiple consecutive hyphens
        name = re.sub(r"-+", "-", name)

        # Remove leading/trailing hyphens
        name = name.strip("-")

        # Validate the generated name
        if not name:
            raise ValueError(
                f"Cannot generate package name from empty app name: '{app_name}'"
            )

        if not name[0].isalnum():
            raise ValueError(
                f"Invalid package name generated: 'casaos-{name}-container'\n"
                f"Debian package names must start with alphanumeric character.\n"
                f"Original app name: '{app_name}'"
            )

        if len(name) < 2:
            raise ValueError(
                f"Invalid package name generated: 'casaos-{name}-container'\n"
                f"Package name too short (minimum 2 characters).\n"
                f"Original app name: '{app_name}'"
            )

        # Add prefix and suffix
        return f"casaos-{name}-container"

    def _build_clean_compose(self, casaos_app: CasaOSApp) -> dict[str, Any]:
        """Build docker-compose dictionary with x-casaos metadata removed.

        Args:
            casaos_app: CasaOS application

        Returns:
            Clean docker-compose dictionary
        """
        compose: dict[str, Any] = {
            "name": casaos_app.id,
            "services": {},
        }

        for service in casaos_app.services:
            service_def: dict[str, Any] = {
                "image": service.image,
                "restart": "no",
            }

            # Add environment variables (as dict)
            if service.environment:
                env_dict = {}
                for env_var in service.environment:
                    # Normalize variable name and use reference format: ${NORMALIZED_NAME}
                    normalized_name = self._normalize_env_var_name(env_var.name)
                    env_dict[normalized_name] = f"${{{normalized_name}}}"
                service_def["environment"] = env_dict

            # Add ports
            if service.ports:
                ports = []
                for port in service.ports:
                    port_def = {
                        "target": port.container,
                        "protocol": port.protocol or "tcp",
                    }
                    # Use variable reference if host port looks like a variable
                    if port.host is not None:
                        port_def["published"] = port.host
                    ports.append(port_def)
                service_def["ports"] = ports

            # Add volumes with transformed paths
            if service.volumes:
                volumes = []
                for volume in service.volumes:
                    # Transform host path
                    transformed_host = self._transform_path(volume.host, casaos_app.id)

                    volume_def = {
                        "type": "bind",
                        "source": transformed_host,
                        "target": volume.container,
                    }

                    # Add mode if specified
                    if volume.mode:
                        volume_def["read_only"] = volume.mode == "ro"

                    volumes.append(volume_def)
                service_def["volumes"] = volumes

            # Add command if present
            if service.command:
                service_def["command"] = service.command

            # Add entrypoint if present
            if service.entrypoint:
                service_def["entrypoint"] = service.entrypoint

            compose["services"][service.name] = service_def

        return compose
