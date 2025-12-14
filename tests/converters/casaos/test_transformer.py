"""Tests for CasaOS metadata transformer.

Tests the transformation of CasaOS app definitions to HaLOS format,
including category mapping, field type inference, path transformation,
and package naming.
"""

from pathlib import Path

import pytest

from generate_container_packages.converters.casaos.constants import (
    get_default_mappings_dir,
)
from generate_container_packages.converters.casaos.models import (
    CasaOSApp,
    CasaOSEnvVar,
    CasaOSPort,
    CasaOSService,
    CasaOSVolume,
    ConversionContext,
)
from generate_container_packages.converters.casaos.transformer import (
    MetadataTransformer,
)


@pytest.fixture
def mappings_dir() -> Path:
    """Return path to test mapping files."""
    return get_default_mappings_dir()


@pytest.fixture
def transformer(mappings_dir: Path) -> MetadataTransformer:
    """Create a MetadataTransformer instance."""
    return MetadataTransformer(mappings_dir)


@pytest.fixture
def conversion_context() -> ConversionContext:
    """Create a ConversionContext for testing."""
    return ConversionContext(source_format="casaos", app_id="test-app")


@pytest.fixture
def simple_casaos_app() -> CasaOSApp:
    """Create a simple CasaOS app for testing."""
    return CasaOSApp(
        id="nginx-test",
        name="Nginx Test",
        tagline="Web server",
        description="Simple nginx web server for testing",
        category="Utilities",
        developer="nginx",
        homepage="https://nginx.org",
        icon="https://example.com/nginx-icon.png",
        screenshots=["https://example.com/screenshot1.png"],
        tags=["web", "server"],
        services=[
            CasaOSService(
                name="nginx",
                image="nginx:1.25",
                environment=[
                    CasaOSEnvVar(
                        name="TZ",
                        default="UTC",
                        label="Timezone",
                        description="Container timezone",
                        type="text",
                    ),
                    CasaOSEnvVar(
                        name="WEBUI_PORT",
                        default="8080",
                        label="Web UI Port",
                        description="Port for web interface",
                        type="number",
                    ),
                ],
                ports=[
                    CasaOSPort(
                        container=80,
                        host=8080,
                        protocol="tcp",
                        description="Web UI port",
                    )
                ],
                volumes=[
                    CasaOSVolume(
                        container="/usr/share/nginx/html",
                        host="/DATA/AppData/nginx-test/html",
                        mode="rw",
                        description="HTML content directory",
                    )
                ],
            )
        ],
    )


class TestCategoryMapping:
    """Test category mapping from CasaOS to Debian sections."""

    def test_entertainment_to_video(self, transformer: MetadataTransformer) -> None:
        """Test Entertainment category maps to video section."""
        assert transformer._map_category("Entertainment") == "video"

    def test_media_to_video(self, transformer: MetadataTransformer) -> None:
        """Test Media category maps to video section."""
        assert transformer._map_category("Media") == "video"

    def test_developer_to_devel(self, transformer: MetadataTransformer) -> None:
        """Test Developer category maps to devel section."""
        assert transformer._map_category("Developer") == "devel"

    def test_utilities_to_utils(self, transformer: MetadataTransformer) -> None:
        """Test Utilities category maps to utils section."""
        assert transformer._map_category("Utilities") == "utils"

    def test_network_to_net(self, transformer: MetadataTransformer) -> None:
        """Test Network category maps to net section."""
        assert transformer._map_category("Network") == "net"

    def test_games_to_games(self, transformer: MetadataTransformer) -> None:
        """Test Games category maps to games section."""
        assert transformer._map_category("Games") == "games"

    def test_unknown_category_fallback(self, transformer: MetadataTransformer) -> None:
        """Test unknown category falls back to misc."""
        assert transformer._map_category("UnknownCategory") == "misc"

    def test_empty_category_fallback(self, transformer: MetadataTransformer) -> None:
        """Test empty category falls back to misc."""
        assert transformer._map_category("") == "misc"

    def test_case_sensitive_mapping(self, transformer: MetadataTransformer) -> None:
        """Test category mapping is case-sensitive."""
        assert (
            transformer._map_category("entertainment") == "misc"
        )  # lowercase should not match
        assert (
            transformer._map_category("ENTERTAINMENT") == "misc"
        )  # uppercase should not match


class TestCategoryTagMapping:
    """Test category:: tag generation from CasaOS categories."""

    def test_entertainment_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Entertainment category generates category::entertainment tag."""
        assert (
            transformer._get_category_tag("Entertainment") == "category::entertainment"
        )

    def test_media_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Media category generates category::media tag."""
        assert transformer._get_category_tag("Media") == "category::media"

    def test_developer_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Developer category generates category::development tag."""
        assert transformer._get_category_tag("Developer") == "category::development"

    def test_utilities_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Utilities category generates category::utilities tag."""
        assert transformer._get_category_tag("Utilities") == "category::utilities"

    def test_network_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Network category generates category::networking tag."""
        assert transformer._get_category_tag("Network") == "category::networking"

    def test_system_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test System category generates category::system-tools tag."""
        assert transformer._get_category_tag("System") == "category::system-tools"

    def test_monitoring_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Monitoring category generates category::monitoring tag."""
        assert transformer._get_category_tag("Monitoring") == "category::monitoring"

    def test_games_category_tag(self, transformer: MetadataTransformer) -> None:
        """Test Games category generates category::games tag."""
        assert transformer._get_category_tag("Games") == "category::games"

    def test_unknown_category_no_tag(self, transformer: MetadataTransformer) -> None:
        """Test unknown category returns None (no tag generated)."""
        assert transformer._get_category_tag("UnknownCategory") is None

    def test_empty_category_no_tag(self, transformer: MetadataTransformer) -> None:
        """Test empty category returns None (no tag generated)."""
        assert transformer._get_category_tag("") is None


class TestFieldTypeInference:
    """Test field type inference from environment variable names."""

    def test_port_inference(self, transformer: MetadataTransformer) -> None:
        """Test PORT suffix infers integer type with port validation."""
        env_var = CasaOSEnvVar(name="WEBUI_PORT", default="8080", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert validation.get("min") == 1024
        assert validation.get("max") == 65535
        assert group == "network"

    def test_port_without_underscore(self, transformer: MetadataTransformer) -> None:
        """Test PORT at end infers integer type."""
        env_var = CasaOSEnvVar(name="PORT", default="3000", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert validation.get("min") == 1024
        assert validation.get("max") == 65535
        assert group == "network"

    def test_password_inference(self, transformer: MetadataTransformer) -> None:
        """Test PASSWORD suffix infers password type."""
        env_var = CasaOSEnvVar(name="DB_PASSWORD", default="", type="password")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"
        assert group == "authentication"

    def test_passwd_inference(self, transformer: MetadataTransformer) -> None:
        """Test PASSWD suffix infers password type."""
        env_var = CasaOSEnvVar(name="USER_PASSWD", default="", type="password")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"
        assert group == "authentication"

    def test_secret_inference(self, transformer: MetadataTransformer) -> None:
        """Test SECRET suffix infers password type."""
        env_var = CasaOSEnvVar(name="API_SECRET", default="", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"
        assert group == "authentication"

    def test_token_inference(self, transformer: MetadataTransformer) -> None:
        """Test TOKEN suffix infers password type."""
        env_var = CasaOSEnvVar(name="AUTH_TOKEN", default="", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"
        assert group == "authentication"

    def test_key_inference(self, transformer: MetadataTransformer) -> None:
        """Test KEY suffix infers password type."""
        env_var = CasaOSEnvVar(name="API_KEY", default="", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"
        assert group == "authentication"

    def test_host_inference(self, transformer: MetadataTransformer) -> None:
        """Test HOST suffix infers string type."""
        env_var = CasaOSEnvVar(name="DB_HOST", default="localhost", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "network"

    def test_hostname_inference(self, transformer: MetadataTransformer) -> None:
        """Test HOSTNAME suffix infers string type."""
        env_var = CasaOSEnvVar(name="SERVER_HOSTNAME", default="server", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "network"

    def test_url_inference(self, transformer: MetadataTransformer) -> None:
        """Test URL suffix infers string type."""
        env_var = CasaOSEnvVar(name="CALLBACK_URL", default="", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "network"

    def test_domain_inference(self, transformer: MetadataTransformer) -> None:
        """Test DOMAIN suffix infers string type."""
        env_var = CasaOSEnvVar(name="BASE_DOMAIN", default="example.com", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "network"

    def test_path_inference(self, transformer: MetadataTransformer) -> None:
        """Test PATH suffix infers path type."""
        env_var = CasaOSEnvVar(name="DATA_PATH", default="/data", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "path"
        assert group == "storage"

    def test_dir_inference(self, transformer: MetadataTransformer) -> None:
        """Test DIR suffix infers path type."""
        env_var = CasaOSEnvVar(name="CONFIG_DIR", default="/config", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "path"
        assert group == "storage"

    def test_directory_inference(self, transformer: MetadataTransformer) -> None:
        """Test DIRECTORY suffix infers path type."""
        env_var = CasaOSEnvVar(name="BACKUP_DIRECTORY", default="/backup", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "path"
        assert group == "storage"

    def test_folder_inference(self, transformer: MetadataTransformer) -> None:
        """Test FOLDER suffix infers path type."""
        env_var = CasaOSEnvVar(name="MEDIA_FOLDER", default="/media", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "path"
        assert group == "storage"

    def test_puid_inference(self, transformer: MetadataTransformer) -> None:
        """Test PUID infers integer type with UID validation."""
        env_var = CasaOSEnvVar(name="PUID", default="1000", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert validation.get("min") == 0
        assert validation.get("max") == 65535
        assert group == "system"

    def test_pgid_inference(self, transformer: MetadataTransformer) -> None:
        """Test PGID infers integer type with GID validation."""
        env_var = CasaOSEnvVar(name="PGID", default="1000", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert validation.get("min") == 0
        assert validation.get("max") == 65535
        assert group == "system"

    def test_tz_inference(self, transformer: MetadataTransformer) -> None:
        """Test TZ infers string type."""
        env_var = CasaOSEnvVar(name="TZ", default="UTC", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "system"

    def test_timezone_inference(self, transformer: MetadataTransformer) -> None:
        """Test TIMEZONE suffix infers string type."""
        env_var = CasaOSEnvVar(name="SERVER_TIMEZONE", default="UTC", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "system"

    def test_enable_inference(self, transformer: MetadataTransformer) -> None:
        """Test ENABLE suffix infers boolean type."""
        env_var = CasaOSEnvVar(name="FEATURE_ENABLE", default="false", type="boolean")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "boolean"
        assert group == "configuration"

    def test_enabled_inference(self, transformer: MetadataTransformer) -> None:
        """Test ENABLED suffix infers boolean type."""
        env_var = CasaOSEnvVar(name="LOGGING_ENABLED", default="true", type="boolean")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "boolean"
        assert group == "configuration"

    def test_disable_inference(self, transformer: MetadataTransformer) -> None:
        """Test DISABLE suffix infers boolean type."""
        env_var = CasaOSEnvVar(name="AUTH_DISABLE", default="false", type="boolean")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "boolean"
        assert group == "configuration"

    def test_debug_inference(self, transformer: MetadataTransformer) -> None:
        """Test DEBUG suffix infers boolean type."""
        env_var = CasaOSEnvVar(name="DEBUG", default="false", type="boolean")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "boolean"
        assert group == "configuration"

    def test_count_inference(self, transformer: MetadataTransformer) -> None:
        """Test COUNT suffix infers integer type."""
        env_var = CasaOSEnvVar(name="RETRY_COUNT", default="3", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert group == "configuration"

    def test_size_inference(self, transformer: MetadataTransformer) -> None:
        """Test SIZE suffix infers integer type."""
        env_var = CasaOSEnvVar(name="BUFFER_SIZE", default="1024", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert group == "configuration"

    def test_limit_inference(self, transformer: MetadataTransformer) -> None:
        """Test LIMIT suffix infers integer type."""
        env_var = CasaOSEnvVar(name="RATE_LIMIT", default="100", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert group == "configuration"

    def test_timeout_inference(self, transformer: MetadataTransformer) -> None:
        """Test TIMEOUT suffix infers integer type."""
        env_var = CasaOSEnvVar(name="REQUEST_TIMEOUT", default="30", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert group == "configuration"

    def test_username_inference(self, transformer: MetadataTransformer) -> None:
        """Test USERNAME suffix infers string type."""
        env_var = CasaOSEnvVar(name="DB_USERNAME", default="admin", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "authentication"

    def test_user_inference(self, transformer: MetadataTransformer) -> None:
        """Test USER suffix infers string type."""
        env_var = CasaOSEnvVar(name="ADMIN_USER", default="admin", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"
        assert group == "authentication"

    def test_pattern_precedence(self, transformer: MetadataTransformer) -> None:
        """Test that PORT pattern takes precedence over COUNT pattern."""
        # PORT should match before generic number patterns
        env_var = CasaOSEnvVar(name="SERVER_PORT", default="8080", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"
        assert validation.get("min") == 1024  # PORT validation, not generic integer
        assert group == "network"

    def test_fallback_to_casaos_type_number(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test fallback to CasaOS type hint for number."""
        env_var = CasaOSEnvVar(name="SOME_VALUE", default="42", type="number")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "integer"

    def test_fallback_to_casaos_type_text(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test fallback to CasaOS type hint for text."""
        env_var = CasaOSEnvVar(name="SOME_TEXT", default="value", type="text")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"

    def test_fallback_to_casaos_type_password(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test fallback to CasaOS type hint for password."""
        env_var = CasaOSEnvVar(name="SOME_SECRET_VALUE", default="", type="password")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "password"

    def test_fallback_to_casaos_type_boolean(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test fallback to CasaOS type hint for boolean."""
        env_var = CasaOSEnvVar(name="SOME_FLAG", default="true", type="boolean")
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "boolean"

    def test_fallback_to_string_when_no_type(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test fallback to string when no pattern matches and no type hint."""
        env_var = CasaOSEnvVar(name="RANDOM_VAR", default="value", type=None)
        field_type, validation, group = transformer._infer_field_type(env_var)

        assert field_type == "string"


class TestPathTransformation:
    """Test path transformation from CasaOS to HaLOS conventions."""

    def test_appdata_path_with_trailing_slash(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test /DATA/AppData/{app}/ transforms to ${CONTAINER_DATA_ROOT}/."""
        result = transformer._transform_path("/DATA/AppData/nginx/", "nginx")
        assert result == "${CONTAINER_DATA_ROOT}/"

    def test_appdata_path_without_trailing_slash(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test /DATA/AppData/{app} transforms to ${CONTAINER_DATA_ROOT}."""
        result = transformer._transform_path("/DATA/AppData/nginx", "nginx")
        assert result == "${CONTAINER_DATA_ROOT}"

    def test_appdata_path_with_subpath(self, transformer: MetadataTransformer) -> None:
        """Test /DATA/AppData/{app}/config transforms correctly."""
        result = transformer._transform_path("/DATA/AppData/nginx/config", "nginx")
        assert result == "${CONTAINER_DATA_ROOT}/config"

    def test_generic_data_prefix_removal(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test /DATA/ prefix is removed and media goes under CONTAINER_DATA_ROOT."""
        result = transformer._transform_path("/DATA/media", "app")
        assert result == "${CONTAINER_DATA_ROOT}/media"

    def test_config_directory(self, transformer: MetadataTransformer) -> None:
        """Test /config transforms to ${CONTAINER_DATA_ROOT}/config."""
        result = transformer._transform_path("/config", "app")
        assert result == "${CONTAINER_DATA_ROOT}/config"

    def test_data_directory(self, transformer: MetadataTransformer) -> None:
        """Test /data transforms to ${CONTAINER_DATA_ROOT}/data."""
        result = transformer._transform_path("/data", "app")
        assert result == "${CONTAINER_DATA_ROOT}/data"

    def test_media_directory_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /media transforms to ${CONTAINER_DATA_ROOT}/media."""
        result = transformer._transform_path("/media", "app")
        assert result == "${CONTAINER_DATA_ROOT}/media"

    def test_movies_directory(self, transformer: MetadataTransformer) -> None:
        """Test /movies transforms to ${CONTAINER_DATA_ROOT}/movies."""
        result = transformer._transform_path("/movies", "app")
        assert result == "${CONTAINER_DATA_ROOT}/movies"

    def test_tv_directory(self, transformer: MetadataTransformer) -> None:
        """Test /tv transforms to ${CONTAINER_DATA_ROOT}/tv."""
        result = transformer._transform_path("/tv", "app")
        assert result == "${CONTAINER_DATA_ROOT}/tv"

    def test_music_directory(self, transformer: MetadataTransformer) -> None:
        """Test /music transforms to ${CONTAINER_DATA_ROOT}/music."""
        result = transformer._transform_path("/music", "app")
        assert result == "${CONTAINER_DATA_ROOT}/music"

    def test_photos_directory(self, transformer: MetadataTransformer) -> None:
        """Test /photos transforms to ${CONTAINER_DATA_ROOT}/photos."""
        result = transformer._transform_path("/photos", "app")
        assert result == "${CONTAINER_DATA_ROOT}/photos"

    def test_books_directory(self, transformer: MetadataTransformer) -> None:
        """Test /books transforms to ${CONTAINER_DATA_ROOT}/books."""
        result = transformer._transform_path("/books", "app")
        assert result == "${CONTAINER_DATA_ROOT}/books"

    def test_downloads_directory_preserved(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test /downloads transforms to ${CONTAINER_DATA_ROOT}/downloads."""
        result = transformer._transform_path("/downloads", "app")
        assert result == "${CONTAINER_DATA_ROOT}/downloads"

    def test_etc_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /etc is preserved (system path)."""
        result = transformer._transform_path("/etc/nginx/nginx.conf", "app")
        assert result == "/etc/nginx/nginx.conf"

    def test_var_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /var is preserved (system path)."""
        result = transformer._transform_path("/var/log", "app")
        assert result == "/var/log"

    def test_usr_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /usr is preserved (system path)."""
        result = transformer._transform_path("/usr/share/data", "app")
        assert result == "/usr/share/data"

    def test_tmp_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /tmp is preserved (system path)."""
        result = transformer._transform_path("/tmp", "app")
        assert result == "/tmp"

    def test_dev_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /dev is preserved (system path)."""
        result = transformer._transform_path("/dev/null", "app")
        assert result == "/dev/null"

    def test_sys_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /sys is preserved (system path)."""
        result = transformer._transform_path("/sys", "app")
        assert result == "/sys"

    def test_proc_preserved(self, transformer: MetadataTransformer) -> None:
        """Test /proc is preserved (system path)."""
        result = transformer._transform_path("/proc", "app")
        assert result == "/proc"

    def test_unmapped_path_gets_data_root(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test unmapped paths get ${CONTAINER_DATA_ROOT} prepended."""
        result = transformer._transform_path("/custom/path", "app")
        assert result == "${CONTAINER_DATA_ROOT}/custom/path"

    def test_app_variable_substitution(self, transformer: MetadataTransformer) -> None:
        """Test {app} variable is replaced with app_id."""
        result = transformer._transform_path("/DATA/AppData/{app}/config", "myapp")
        assert result == "${CONTAINER_DATA_ROOT}/config"

    def test_app_id_variable_substitution(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test {app_id} variable is replaced with app_id."""
        result = transformer._transform_path("/DATA/AppData/{app_id}/config", "myapp")
        assert result == "${CONTAINER_DATA_ROOT}/config"

    def test_case_sensitivity_in_app_name(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test app name replacement is case-sensitive."""
        result = transformer._transform_path("/DATA/AppData/MyApp/config", "myapp")
        # Should not match because case doesn't match, but /DATA/ is still removed
        assert result == "${CONTAINER_DATA_ROOT}/AppData/MyApp/config"


class TestTransformerIntegration:
    """Integration tests for full transformation."""

    def test_transform_simple_app(
        self,
        transformer: MetadataTransformer,
        simple_casaos_app: CasaOSApp,
        conversion_context: ConversionContext,
    ) -> None:
        """Test full transformation of simple app."""
        result = transformer.transform(simple_casaos_app, conversion_context)

        # Check structure
        assert "metadata" in result
        assert "config" in result
        assert "compose" in result

        # Check metadata basics
        metadata = result["metadata"]
        assert metadata["name"] == "Nginx Test"
        assert metadata["app_id"] == "nginx-test"
        assert metadata["debian_section"] == "utils"  # Utilities → utils
        assert (
            metadata["description"] == "Web server"
        )  # Uses tagline for short description
        assert metadata["long_description"] == "Simple nginx web server for testing"

        # Check config structure
        config = result["config"]
        assert config["version"] == "1.0"
        assert "groups" in config
        assert len(config["groups"]) > 0

        # Check fields are present
        all_fields = []
        for group in config["groups"]:
            all_fields.extend(group["fields"])

        field_ids = [f["id"] for f in all_fields]
        assert "TZ" in field_ids
        assert "WEBUI_PORT" in field_ids

        # Check field types were inferred correctly
        tz_field = next(f for f in all_fields if f["id"] == "TZ")
        assert tz_field["type"] == "string"

        port_field = next(f for f in all_fields if f["id"] == "WEBUI_PORT")
        assert port_field["type"] == "integer"
        assert port_field.get("min") == 1024
        assert port_field.get("max") == 65535

        # Check compose is cleaned (no x-casaos)
        compose = result["compose"]
        assert "x-casaos" not in compose
        assert "services" in compose
        assert "nginx" in compose["services"]

        # Check paths were transformed
        nginx_service = compose["services"]["nginx"]
        volumes = nginx_service.get("volumes", [])
        assert len(volumes) > 0

        # Volume should have transformed path
        volume = volumes[0]
        if isinstance(volume, dict):
            source = volume.get("source", "")
        else:
            # String format "host:container"
            source = volume.split(":")[0] if ":" in volume else ""

        assert "${CONTAINER_DATA_ROOT}" in source or source.startswith("/")

    def test_validate_metadata_against_schema(
        self,
        transformer: MetadataTransformer,
        simple_casaos_app: CasaOSApp,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that generated metadata validates against PackageMetadata schema."""
        from schemas.metadata import PackageMetadata

        result = transformer.transform(simple_casaos_app, conversion_context)
        metadata = result["metadata"]

        # Add required fields that aren't in CasaOS
        metadata["maintainer"] = "HaLOS Team <halos@hatlabs.fi>"
        metadata["license"] = "MIT"
        metadata["tags"] = ["role::container-app"]
        metadata["version"] = "1.0.0"
        metadata["architecture"] = "all"

        # Should not raise validation error
        PackageMetadata.model_validate(metadata)

    def test_validate_config_against_schema(
        self,
        transformer: MetadataTransformer,
        simple_casaos_app: CasaOSApp,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that generated config validates against ConfigSchema schema."""
        from schemas.config import ConfigSchema

        result = transformer.transform(simple_casaos_app, conversion_context)
        config = result["config"]

        # Should not raise validation error
        ConfigSchema.model_validate(config)

    def test_warnings_collected_in_context(
        self,
        transformer: MetadataTransformer,
        simple_casaos_app: CasaOSApp,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that warnings are collected during transformation."""
        # Transform
        transformer.transform(simple_casaos_app, conversion_context)

        # Context should be updated
        # Warnings might be empty for a valid app, but the list should exist
        assert hasattr(conversion_context, "warnings")
        assert isinstance(conversion_context.warnings, list)

    def test_multi_service_app_handling(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test transformation of app with multiple services."""
        multi_service_app = CasaOSApp(
            id="app-with-db",
            name="App with Database",
            tagline="App and DB",
            description="Application with separate database service",
            category="Developer",
            services=[
                CasaOSService(
                    name="app",
                    image="myapp:latest",
                    environment=[
                        CasaOSEnvVar(name="DB_HOST", default="db", type="text"),
                    ],
                    ports=[CasaOSPort(container=3000, host=3000, protocol="tcp")],
                    volumes=[],
                ),
                CasaOSService(
                    name="db",
                    image="postgres:15",
                    environment=[
                        CasaOSEnvVar(
                            name="POSTGRES_PASSWORD", default="", type="password"
                        ),
                    ],
                    ports=[],
                    volumes=[
                        CasaOSVolume(
                            container="/var/lib/postgresql/data",
                            host="/DATA/AppData/app-with-db/db",
                            mode="rw",
                        )
                    ],
                ),
            ],
        )

        result = transformer.transform(multi_service_app, conversion_context)

        # Both services should be in compose
        assert "app" in result["compose"]["services"]
        assert "db" in result["compose"]["services"]

        # All environment variables should be in config
        all_fields = []
        for group in result["config"]["groups"]:
            all_fields.extend(group["fields"])

        field_ids = [f["id"] for f in all_fields]
        assert "DB_HOST" in field_ids
        assert "POSTGRES_PASSWORD" in field_ids

    def test_category_tag_added_to_metadata(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that category:: tag is added to metadata tags based on CasaOS category."""
        app = CasaOSApp(
            id="sonarr",
            name="Sonarr",
            tagline="TV show manager",
            description="Sonarr is a PVR for Usenet and BitTorrent users",
            category="Entertainment",
            services=[
                CasaOSService(
                    name="sonarr",
                    image="linuxserver/sonarr:4.0.15",
                    environment=[],
                    ports=[],
                    volumes=[],
                )
            ],
        )

        result = transformer.transform(app, conversion_context)

        # Category tag should be in metadata tags list
        assert "tags" in result["metadata"]
        assert "category::entertainment" in result["metadata"]["tags"]

    def test_category_tag_for_developer_category(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that Developer category generates category::development tag."""
        app = CasaOSApp(
            id="gitea",
            name="Gitea",
            tagline="Git with a cup of tea",
            description="Self-hosted Git service",
            category="Developer",
            services=[
                CasaOSService(
                    name="gitea",
                    image="gitea/gitea:1.21",
                    environment=[],
                    ports=[],
                    volumes=[],
                )
            ],
        )

        result = transformer.transform(app, conversion_context)

        assert "tags" in result["metadata"]
        assert "category::development" in result["metadata"]["tags"]

    def test_category_tag_for_monitoring_category(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that Monitoring category generates category::monitoring tag."""
        app = CasaOSApp(
            id="grafana",
            name="Grafana",
            tagline="Observability platform",
            description="Open-source analytics and monitoring",
            category="Monitoring",
            services=[
                CasaOSService(
                    name="grafana",
                    image="grafana/grafana:10.0.0",
                    environment=[],
                    ports=[],
                    volumes=[],
                )
            ],
        )

        result = transformer.transform(app, conversion_context)

        assert "tags" in result["metadata"]
        assert "category::monitoring" in result["metadata"]["tags"]

    def test_unknown_category_no_tag(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that unknown category does not add category:: tag."""
        app = CasaOSApp(
            id="custom-app",
            name="Custom App",
            tagline="Custom application",
            description="An app with unknown category",
            category="SomeUnknownCategory",
            services=[
                CasaOSService(
                    name="app",
                    image="myapp:1.0",
                    environment=[],
                    ports=[],
                    volumes=[],
                )
            ],
        )

        result = transformer.transform(app, conversion_context)

        # Tags list should exist but not contain any category:: tag
        tags = result["metadata"].get("tags", [])
        category_tags = [t for t in tags if t.startswith("category::")]
        assert len(category_tags) == 0


class TestVersionExtraction:
    """Test Docker image version extraction for issue #111."""

    def test_extract_standard_semantic_version(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test standard semantic version extraction."""
        assert (
            transformer._extract_version_from_image("linuxserver/sonarr:4.0.15")
            == "4.0.15"
        )
        assert transformer._extract_version_from_image("postgres:17.4") == "17.4"
        assert (
            transformer._extract_version_from_image("jellyfin/jellyfin:10.10.7")
            == "10.10.7"
        )
        assert (
            transformer._extract_version_from_image("portainer/portainer-ce:2.31.3")
            == "2.31.3"
        )

    def test_extract_version_with_v_prefix(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test v-prefix is stripped from version."""
        assert (
            transformer._extract_version_from_image("tailscale/tailscale:v1.90.8")
            == "1.90.8"
        )
        assert (
            transformer._extract_version_from_image("adguard/adguardhome:v0.107.61")
            == "0.107.61"
        )
        assert (
            transformer._extract_version_from_image("ghcr.io/gohugoio/hugo:v0.148.2")
            == "0.148.2"
        )

    def test_extract_version_with_suffix(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test version extraction with suffixes like -alpine."""
        assert (
            transformer._extract_version_from_image(
                "louislam/uptime-kuma:1.23.16-alpine"
            )
            == "1.23.16"
        )
        assert transformer._extract_version_from_image("postgres:15-alpine") == "15"
        assert transformer._extract_version_from_image("redis:6.2-alpine3.22") == "6.2"
        assert (
            transformer._extract_version_from_image("nginx:1.25.3-bookworm") == "1.25.3"
        )

    def test_extract_date_based_version(self, transformer: MetadataTransformer) -> None:
        """Test date-based version extraction."""
        assert (
            transformer._extract_version_from_image("photoprism/photoprism:250228")
            == "250228"
        )
        assert (
            transformer._extract_version_from_image("actualbudget/actual-server:25.7.1")
            == "25.7.1"
        )
        assert (
            transformer._extract_version_from_image("anaconda3:2024.10-1")
            == "2024.10-1"
        )

    def test_extract_version_with_digest(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test version extraction from image with digest reference."""
        assert (
            transformer._extract_version_from_image("redis:6.2-alpine@sha256:abc123def")
            == "6.2"
        )
        assert (
            transformer._extract_version_from_image("nginx:1.25@sha256:fedcba987")
            == "1.25"
        )

    def test_skip_latest_tag(self, transformer: MetadataTransformer) -> None:
        """Test that :latest tags are skipped (return None)."""
        assert (
            transformer._extract_version_from_image("homebridge/homebridge:latest")
            is None
        )
        assert transformer._extract_version_from_image("duckdns:latest") is None
        assert transformer._extract_version_from_image("excalidraw:latest") is None

    def test_skip_branch_tags(self, transformer: MetadataTransformer) -> None:
        """Test that branch tags are skipped (return None)."""
        assert transformer._extract_version_from_image("chatbot-ui:main") is None
        assert transformer._extract_version_from_image("medusa:master") is None
        assert transformer._extract_version_from_image("netdata/netdata:stable") is None
        assert transformer._extract_version_from_image("app:develop") is None
        assert transformer._extract_version_from_image("app:dev") is None

    def test_skip_no_tag(self, transformer: MetadataTransformer) -> None:
        """Test that images without tags are skipped (return None)."""
        assert transformer._extract_version_from_image("anythingllm") is None
        assert transformer._extract_version_from_image("myimage") is None

    def test_extract_version_with_registry(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test version extraction with full registry path."""
        assert (
            transformer._extract_version_from_image("ghcr.io/linuxserver/sonarr:4.0.15")
            == "4.0.15"
        )
        assert (
            transformer._extract_version_from_image("docker.io/library/postgres:15")
            == "15"
        )

    def test_extract_multi_digit_versions(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test extraction of multi-digit version numbers."""
        assert transformer._extract_version_from_image("app:10.20.30") == "10.20.30"
        assert (
            transformer._extract_version_from_image("app:v100.200.300") == "100.200.300"
        )

    def test_extract_prerelease_rc_versions(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test RC versions are converted to Debian format with tilde."""
        assert transformer._extract_version_from_image("app:1.2.3-rc1") == "1.2.3~rc1"
        assert transformer._extract_version_from_image("app:1.2.3-RC2") == "1.2.3~RC2"
        assert (
            transformer._extract_version_from_image("app:v2.0.0-rc.1") == "2.0.0~rc.1"
        )
        assert transformer._extract_version_from_image("app:1.0.0-rc") == "1.0.0~rc"

    def test_extract_prerelease_beta_alpha_versions(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test beta/alpha versions are converted to Debian format with tilde."""
        assert (
            transformer._extract_version_from_image("app:1.2.3-beta1") == "1.2.3~beta1"
        )
        assert (
            transformer._extract_version_from_image("app:1.2.3-beta.2")
            == "1.2.3~beta.2"
        )
        assert (
            transformer._extract_version_from_image("app:1.2.3-alpha1")
            == "1.2.3~alpha1"
        )
        assert transformer._extract_version_from_image("app:2.0.0-pre1") == "2.0.0~pre1"
        assert transformer._extract_version_from_image("app:1.5.0-dev") == "1.5.0~dev"

    def test_extract_version_numeric_suffix_preserved(
        self, transformer: MetadataTransformer
    ) -> None:
        """Test numeric suffixes are preserved (not treated as pre-release)."""
        # Date-based versions with numeric suffixes
        assert transformer._extract_version_from_image("app:2024.10-1") == "2024.10-1"
        assert transformer._extract_version_from_image("app:2024.11-2") == "2024.11-2"

    def test_transform_with_extracted_version(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that transform() extracts and sets version in metadata."""
        app = CasaOSApp(
            id="sonarr",
            name="Sonarr",
            tagline="TV show manager",
            description="Sonarr is a PVR for Usenet and BitTorrent users",
            category="Entertainment",
            services=[
                CasaOSService(
                    name="sonarr",
                    image="linuxserver/sonarr:4.0.15",
                    environment=[],
                    ports=[],
                    volumes=[],
                )
            ],
        )

        result = transformer.transform(app, conversion_context)

        # Version should be extracted from image tag
        assert result["metadata"]["version"] == "4.0.15"

        # Source metadata should track extraction
        assert result["metadata"]["source_metadata"] is None or (
            "version_source" not in result["metadata"].get("source_metadata", {})
            or result["metadata"]["source_metadata"]["version_source"]
            == "auto-extracted"
        )

    def test_transform_multi_service_app_uses_matching_service(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that multi-service app uses service matching app.id for version."""
        app = CasaOSApp(
            id="immich",
            name="Immich",
            tagline="Photo manager",
            description="Self-hosted photo and video backup solution",
            category="Entertainment",
            services=[
                CasaOSService(
                    name="immich-postgres",
                    image="postgres:15-alpine",
                    environment=[],
                    ports=[],
                    volumes=[],
                ),
                CasaOSService(
                    name="immich-server",
                    image="ghcr.io/immich-app/immich-server:v1.132.3",
                    environment=[],
                    ports=[],
                    volumes=[],
                ),
                CasaOSService(
                    name="immich-ml",
                    image="ghcr.io/immich-app/immich-machine-learning:v1.132.3",
                    environment=[],
                    ports=[],
                    volumes=[],
                ),
            ],
        )

        result = transformer.transform(app, conversion_context)

        # Should use immich-server (contains app.id) not postgres
        assert result["metadata"]["version"] == "1.132.3"

    def test_transform_multi_service_app_fallback_to_first(
        self,
        transformer: MetadataTransformer,
        conversion_context: ConversionContext,
    ) -> None:
        """Test that multi-service app falls back to first service if no name match."""
        app = CasaOSApp(
            id="myapp",
            name="My App",
            tagline="Test app",
            description="Test app with multiple services",
            category="Utilities",
            services=[
                CasaOSService(
                    name="web",
                    image="nginx:1.25.3",
                    environment=[],
                    ports=[],
                    volumes=[],
                ),
                CasaOSService(
                    name="db",
                    image="postgres:15",
                    environment=[],
                    ports=[],
                    volumes=[],
                ),
            ],
        )

        result = transformer.transform(app, conversion_context)

        # Should use first service (web/nginx) since no name contains "myapp"
        assert result["metadata"]["version"] == "1.25.3"
