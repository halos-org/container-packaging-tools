"""Custom exceptions for converter subsystem."""


class ConverterError(Exception):
    """Base exception for all converter errors."""

    pass


class ConversionError(ConverterError):
    """Raised when transformation fails due to incompatible data.

    This error indicates that the source format data cannot be converted
    to HaLOS format, typically due to missing required fields, incompatible
    structures, or invalid data that cannot be mapped.
    """

    pass


class ValidationError(ConverterError):
    """Raised when source data is invalid or malformed.

    This error indicates that the input data does not conform to the
    expected source format schema. It should be raised during the parse
    phase when validation fails.
    """

    pass


class GenerationError(ConverterError):
    """Raised when output generation fails.

    This error indicates that the converter cannot generate valid HaLOS
    output files from the transformed data. This typically occurs when
    the output would fail schema validation or violate HaLOS requirements.
    """

    pass
