"""Base converter interface for all source format converters."""

from abc import ABC, abstractmethod
from typing import Any


class Converter(ABC):
    """Abstract base class for container app definition converters.

    This interface defines the contract for all converters that transform
    application definitions from various source formats (CasaOS, Runtipi, etc.)
    into the HaLOS container store format.

    Converters follow a three-stage pipeline:
    1. Parse: Read and validate the source format
    2. Transform: Convert to HaLOS internal representation
    3. Generate: Produce output files (metadata.yaml, config.yml, docker-compose.yml)

    Subclasses must implement all three methods to provide complete conversion
    functionality for their specific source format.
    """

    @abstractmethod
    def parse(self, source: Any) -> Any:
        """Parse source format into internal representation.

        Args:
            source: Source data in the format-specific structure.
                   Could be a file path, directory, dict, or other format-specific type.

        Returns:
            Parsed data in an intermediate representation suitable for transformation.

        Raises:
            ValidationError: If source data is invalid or malformed.
        """
        pass

    @abstractmethod
    def transform(self, parsed_data: Any) -> Any:
        """Transform parsed data into HaLOS format.

        Args:
            parsed_data: Data returned from the parse() method.

        Returns:
            Transformed data ready for HaLOS package generation.

        Raises:
            ConversionError: If transformation fails due to incompatible data.
        """
        pass

    @abstractmethod
    def generate(self, transformed_data: Any) -> Any:
        """Generate HaLOS output files from transformed data.

        Args:
            transformed_data: Data returned from the transform() method.

        Returns:
            Dictionary containing the generated file contents:
            - "metadata.yaml": Package metadata
            - "config.yml": Configuration schema
            - "docker-compose.yml": Container definitions

        Raises:
            GenerationError: If output generation fails.
        """
        pass
