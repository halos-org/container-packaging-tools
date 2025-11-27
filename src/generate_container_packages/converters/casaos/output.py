"""Output writer for CasaOS to HaLOS conversion.

Writes metadata.yaml, config.yml, and docker-compose.yml files with
schema validation and proper YAML formatting.
"""

import copy
from pathlib import Path
from typing import Any

import yaml

from schemas.config import ConfigSchema
from schemas.metadata import PackageMetadata

from .models import ConversionContext


class OutputWriter:
    """Writes HaLOS package files to disk with validation.

    Takes transformer output (metadata, config, compose dictionaries)
    and writes them as properly formatted YAML files after validating
    against Pydantic schemas.

    The writer:
    - Validates metadata against PackageMetadata schema
    - Validates config against ConfigSchema schema
    - Strips any remaining x-casaos extensions from compose
    - Writes three files: metadata.yaml, config.yml, docker-compose.yml
    """

    def __init__(self, output_dir: Path) -> None:
        """Initialize output writer.

        Args:
            output_dir: Directory to write output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_package(
        self,
        metadata: dict[str, Any],
        config: dict[str, Any],
        compose: dict[str, Any],
        context: ConversionContext,
    ) -> None:
        """Write all package files with validation.

        Validates metadata and config against schemas before writing.
        Strips any x-casaos extensions from compose.

        Args:
            metadata: Metadata dict (must validate against PackageMetadata)
            config: Config dict (must validate against ConfigSchema)
            compose: Docker Compose dict (x-casaos will be stripped)
            context: Conversion context for tracking errors

        Raises:
            ValidationError: If metadata or config don't validate against schemas
            OSError: If file writing fails
        """
        # Validate metadata against schema
        try:
            PackageMetadata.model_validate(metadata)
        except Exception as e:
            error_msg = f"Metadata validation failed: {e}"
            context.errors.append(error_msg)
            raise

        # Validate config against schema
        try:
            ConfigSchema.model_validate(config)
        except Exception as e:
            error_msg = f"Config validation failed: {e}"
            context.errors.append(error_msg)
            raise

        # Strip any remaining x-casaos extensions from compose
        compose_clean = self._strip_xcasaos(compose)

        # Write files
        try:
            self._write_yaml(self.output_dir / "metadata.yaml", metadata)
            self._write_yaml(self.output_dir / "config.yml", config)
            self._write_yaml(self.output_dir / "docker-compose.yml", compose_clean)
        except OSError as e:
            error_msg = f"Failed to write output files: {e}"
            context.errors.append(error_msg)
            raise

    def _strip_xcasaos(self, compose: dict[str, Any]) -> dict[str, Any]:
        """Strip x-casaos extensions from compose dict.

        Removes x-casaos keys at both root level and service level.

        Args:
            compose: Docker Compose dictionary

        Returns:
            Cleaned compose dictionary without x-casaos extensions
        """
        # Deep copy to avoid modifying input
        compose_clean = copy.deepcopy(compose)

        # Remove root-level x-casaos
        compose_clean.pop("x-casaos", None)

        # Remove service-level x-casaos
        if "services" in compose_clean:
            for service_name in compose_clean["services"]:
                service = compose_clean["services"][service_name]
                if isinstance(service, dict):
                    service.pop("x-casaos", None)

        return compose_clean

    def _write_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """Write data as YAML file with proper formatting.

        Uses PyYAML with settings for readable output:
        - Block style (not inline flow style)
        - Sorted keys for consistency
        - Proper indentation

        Args:
            path: Output file path
            data: Data to write as YAML
        """
        with open(path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,  # Use block style, not inline {}
                sort_keys=True,  # Sort keys for consistency
                allow_unicode=True,  # Support Unicode characters
                indent=2,  # 2-space indentation
            )
