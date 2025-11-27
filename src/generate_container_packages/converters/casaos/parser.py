"""Parser for CasaOS docker-compose.yml files with x-casaos metadata."""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from generate_container_packages.converters.casaos.models import (
    CasaOSApp,
    CasaOSEnvVar,
    CasaOSPort,
    CasaOSService,
    CasaOSVolume,
)
from generate_container_packages.converters.exceptions import (
    ValidationError as ConverterValidationError,
)

logger = logging.getLogger(__name__)


class CasaOSParser:
    """Parser for CasaOS application definitions.

    Parses docker-compose.yml files with x-casaos metadata extensions
    and converts them into CasaOSApp model instances.

    Attributes:
        warnings: List of non-fatal warnings encountered during parsing
    """

    def __init__(self):
        """Initialize parser."""
        self.warnings: list[str] = []
        self._current_file: Path | None = None

    def parse_from_file(self, compose_file: Path) -> CasaOSApp:
        """Parse a CasaOS app from a docker-compose.yml file.

        Args:
            compose_file: Path to the docker-compose.yml file

        Returns:
            CasaOSApp model instance

        Raises:
            FileNotFoundError: If the compose file doesn't exist
            ConverterValidationError: If the file format is invalid
        """
        if not compose_file.exists():
            raise FileNotFoundError(f"Compose file not found: {compose_file}")

        # Track file path for better error messages
        self._current_file = compose_file
        self.warnings.clear()  # Reset warnings for new parse

        yaml_content = compose_file.read_text()
        try:
            return self.parse_from_string(yaml_content)
        finally:
            self._current_file = None

    def _add_warning(self, message: str):
        """Add a warning with optional file context.

        Args:
            message: Warning message
        """
        if self._current_file:
            full_message = f"{self._current_file}: {message}"
        else:
            full_message = message
        self.warnings.append(full_message)
        logger.warning(full_message)

    def _validate_string_list(self, value: Any, context: str) -> list[str] | None:
        """Validate and normalize a value to a list of strings.

        Args:
            value: Value to validate (can be str, list, or None)
            context: Context description for error messages

        Returns:
            List of strings, or None if value is None
        """
        if value is None:
            return None

        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            # Validate all items are strings
            result = []
            for i, item in enumerate(value):
                if not isinstance(item, str):
                    self._add_warning(
                        f"Non-string item at index {i} in {context}: {type(item).__name__}. "
                        f"Converting to string."
                    )
                result.append(str(item))
            return result

        # Unexpected type
        self._add_warning(
            f"Unexpected type for {context}: {type(value).__name__}. "
            f"Expected string or list. Converting to string."
        )
        return [str(value)]

    def _error_context(self, message: str) -> str:
        """Add file context to error message.

        Args:
            message: Error message

        Returns:
            Error message with file context if available
        """
        if self._current_file:
            return f"{message} in {self._current_file}"
        return message

    def parse_from_string(self, yaml_content: str) -> CasaOSApp:
        """Parse a CasaOS app from YAML string content.

        Args:
            yaml_content: Docker compose YAML content as string

        Returns:
            CasaOSApp model instance

        Raises:
            ConverterValidationError: If the YAML is invalid or missing required fields
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ConverterValidationError(
                self._error_context(f"Invalid YAML syntax: {e}")
            ) from e

        if not isinstance(data, dict):
            raise ConverterValidationError(
                self._error_context("Docker compose file must be a YAML dictionary")
            )

        return self._parse_compose_data(data)

    def _parse_compose_data(self, data: dict[str, Any]) -> CasaOSApp:
        """Parse compose data dictionary into CasaOSApp.

        Args:
            data: Parsed YAML data as dictionary

        Returns:
            CasaOSApp model instance

        Raises:
            ConverterValidationError: If required fields are missing or invalid
        """
        # Extract app name from 'name' field
        app_name = data.get("name")
        if not app_name:
            raise ConverterValidationError(
                self._error_context("Missing required 'name' field")
            )

        # Extract x-casaos metadata
        x_casaos = data.get("x-casaos")
        if not x_casaos:
            raise ConverterValidationError(
                self._error_context("Missing required 'x-casaos' metadata")
            )

        # Extract services
        services_data = data.get("services", {})
        if not services_data:
            raise ConverterValidationError(
                self._error_context("Missing or empty 'services'")
            )

        # Parse services
        services = []
        for service_name, service_config in services_data.items():
            service = self._parse_service(service_name, service_config)
            services.append(service)

        # Build CasaOSApp
        try:
            app = CasaOSApp(
                id=app_name,
                name=app_name,
                tagline=self._extract_multilingual(x_casaos.get("tagline", "")),
                description=self._extract_multilingual(x_casaos.get("description", "")),
                category=x_casaos.get("category", ""),
                developer=x_casaos.get("developer"),
                homepage=x_casaos.get("homepage"),
                icon=x_casaos.get("icon"),
                screenshots=x_casaos.get("screenshot_link", []),
                tags=x_casaos.get("tags", []),
                services=services,
            )
            return app
        except ValidationError as e:
            raise ConverterValidationError(f"Invalid CasaOS app data: {e}") from e

    def _parse_service(
        self, service_name: str, service_config: dict[str, Any]
    ) -> CasaOSService:
        """Parse a single service configuration.

        Args:
            service_name: Name of the service
            service_config: Service configuration dictionary

        Returns:
            CasaOSService model instance
        """
        # Extract basic service info
        image = service_config.get("image", "")

        # Extract service-level x-casaos metadata
        service_x_casaos = service_config.get("x-casaos", {})

        # Parse environment variables
        env_vars = self._parse_env_vars(
            service_config.get("environment", {}), service_x_casaos.get("envs", [])
        )

        # Build set of defined environment variables for validation
        env_var_names = {env.name for env in env_vars}

        # Parse ports
        ports = self._parse_ports(
            service_config.get("ports", []),
            service_x_casaos.get("ports", []),
            env_var_names,
        )

        # Parse volumes
        volumes = self._parse_volumes(
            service_config.get("volumes", []),
            service_x_casaos.get("volumes", []),
            env_var_names,
        )

        # Parse command and entrypoint with validation
        command = self._validate_string_list(
            service_config.get("command"), f"command in service '{service_name}'"
        )

        entrypoint = self._validate_string_list(
            service_config.get("entrypoint"), f"entrypoint in service '{service_name}'"
        )

        return CasaOSService(
            name=service_name,
            image=image,
            environment=env_vars,
            ports=ports,
            volumes=volumes,
            command=command,
            entrypoint=entrypoint,
        )

    def _parse_env_vars(
        self, env_config: dict[str, Any] | list[str], env_metadata: list[dict[str, Any]]
    ) -> list[CasaOSEnvVar]:
        """Parse environment variables with their metadata.

        Args:
            env_config: Environment section from compose (dict or list)
            env_metadata: Environment metadata from x-casaos

        Returns:
            List of CasaOSEnvVar instances
        """
        env_vars = []

        # Convert env_config to dict if it's a list
        if isinstance(env_config, list):
            env_dict = {}
            for item in env_config:
                if isinstance(item, str) and "=" in item:
                    key, value = item.split("=", 1)
                    env_dict[key] = value
                elif isinstance(item, str):
                    env_dict[item] = ""
        else:
            env_dict = env_config

        # Build metadata lookup
        metadata_lookup = {
            item.get("container"): item
            for item in env_metadata
            if item.get("container")
        }

        # Create CasaOSEnvVar for each environment variable
        for name, value in env_dict.items():
            metadata = metadata_lookup.get(name, {})
            env_var = CasaOSEnvVar(
                name=name,
                default=str(value) if value is not None else "",
                label=metadata.get("label"),
                description=self._extract_multilingual(metadata.get("description")),
                type=metadata.get("type"),
            )
            env_vars.append(env_var)

        return env_vars

    def _parse_ports(
        self,
        ports_config: list[Any],
        ports_metadata: list[dict[str, Any]],
        env_var_names: set[str],
    ) -> list[CasaOSPort]:
        """Parse port mappings with their metadata.

        Args:
            ports_config: Ports section from compose
            ports_metadata: Ports metadata from x-casaos
            env_var_names: Set of defined environment variable names for validation

        Returns:
            List of CasaOSPort instances
        """
        ports = []

        # Build metadata lookup by container port
        metadata_lookup = {}
        for item in ports_metadata:
            container_port = item.get("container")
            if container_port:
                # Convert to int for lookup
                try:
                    port_num = int(container_port)
                    metadata_lookup[port_num] = item
                except (ValueError, TypeError):
                    self._add_warning(
                        f"Failed to convert port metadata container value to int: {container_port}"
                    )

        # Parse each port mapping
        for port_config in ports_config:
            container_port = None
            host_port = None
            protocol = None

            if isinstance(port_config, str):
                # String format: "host:container" or "host:container/protocol"
                parts = port_config.split(":")
                if len(parts) == 2:
                    host_str, container_str = parts
                    # Handle protocol suffix
                    if "/" in container_str:
                        container_str, protocol = container_str.split("/")
                    try:
                        # Handle variable references
                        if (
                            host_str
                            and host_str.startswith("${")
                            and host_str.endswith("}")
                        ):
                            var_name = host_str[2:-1]
                            if var_name not in env_var_names:
                                self._add_warning(
                                    f"Port references undefined variable: {var_name}"
                                )
                            host_port = None
                        elif host_str:
                            host_port = int(host_str)

                        if container_str.startswith("${") and container_str.endswith(
                            "}"
                        ):
                            var_name = container_str[2:-1]
                            if var_name not in env_var_names:
                                self._add_warning(
                                    f"Port references undefined variable: {var_name}"
                                )
                            container_port = None
                        else:
                            container_port = int(container_str)
                    except ValueError as e:
                        self._add_warning(
                            f"Failed to parse port mapping '{port_config}': {e}"
                        )
            elif isinstance(port_config, dict):
                # Dict format: {target: X, published: Y, protocol: Z}
                try:
                    container_port = int(port_config.get("target", 0))
                except (ValueError, TypeError) as e:
                    self._add_warning(
                        f"Failed to parse port target: {port_config.get('target')} - {e}"
                    )

                published = port_config.get("published")
                if published:
                    pub_str = str(published)
                    if pub_str.startswith("${") and pub_str.endswith("}"):
                        var_name = pub_str[2:-1]
                        if var_name not in env_var_names:
                            self._add_warning(
                                f"Port references undefined variable: {var_name}"
                            )
                        host_port = None
                    else:
                        try:
                            host_port = int(published)
                        except (ValueError, TypeError) as e:
                            self._add_warning(
                                f"Failed to parse published port: {published} - {e}"
                            )

                protocol = port_config.get("protocol")

            if container_port:
                metadata = metadata_lookup.get(container_port, {})
                # Get protocol from metadata if not in config
                if not protocol:
                    protocol = metadata.get("protocol")

                port = CasaOSPort(
                    container=container_port,
                    host=host_port,
                    protocol=protocol if protocol in ["tcp", "udp"] else None,
                    description=self._extract_multilingual(metadata.get("description")),
                )
                ports.append(port)
            else:
                # Port config was skipped
                self._add_warning(
                    f"Skipping unparseable port configuration: {port_config}"
                )

        return ports

    def _parse_volumes(
        self,
        volumes_config: list[Any],
        volumes_metadata: list[dict[str, Any]],
        env_var_names: set[str],
    ) -> list[CasaOSVolume]:
        """Parse volume mounts with their metadata.

        Args:
            volumes_config: Volumes section from compose
            volumes_metadata: Volumes metadata from x-casaos
            env_var_names: Set of defined environment variable names for validation

        Returns:
            List of CasaOSVolume instances
        """
        volumes = []

        # Build metadata lookup by container path
        metadata_lookup = {
            item.get("container"): item
            for item in volumes_metadata
            if item.get("container")
        }

        # Parse each volume
        for volume_config in volumes_config:
            container_path = None
            host_path = None
            mode = None

            if isinstance(volume_config, str):
                # String format: "host:container" or "host:container:mode"
                parts = volume_config.split(":")
                if len(parts) >= 2:
                    host_path = parts[0]
                    container_path = parts[1]
                    if len(parts) == 3:
                        mode = parts[2]
            elif isinstance(volume_config, dict):
                # Dict format: {source: X, target: Y, ...}
                container_path = volume_config.get("target")
                host_path = volume_config.get("source")
                read_only = volume_config.get("read_only", False)
                if read_only:
                    mode = "ro"

            if container_path and host_path:
                metadata = metadata_lookup.get(container_path, {})
                volume = CasaOSVolume(
                    container=container_path,
                    host=host_path,
                    mode=mode,
                    description=self._extract_multilingual(metadata.get("description")),
                )
                volumes.append(volume)
            else:
                # Volume config was skipped
                self._add_warning(
                    f"Skipping incomplete volume configuration: {volume_config}"
                )

        return volumes

    def _extract_multilingual(self, field: Any) -> str:
        """Extract string from multilingual field.

        CasaOS uses multilingual fields like:
        description:
          en_us: "English description"
          zh_cn: "Chinese description"

        This extracts the en_us value or returns empty string.

        Args:
            field: The field value (could be str, dict, or None)

        Returns:
            Extracted string value
        """
        if isinstance(field, dict):
            # Try common English keys
            for key in ["en_us", "en-us", "en", "default"]:
                if key in field:
                    return str(field[key])
            # Fallback to first available value
            if field:
                return str(next(iter(field.values())))
            return ""
        elif isinstance(field, str):
            return field
        else:
            return ""
