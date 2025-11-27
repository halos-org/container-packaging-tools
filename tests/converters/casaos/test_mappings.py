"""Unit tests for CasaOS mapping configuration files."""

import pytest
import yaml

from generate_container_packages.converters.casaos.constants import (
    get_default_mappings_dir,
)
from schemas.config import ConfigField
from schemas.metadata import PackageMetadata

# Path to mapping files
MAPPINGS_DIR = get_default_mappings_dir()


class TestCategoriesMappings:
    """Tests for categories.yaml mapping file."""

    @pytest.fixture
    def categories_config(self):
        """Load categories.yaml configuration."""
        categories_file = MAPPINGS_DIR / "categories.yaml"
        with open(categories_file) as f:
            return yaml.safe_load(f)

    def test_categories_file_exists(self):
        """Test that categories.yaml exists."""
        categories_file = MAPPINGS_DIR / "categories.yaml"
        assert categories_file.exists(), "categories.yaml file must exist"

    def test_categories_valid_yaml(self, categories_config):
        """Test that categories.yaml is valid YAML."""
        assert categories_config is not None
        assert isinstance(categories_config, dict)

    def test_categories_has_mappings(self, categories_config):
        """Test that categories.yaml has mappings section."""
        assert "mappings" in categories_config
        assert isinstance(categories_config["mappings"], dict)
        assert len(categories_config["mappings"]) > 0

    def test_categories_has_default(self, categories_config):
        """Test that categories.yaml has default fallback."""
        assert "default" in categories_config
        assert isinstance(categories_config["default"], str)
        assert len(categories_config["default"]) > 0

    def test_categories_valid_debian_sections(self, categories_config):
        """Test that all mapped categories use valid Debian sections."""
        # Get valid Debian sections from PackageMetadata model
        valid_sections = set(
            PackageMetadata.model_fields["debian_section"].annotation.__args__
        )

        # Check all mapped sections are valid
        for casaos_cat, debian_section in categories_config["mappings"].items():
            assert debian_section in valid_sections, (
                f"Invalid Debian section '{debian_section}' for category '{casaos_cat}'"
            )

        # Check default is valid
        assert categories_config["default"] in valid_sections, (
            f"Invalid default section '{categories_config['default']}'"
        )

    def test_categories_common_mappings_exist(self, categories_config):
        """Test that common CasaOS categories are mapped."""
        common_categories = [
            "Entertainment",
            "Media",
            "Productivity",
            "Developer",
            "Network",
            "Tools",
        ]
        mappings = categories_config["mappings"]

        for category in common_categories:
            assert category in mappings, (
                f"Common category '{category}' should be mapped"
            )


class TestFieldTypesMappings:
    """Tests for field_types.yaml mapping file."""

    @pytest.fixture
    def field_types_config(self):
        """Load field_types.yaml configuration."""
        field_types_file = MAPPINGS_DIR / "field_types.yaml"
        with open(field_types_file) as f:
            return yaml.safe_load(f)

    def test_field_types_file_exists(self):
        """Test that field_types.yaml exists."""
        field_types_file = MAPPINGS_DIR / "field_types.yaml"
        assert field_types_file.exists(), "field_types.yaml file must exist"

    def test_field_types_valid_yaml(self, field_types_config):
        """Test that field_types.yaml is valid YAML."""
        assert field_types_config is not None
        assert isinstance(field_types_config, dict)

    def test_field_types_has_patterns(self, field_types_config):
        """Test that field_types.yaml has patterns section."""
        assert "patterns" in field_types_config
        assert isinstance(field_types_config["patterns"], list)
        assert len(field_types_config["patterns"]) > 0

    def test_field_types_has_defaults(self, field_types_config):
        """Test that field_types.yaml has defaults section."""
        assert "defaults" in field_types_config
        assert isinstance(field_types_config["defaults"], dict)

    def test_field_types_has_groups(self, field_types_config):
        """Test that field_types.yaml has groups section."""
        assert "groups" in field_types_config
        assert isinstance(field_types_config["groups"], dict)

    def test_field_types_valid_types(self, field_types_config):
        """Test that all field types are valid ConfigField types."""
        # Get valid field types from ConfigField model
        valid_types = set(ConfigField.model_fields["type"].annotation.__args__)

        # Check pattern types
        for pattern in field_types_config["patterns"]:
            assert "type" in pattern, f"Pattern must have 'type': {pattern}"
            assert pattern["type"] in valid_types, (
                f"Invalid type '{pattern['type']}' in pattern {pattern['pattern']}"
            )

        # Check default types
        for casaos_type, field_type in field_types_config["defaults"].items():
            if casaos_type != "fallback":  # fallback can be any type
                assert field_type in valid_types, (
                    f"Invalid default type '{field_type}' for '{casaos_type}'"
                )

    def test_field_types_patterns_have_required_fields(self, field_types_config):
        """Test that all patterns have required fields."""
        for pattern in field_types_config["patterns"]:
            assert "pattern" in pattern, "Pattern must have 'pattern' field"
            assert "type" in pattern, f"Pattern must have 'type': {pattern}"
            assert isinstance(pattern["pattern"], str)
            assert isinstance(pattern["type"], str)

    def test_field_types_common_patterns_exist(self, field_types_config):
        """Test that common environment variable patterns are covered."""
        patterns = [p["pattern"] for p in field_types_config["patterns"]]

        # Check for common patterns
        assert any("PORT" in p for p in patterns), (
            "Should have pattern for PORT variables"
        )
        assert any("PASS" in p for p in patterns), (
            "Should have pattern for PASSWORD variables"
        )
        assert any("PATH" in p or "DIR" in p for p in patterns), (
            "Should have pattern for path variables"
        )
        assert any("USER" in p for p in patterns), (
            "Should have pattern for USER variables"
        )

    def test_field_types_integer_validation_ranges(self, field_types_config):
        """Test that integer types have sensible validation ranges."""
        for pattern in field_types_config["patterns"]:
            if pattern["type"] == "integer" and "validation" in pattern:
                validation = pattern["validation"]
                if "min" in validation and "max" in validation:
                    assert validation["min"] < validation["max"], (
                        f"Min must be less than max in pattern {pattern['pattern']}"
                    )


class TestPathsMappings:
    """Tests for paths.yaml mapping file."""

    @pytest.fixture
    def paths_config(self):
        """Load paths.yaml configuration."""
        paths_file = MAPPINGS_DIR / "paths.yaml"
        with open(paths_file) as f:
            return yaml.safe_load(f)

    def test_paths_file_exists(self):
        """Test that paths.yaml exists."""
        paths_file = MAPPINGS_DIR / "paths.yaml"
        assert paths_file.exists(), "paths.yaml file must exist"

    def test_paths_valid_yaml(self, paths_config):
        """Test that paths.yaml is valid YAML."""
        assert paths_config is not None
        assert isinstance(paths_config, dict)

    def test_paths_has_transforms(self, paths_config):
        """Test that paths.yaml has transforms section."""
        assert "transforms" in paths_config
        assert isinstance(paths_config["transforms"], list)
        assert len(paths_config["transforms"]) > 0

    def test_paths_has_special_cases(self, paths_config):
        """Test that paths.yaml has special_cases section."""
        assert "special_cases" in paths_config
        assert isinstance(paths_config["special_cases"], dict)

    def test_paths_has_default(self, paths_config):
        """Test that paths.yaml has default section."""
        assert "default" in paths_config
        assert isinstance(paths_config["default"], dict)

    def test_paths_transforms_have_required_fields(self, paths_config):
        """Test that all transforms have required fields."""
        for transform in paths_config["transforms"]:
            assert "from" in transform, "Transform must have 'from' field"
            assert "to" in transform, f"Transform must have 'to' field: {transform}"
            assert "description" in transform, (
                f"Transform must have 'description': {transform}"
            )

    def test_paths_casaos_appdata_transform(self, paths_config):
        """Test that CasaOS /DATA/AppData pattern is transformed."""
        transforms = paths_config["transforms"]
        appdata_transforms = [
            t for t in transforms if "/DATA/AppData" in t.get("from", "")
        ]
        assert len(appdata_transforms) > 0, "Should have transforms for /DATA/AppData"

        # Check it maps to CONTAINER_DATA_ROOT
        for t in appdata_transforms:
            assert "CONTAINER_DATA_ROOT" in t["to"], (
                "AppData should map to CONTAINER_DATA_ROOT"
            )

    def test_paths_system_paths_preserved(self, paths_config):
        """Test that system paths are in preserve list."""
        special_cases = paths_config["special_cases"]
        assert "preserve" in special_cases
        preserve = special_cases["preserve"]

        # Common system paths that should be preserved
        system_paths = ["/etc", "/var", "/usr", "/tmp"]
        for path in system_paths:
            assert path in preserve, f"System path '{path}' should be preserved"

    def test_paths_configurable_patterns_valid(self, paths_config):
        """Test that configurable path patterns are valid."""
        special_cases = paths_config["special_cases"]
        if "configurable" in special_cases:
            for config in special_cases["configurable"]:
                assert "pattern" in config, "Configurable must have 'pattern' field"
                assert "field_name" in config, (
                    f"Configurable must have 'field_name': {config}"
                )
                assert "description" in config, (
                    f"Configurable must have 'description': {config}"
                )

                # Field name should be valid environment variable name
                assert config["field_name"].isupper(), (
                    f"Field name should be uppercase: {config['field_name']}"
                )

    def test_paths_no_preserve_transform_overlap(self, paths_config):
        """Test that preserve paths don't overlap with transform paths."""
        special_cases = paths_config["special_cases"]
        transforms = paths_config["transforms"]

        if "preserve" not in special_cases:
            return

        preserve_paths = set(special_cases["preserve"])
        transform_froms = {t["from"] for t in transforms}

        # Check for direct overlaps
        overlaps = preserve_paths & transform_froms
        assert len(overlaps) == 0, (
            f"Paths should not be both preserved and transformed: {overlaps}"
        )

        # Check for prefix overlaps (e.g., /etc and /etc/config)
        for preserve in preserve_paths:
            for transform_from in transform_froms:
                # Skip if they contain placeholders
                if "{" in preserve or "{" in transform_from:
                    continue

                # Check if one is a prefix of the other
                if transform_from.startswith(preserve + "/") or preserve.startswith(
                    transform_from + "/"
                ):
                    raise AssertionError(
                        f"Preserved path '{preserve}' overlaps with transform '{transform_from}'"
                    )


class TestMappingsIntegration:
    """Integration tests for mapping files working together."""

    def test_all_mapping_files_present(self):
        """Test that all required mapping files exist."""
        required_files = ["categories.yaml", "field_types.yaml", "paths.yaml"]
        for filename in required_files:
            filepath = MAPPINGS_DIR / filename
            assert filepath.exists(), f"Required mapping file '{filename}' must exist"

    def test_readme_exists(self):
        """Test that README.md documentation exists."""
        readme_file = MAPPINGS_DIR / "README.md"
        assert readme_file.exists(), "README.md documentation must exist"

    def test_mappings_directory_structure(self):
        """Test that mappings directory structure is correct."""
        assert MAPPINGS_DIR.exists(), "mappings/casaos directory must exist"
        assert MAPPINGS_DIR.is_dir(), "mappings/casaos must be a directory"
