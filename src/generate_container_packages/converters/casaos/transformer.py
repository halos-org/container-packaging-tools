"""Metadata transformer for CasaOS to HaLOS conversion.

Transforms CasaOS application definitions into HaLOS package format,
including category mapping, field type inference, path transformation,
and package naming.
"""

import re
from pathlib import Path
from typing import Any

import yaml

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
        self, casaos_app: CasaOSApp, context: ConversionContext
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

        # Build metadata dictionary
        metadata = {
            "name": casaos_app.name,
            "package_name": package_name,
            "description": casaos_app.tagline,
            "long_description": casaos_app.description,
            "debian_section": debian_section,
            "homepage": casaos_app.homepage,
            "icon": casaos_app.icon,
            "screenshots": casaos_app.screenshots if casaos_app.screenshots else None,
        }

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

            # Build field dictionary
            field = {
                "id": env_var.name,
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
        # First, replace {app} or {app_id} variables in the incoming path
        # This allows patterns like "/DATA/AppData/{app}/" to match actual paths
        path = path.replace("{app}", app_id)
        path = path.replace("{app_id}", app_id)

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
            from_pattern_with_app = from_pattern.replace("{app}", app_id).replace(
                "{app_id}", app_id
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
            }

            # Add environment variables (as dict)
            if service.environment:
                env_dict = {}
                for env_var in service.environment:
                    # Use variable reference format: ${VAR_NAME}
                    env_dict[env_var.name] = f"${{{env_var.name}}}"
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
