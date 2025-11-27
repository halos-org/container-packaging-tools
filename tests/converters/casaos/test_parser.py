"""Unit tests for CasaOS parser."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from generate_container_packages.converters.casaos.models import CasaOSApp
from generate_container_packages.converters.casaos.parser import CasaOSParser
from generate_container_packages.converters.exceptions import (
    ValidationError as ConverterValidationError,
)

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCasaOSParser:
    """Tests for CasaOSParser class."""

    def test_parser_initialization(self):
        """Test that parser can be instantiated."""
        parser = CasaOSParser()
        assert parser is not None
        assert isinstance(parser, CasaOSParser)

    def test_parse_from_file_simple_app(self):
        """Test parsing a simple CasaOS app from file."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        assert isinstance(app, CasaOSApp)
        assert app.id == "nginx-test"
        assert app.name == "nginx-test"
        assert app.category == "Utilities"
        assert len(app.services) == 1
        assert app.services[0].name == "nginx"
        assert app.services[0].image == "nginx:1.25"

    def test_parse_from_file_complex_app(self):
        """Test parsing a complex CasaOS app from file."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        assert isinstance(app, CasaOSApp)
        assert app.id == "jellyfin"
        assert app.name == "jellyfin"
        assert app.category == "Media"
        assert app.developer == "Jellyfin"
        assert app.tagline == "The Free Software Media System"
        assert app.description.startswith("Jellyfin is a Free Software")
        assert (
            app.icon
            == "https://cdn.jsdelivr.net/gh/IceWhaleTech/CasaOS-AppStore@main/Apps/Jellyfin/icon.png"
        )
        assert len(app.screenshots) == 3
        assert len(app.services) == 1

    def test_parse_service_metadata(self):
        """Test that service-level metadata is correctly extracted."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)
        service = app.services[0]

        # Check environment variables
        assert len(service.environment) == 4
        env_names = {env.name for env in service.environment}
        assert "PUID" in env_names
        assert "PGID" in env_names
        assert "TZ" in env_names

        # Check ports
        assert len(service.ports) == 4
        port_nums = {port.container for port in service.ports}
        assert 8096 in port_nums
        assert 8920 in port_nums
        assert 7359 in port_nums

        # Check volumes
        assert len(service.volumes) == 2
        volume_paths = {vol.container for vol in service.volumes}
        assert "/config" in volume_paths
        assert "/Media" in volume_paths

    def test_parse_environment_variables(self):
        """Test environment variable parsing with descriptions."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)
        service = app.services[0]

        assert len(service.environment) == 1
        env = service.environment[0]
        assert env.name == "TZ"
        assert env.default == "$TZ"
        assert env.description == "Timezone"

    def test_parse_ports_with_descriptions(self):
        """Test port parsing with descriptions."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)
        service = app.services[0]

        assert len(service.ports) == 1
        port = service.ports[0]
        assert port.container == 80
        assert port.host is None  # Variable reference, not parsed as int
        assert port.description == "Web UI port"

    def test_parse_volumes_with_descriptions(self):
        """Test volume parsing with descriptions."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)
        service = app.services[0]

        assert len(service.volumes) == 1
        volume = service.volumes[0]
        assert volume.container == "/usr/share/nginx/html"
        assert volume.host == "/DATA/AppData/$AppID/html"
        assert volume.description == "HTML content directory"

    def test_parse_from_string(self):
        """Test parsing CasaOS app from YAML string."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"
        yaml_content = compose_file.read_text()

        app = parser.parse_from_string(yaml_content)

        assert isinstance(app, CasaOSApp)
        assert app.id == "nginx-test"
        assert app.name == "nginx-test"

    def test_parse_nonexistent_file(self):
        """Test that parsing nonexistent file raises appropriate error."""
        parser = CasaOSParser()
        nonexistent = FIXTURES_DIR / "nonexistent" / "docker-compose.yml"

        with pytest.raises(FileNotFoundError):
            parser.parse_from_file(nonexistent)

    def test_parse_invalid_yaml(self):
        """Test that invalid YAML raises validation error."""
        parser = CasaOSParser()
        invalid_yaml = "{ this is not: valid: yaml ]"

        with pytest.raises(ConverterValidationError) as exc_info:
            parser.parse_from_string(invalid_yaml)
        assert "yaml" in str(exc_info.value).lower()

    def test_parse_missing_required_fields(self):
        """Test that missing required fields raises validation error."""
        parser = CasaOSParser()
        # Missing 'services' key
        incomplete_yaml = """
name: test-app
x-casaos:
  category: Utilities
"""
        with pytest.raises(ConverterValidationError):
            parser.parse_from_string(incomplete_yaml)

    def test_parse_missing_x_casaos(self):
        """Test that missing x-casaos metadata raises validation error."""
        parser = CasaOSParser()
        no_metadata = """
name: test-app
services:
  web:
    image: nginx:latest
"""
        with pytest.raises(ConverterValidationError) as exc_info:
            parser.parse_from_string(no_metadata)
        assert "x-casaos" in str(exc_info.value).lower()

    def test_parse_extracts_app_name_from_name_field(self):
        """Test that app name is extracted from compose 'name' field."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        # Both id and name should come from the 'name' field
        assert app.id == "nginx-test"
        assert app.name == "nginx-test"

    def test_parse_merges_service_and_app_metadata(self):
        """Test that service x-casaos and app-level x-casaos are properly merged."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        # App-level metadata should be present
        assert app.developer == "Jellyfin"
        assert app.category == "Media"

        # Service-level metadata should be merged into service
        assert len(app.services[0].environment) > 0
        assert len(app.services[0].ports) > 0

    def test_parse_handles_multilingual_fields(self):
        """Test that multilingual description fields are extracted correctly."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        # Should extract en_us value as the default
        assert app.description is not None
        assert "Jellyfin" in app.description
        assert app.tagline == "The Free Software Media System"

    def test_parse_empty_services_list(self):
        """Test that empty services list raises validation error."""
        parser = CasaOSParser()
        empty_services = """
name: test-app
services: {}
x-casaos:
  category: Utilities
"""
        with pytest.raises((ValidationError, ConverterValidationError)):
            parser.parse_from_string(empty_services)

    def test_parse_preserves_icon_url(self):
        """Test that icon URL is preserved correctly."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        assert app.icon is not None
        assert app.icon.startswith("https://")
        assert "icon.png" in app.icon

    def test_parse_extracts_all_screenshots(self):
        """Test that all screenshots are extracted."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "complex-app" / "docker-compose.yml"

        app = parser.parse_from_file(compose_file)

        assert len(app.screenshots) == 3
        for screenshot in app.screenshots:
            assert screenshot.startswith("https://")


class TestParserWarnings:
    """Tests for parser warning collection and validation."""

    def test_parser_collects_warnings(self):
        """Test that parser collects warnings during parsing."""
        parser = CasaOSParser()
        # Invalid port reference
        yaml_with_issues = """
name: test-app
services:
  web:
    image: nginx:latest
    ports:
      - "invalid:80"
x-casaos:
  category: Utilities
  description:
    en_us: Test
  tagline:
    en_us: App
  developer: Me
"""
        _app = parser.parse_from_string(yaml_with_issues)
        # Should have warning about parsing failure
        assert len(parser.warnings) > 0

    def test_parser_warns_undefined_variable_reference(self):
        """Test that parser warns about undefined variable references."""
        parser = CasaOSParser()
        yaml_content = """
name: test-app
services:
  web:
    image: nginx:latest
    ports:
      - target: 80
        published: "${UNDEFINED_VAR}"
x-casaos:
  category: Utilities
  description:
    en_us: Test
  tagline:
    en_us: App
  developer: Me
"""
        _app = parser.parse_from_string(yaml_content)
        # Should warn about undefined UNDEFINED_VAR
        assert any("UNDEFINED_VAR" in w for w in parser.warnings)

    def test_parser_validates_command_strings(self):
        """Test that parser validates command list items are strings."""
        parser = CasaOSParser()
        # This should generate a warning if command has non-string items
        yaml_content = """
name: test-app
services:
  web:
    image: nginx:latest
    command: ["string", 123]  # 123 is not a string
x-casaos:
  category: Utilities
  description:
    en_us: Test
  tagline:
    en_us: App
  developer: Me
"""
        app = parser.parse_from_string(yaml_content)
        # Parser should convert non-strings and warn
        assert app.services[0].command is not None
        assert all(isinstance(c, str) for c in app.services[0].command)
        # Should have warning about non-string item
        assert any("command" in w.lower() for w in parser.warnings)

    def test_parser_file_context_in_errors(self):
        """Test that file path is included in error messages."""
        parser = CasaOSParser()
        compose_file = FIXTURES_DIR / "simple-app" / "docker-compose.yml"

        # Parse successfully
        _app = parser.parse_from_file(compose_file)

        # Now try parsing invalid YAML with file context
        invalid_file = FIXTURES_DIR / "simple-app" / "invalid.yml"
        try:
            # This will fail if file doesn't exist, which is expected
            parser.parse_from_file(invalid_file)
        except FileNotFoundError as e:
            assert "invalid.yml" in str(e)


class TestParserEdgeCases:
    """Tests for parser edge cases and error handling."""

    def test_parse_service_without_x_casaos(self):
        """Test parsing service without x-casaos metadata."""
        parser = CasaOSParser()
        minimal = """
name: minimal-app
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
x-casaos:
  category: Utilities
  description:
    en_us: Minimal app
  tagline:
    en_us: Test app
  developer: Test
"""
        app = parser.parse_from_string(minimal)

        assert len(app.services) == 1
        # Service should still be created, just without metadata
        assert app.services[0].name == "web"

    def test_parse_with_extra_fields(self):
        """Test that extra fields in x-casaos are allowed."""
        parser = CasaOSParser()
        extra_fields = """
name: test-app
services:
  web:
    image: nginx:latest
x-casaos:
  category: Utilities
  description:
    en_us: Test
  tagline:
    en_us: App
  developer: Me
  custom_field: "Should be allowed"
  another_field: 123
"""
        # Should not raise error due to extra="allow" in models
        app = parser.parse_from_string(extra_fields)
        assert app.id == "test-app"
