"""Unit tests for base converter interface."""

from abc import ABC

import pytest

from generate_container_packages.converters.base import Converter


class TestConverterInterface:
    """Tests for base Converter abstract interface."""

    def test_converter_is_abstract(self):
        """Test that Converter cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            Converter()  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_converter_has_parse_method(self):
        """Test that Converter defines parse method."""
        assert hasattr(Converter, "parse")
        assert callable(Converter.parse)

    def test_converter_has_transform_method(self):
        """Test that Converter defines transform method."""
        assert hasattr(Converter, "transform")
        assert callable(Converter.transform)

    def test_converter_has_generate_method(self):
        """Test that Converter defines generate method."""
        assert hasattr(Converter, "generate")
        assert callable(Converter.generate)

    def test_converter_subclass_requires_implementation(self):
        """Test that subclass must implement all abstract methods."""

        class IncompleteConverter(Converter):
            """Incomplete converter missing required methods."""

            pass

        with pytest.raises(TypeError) as exc_info:
            IncompleteConverter()  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_converter_can_be_subclassed(self):
        """Test that Converter can be properly subclassed."""

        class CompleteConverter(Converter):
            """Complete converter implementation."""

            def parse(self, source):  # type: ignore[override]
                return {"parsed": True}

            def transform(self, parsed_data):  # type: ignore[override]
                return {"transformed": True}

            def generate(self, transformed_data):  # type: ignore[override]
                return {"generated": True}

        # Should be able to instantiate complete implementation
        converter = CompleteConverter()
        assert converter is not None
        assert isinstance(converter, Converter)
        assert isinstance(converter, ABC)

    def test_converter_methods_are_abstract(self):
        """Test that parse, transform, and generate are abstract methods."""

        # Get abstract methods from Converter
        abstract_methods = getattr(Converter, "__abstractmethods__", set())
        assert "parse" in abstract_methods
        assert "transform" in abstract_methods
        assert "generate" in abstract_methods
