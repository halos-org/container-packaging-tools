"""Unit tests for template context builder."""

from pathlib import Path

import pytest

from generate_container_packages.loader import AppDefinition
from generate_container_packages.template_context import (
    _extract_volume_directories,
    _is_bindable_path,
    build_context,
    format_dependencies,
    format_long_description,
)


class TestBuildContext:
    """Tests for build_context function."""

    def test_minimal_app_context(self):
        """Test context building with minimal app definition."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "A test application",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=None,
            screenshot_paths=[],
        )

        context = build_context(app_def)

        # Verify package context
        assert context["package"]["name"] == "test-app-container"
        assert context["package"]["version"] == "1.0.0"
        assert context["package"]["human_name"] == "Test App"
        assert context["package"]["description"] == "A test application"
        assert context["package"]["architecture"] == "all"
        assert context["package"]["section"] == "net"
        assert context["package"]["maintainer"] == "Test <test@example.com>"
        assert context["package"]["license"] == "MIT"

        # Verify service context
        assert context["service"]["name"] == "test-app-container.service"
        assert context["service"]["description"] == "Test App Container"
        assert (
            context["service"]["working_directory"]
            == "/var/lib/container-apps/test-app-container"
        )
        assert (
            context["service"]["env_defaults_file"]
            == "/etc/container-apps/test-app-container/env.defaults"
        )
        assert (
            context["service"]["env_file"]
            == "/etc/container-apps/test-app-container/env"
        )

        # Verify paths
        assert context["paths"]["lib"] == "/var/lib/container-apps/test-app-container"
        assert context["paths"]["etc"] == "/etc/container-apps/test-app-container"
        assert context["paths"]["systemd"] == "/etc/systemd/system"

        # Verify optional fields
        assert context["has_icon"] is False
        assert context["icon_extension"] == ""
        assert context["has_screenshots"] is False

    def test_full_app_context_with_icon(self):
        """Test context building with all optional fields."""
        metadata = {
            "name": "Full Test App",
            "package_name": "full-test-app-container",
            "version": "2.1.0",
            "upstream_version": "2.1.3",
            "description": "A full-featured test application",
            "long_description": "This is a longer description.\n\nWith multiple paragraphs.",
            "homepage": "https://example.com",
            "maintainer": "Developer <dev@example.com>",
            "license": "Apache-2.0",
            "tags": ["role::container-app", "field::marine"],
            "debian_section": "web",
            "architecture": "all",
            "depends": ["docker.io", "python3"],
            "recommends": ["nginx"],
            "suggests": ["postgresql"],
            "web_ui": {"enabled": True, "path": "/admin", "port": 8080},
            "default_config": {"HTTP_PORT": "8080", "DEBUG": "false"},
        }

        icon_path = Path("/tmp/icon.svg")
        screenshot_paths = [Path("/tmp/screen1.png"), Path("/tmp/screen2.png")]

        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=icon_path,
            screenshot_paths=screenshot_paths,
        )

        context = build_context(app_def)

        # Verify optional fields
        assert context["package"]["homepage"] == "https://example.com"
        assert context["package"]["upstream_version"] == "2.1.3"
        assert "longer description" in context["package"]["long_description"]
        assert context["package"]["depends"] == "docker.io, python3"
        assert context["package"]["recommends"] == "nginx"
        assert context["package"]["suggests"] == "postgresql"
        assert context["package"]["tags"] == "role::container-app, field::marine"

        # Verify icon/screenshot flags
        assert context["has_icon"] is True
        assert context["icon_extension"] == "svg"
        assert context["has_screenshots"] is True
        assert context["screenshot_count"] == 2

        # Verify web_ui passed through
        assert context["web_ui"]["enabled"] is True
        assert context["web_ui"]["port"] == 8080

        # Verify default_config passed through
        assert context["default_config"]["HTTP_PORT"] == "8080"

    def test_png_icon_extension(self):
        """Test icon extension detection for PNG files."""
        metadata = {
            "name": "Test App",
            "package_name": "test-app-container",
            "version": "1.0.0",
            "description": "Test",
            "maintainer": "Test <test@example.com>",
            "license": "MIT",
            "tags": ["role::container-app"],
            "debian_section": "net",
            "architecture": "all",
        }

        icon_path = Path("/tmp/icon.png")
        app_def = AppDefinition(
            metadata=metadata,
            compose={},
            config={},
            input_dir=Path("/test/dir"),
            icon_path=icon_path,
        )

        context = build_context(app_def)

        assert context["has_icon"] is True
        assert context["icon_extension"] == "png"


class TestFormatLongDescription:
    """Tests for format_long_description function."""

    def test_empty_description(self):
        """Test formatting empty description."""
        result = format_long_description("")
        assert result == ""

    def test_single_line(self):
        """Test formatting single line description."""
        result = format_long_description("This is a single line.")
        assert result == " This is a single line."

    def test_multiple_lines(self):
        """Test formatting multi-line description."""
        text = "First line.\nSecond line.\nThird line."
        result = format_long_description(text)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == " First line."
        assert lines[1] == " Second line."
        assert lines[2] == " Third line."

    def test_empty_lines_become_dot(self):
        """Test that empty lines become single space-period."""
        text = "Paragraph one.\n\nParagraph two."
        result = format_long_description(text)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == " Paragraph one."
        assert lines[1] == " ."
        assert lines[2] == " Paragraph two."

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "  Line with spaces  \n  Another line  "
        result = format_long_description(text)

        lines = result.split("\n")
        assert lines[0] == " Line with spaces"
        assert lines[1] == " Another line"


class TestFormatDependencies:
    """Tests for format_dependencies function."""

    def test_none_dependencies(self):
        """Test formatting None dependencies."""
        result = format_dependencies(None)
        assert result == ""

    def test_empty_list(self):
        """Test formatting empty list."""
        result = format_dependencies([])
        assert result == ""

    def test_single_dependency(self):
        """Test formatting single dependency."""
        result = format_dependencies(["docker.io"])
        assert result == "docker.io"

    def test_multiple_dependencies(self):
        """Test formatting multiple dependencies."""
        result = format_dependencies(["docker.io", "python3", "nginx"])
        assert result == "docker.io, python3, nginx"


class TestIsBindablePath:
    """Tests for _is_bindable_path function."""

    def test_allows_env_var_container_data_root(self):
        """Test that paths with CONTAINER_DATA_ROOT are allowed."""
        assert _is_bindable_path("${CONTAINER_DATA_ROOT}/config")
        assert _is_bindable_path("${CONTAINER_DATA_ROOT}/data")
        assert _is_bindable_path("$CONTAINER_DATA_ROOT/media")

    def test_allows_env_var_home(self):
        """Test that paths with HOME are allowed."""
        assert _is_bindable_path("${HOME}/.config")
        assert _is_bindable_path("$HOME/data")

    def test_allows_env_var_user(self):
        """Test that paths with USER are allowed."""
        assert _is_bindable_path("${USER}/config")
        assert _is_bindable_path("$USER/data")

    def test_allows_absolute_paths(self):
        """Test that absolute paths are allowed."""
        assert _is_bindable_path("/opt/myapp/data")
        assert _is_bindable_path("/home/user/media")
        assert _is_bindable_path("/var/lib/container-apps/test/data")

    def test_rejects_named_volumes(self):
        """Test that named volumes (no slashes) are rejected."""
        assert not _is_bindable_path("my-volume")
        assert not _is_bindable_path("data_volume")
        assert not _is_bindable_path("nginx-config")

    def test_rejects_system_paths(self):
        """Test that system paths are rejected."""
        assert not _is_bindable_path("/dev/sda")
        assert not _is_bindable_path("/sys/class/gpio")
        assert not _is_bindable_path("/proc/cpuinfo")
        assert not _is_bindable_path("/run/docker.sock")
        assert not _is_bindable_path("/var/run/dbus/system_bus_socket")
        assert not _is_bindable_path("/tmp/cache")

    def test_rejects_path_traversal(self):
        """Test that path traversal attempts are rejected."""
        assert not _is_bindable_path("../etc/passwd")
        assert not _is_bindable_path("/opt/../../../etc/shadow")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/../../../tmp/evil")

    def test_rejects_unknown_env_vars(self):
        """Test that unknown environment variables are rejected."""
        assert not _is_bindable_path("${EVIL_PATH}/data")
        assert not _is_bindable_path("$RANDOM_VAR/config")
        assert not _is_bindable_path("${MALICIOUS}/files")

    def test_rejects_relative_paths(self):
        """Test that relative paths are rejected."""
        assert not _is_bindable_path("./data")
        assert not _is_bindable_path("config/files")

    def test_rejects_file_paths(self):
        """Test that paths ending with file extensions are rejected."""
        # Config file extensions
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/nginx.conf")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/settings.json")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/config.yaml")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/config.yml")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/settings.xml")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/app.toml")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/settings.ini")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/config.cfg")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/vars.env")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/readme.txt")
        # Socket and system files
        assert not _is_bindable_path("/var/lib/app/app.sock")
        assert not _is_bindable_path("/var/lib/app/app.socket")
        assert not _is_bindable_path("/var/lib/app/app.pid")
        assert not _is_bindable_path("/var/lib/app/app.log")
        # Case insensitive
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/Config.JSON")
        assert not _is_bindable_path("${CONTAINER_DATA_ROOT}/settings.YAML")

    def test_accepts_directory_paths(self):
        """Test that directory-like paths are still accepted."""
        # Paths without file extensions
        assert _is_bindable_path("${CONTAINER_DATA_ROOT}/config")
        assert _is_bindable_path("${CONTAINER_DATA_ROOT}/data")
        assert _is_bindable_path("${CONTAINER_DATA_ROOT}/logs")
        assert _is_bindable_path("/opt/myapp/storage")

    def test_accepts_hidden_directories(self):
        """Test that hidden directories (starting with .) are accepted."""
        # Hidden directories should be allowed, not mistaken for file extensions
        assert _is_bindable_path("${HOME}/.config")
        assert _is_bindable_path("${HOME}/.local")
        assert _is_bindable_path("${HOME}/.cache")
        assert _is_bindable_path("/opt/app/.data")


class TestExtractVolumeDirectories:
    """Tests for _extract_volume_directories function."""

    def test_short_format_volumes(self):
        """Test parsing short volume format (source:target)."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                        "${CONTAINER_DATA_ROOT}/data:/app/data:ro",
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert "${CONTAINER_DATA_ROOT}/data" in dirs
        assert len(dirs) == 2

    def test_long_format_volumes(self):
        """Test parsing long volume format (dict with type: bind)."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        {
                            "type": "bind",
                            "source": "${CONTAINER_DATA_ROOT}/config",
                            "target": "/app/config",
                        },
                        {
                            "type": "bind",
                            "source": "/opt/myapp/data",
                            "target": "/app/data",
                        },
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert "/opt/myapp/data" in dirs
        assert len(dirs) == 2

    def test_mixed_format_volumes(self):
        """Test parsing mix of short and long format volumes."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                        {
                            "type": "bind",
                            "source": "/opt/data",
                            "target": "/app/data",
                        },
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert "/opt/data" in dirs
        assert len(dirs) == 2

    def test_filters_named_volumes(self):
        """Test that named volumes are filtered out."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        "my-volume:/app/data",
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert len(dirs) == 1

    def test_filters_system_paths(self):
        """Test that system paths are filtered out."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        "/dev/sda:/dev/sda",
                        "/sys/class/gpio:/sys/class/gpio",
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert len(dirs) == 1

    def test_deduplicates_directories(self):
        """Test that duplicate directories are removed."""
        compose = {
            "services": {
                "app1": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/config:/app/config",
                    ]
                },
                "app2": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/config:/other/config",
                    ]
                },
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert len(dirs) == 1

    def test_multiple_services(self):
        """Test extraction from multiple services."""
        compose = {
            "services": {
                "web": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/web:/app/web",
                    ]
                },
                "db": {
                    "volumes": [
                        "${CONTAINER_DATA_ROOT}/db:/var/lib/db",
                    ]
                },
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/web" in dirs
        assert "${CONTAINER_DATA_ROOT}/db" in dirs
        assert len(dirs) == 2

    def test_empty_compose(self):
        """Test with empty compose file."""
        compose = {}
        dirs = _extract_volume_directories(compose)
        assert dirs == []

    def test_no_volumes(self):
        """Test with service that has no volumes."""
        compose = {
            "services": {
                "app": {
                    "image": "nginx",
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert dirs == []

    def test_long_format_non_bind_volumes(self):
        """Test that non-bind volume types are filtered."""
        compose = {
            "services": {
                "app": {
                    "volumes": [
                        {
                            "type": "volume",
                            "source": "my-volume",
                            "target": "/app/data",
                        },
                        {
                            "type": "bind",
                            "source": "${CONTAINER_DATA_ROOT}/config",
                            "target": "/app/config",
                        },
                    ]
                }
            }
        }
        dirs = _extract_volume_directories(compose)
        assert "${CONTAINER_DATA_ROOT}/config" in dirs
        assert len(dirs) == 1


class TestParseServiceUser:
    """Tests for _parse_service_user function."""

    def test_parse_numeric_user(self):
        """Test parsing numeric user field like '1000:1000'."""
        from generate_container_packages.template_context import _parse_service_user

        result = _parse_service_user("1000:1000")
        assert result is not None
        uid, gid = result
        assert uid == 1000
        assert gid == 1000

    def test_parse_different_uid_gid(self):
        """Test parsing different UID and GID."""
        from generate_container_packages.template_context import _parse_service_user

        result = _parse_service_user("472:0")
        assert result is not None
        uid, gid = result
        assert uid == 472
        assert gid == 0

    def test_parse_empty_user(self):
        """Test parsing empty/None user field (root)."""
        from generate_container_packages.template_context import _parse_service_user

        result = _parse_service_user(None)
        assert result is None

        result = _parse_service_user("")
        assert result is None

    def test_parse_uid_only(self):
        """Test parsing user with UID only (no GID)."""
        from generate_container_packages.template_context import _parse_service_user

        result = _parse_service_user("1000")
        assert result is not None
        uid, gid = result
        assert uid == 1000
        assert gid is None

    def test_invalid_user_colon_only(self):
        """Test that ':' (undefined env vars) raises error."""
        from generate_container_packages.template_context import (
            VolumeOwnershipError,
            _parse_service_user,
        )

        with pytest.raises(VolumeOwnershipError, match="undefined"):
            _parse_service_user(":")

    def test_invalid_user_empty_uid(self):
        """Test that ':1000' (empty UID) raises error."""
        from generate_container_packages.template_context import (
            VolumeOwnershipError,
            _parse_service_user,
        )

        with pytest.raises(VolumeOwnershipError, match="undefined"):
            _parse_service_user(":1000")

    def test_invalid_user_empty_gid(self):
        """Test that '1000:' (empty GID) raises error."""
        from generate_container_packages.template_context import (
            VolumeOwnershipError,
            _parse_service_user,
        )

        with pytest.raises(VolumeOwnershipError, match="undefined"):
            _parse_service_user("1000:")


class TestExtractVolumeOwnership:
    """Tests for volume ownership extraction from docker compose config."""

    def test_no_user_field_returns_none_ownership(self):
        """Test that services without user field get None ownership (root)."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "nginx",
                    "volumes": [
                        {"type": "bind", "source": "/data/app", "target": "/app"}
                    ],
                }
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 1
        assert volumes[0].path == "/data/app"
        assert volumes[0].uid is None
        assert volumes[0].gid is None

    def test_fixed_user_field(self):
        """Test extracting ownership from fixed user field."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "grafana": {
                    "image": "grafana/grafana",
                    "user": "472:0",
                    "volumes": [
                        {
                            "type": "bind",
                            "source": "/data/grafana",
                            "target": "/var/lib/grafana",
                        }
                    ],
                }
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 1
        assert volumes[0].path == "/data/grafana"
        assert volumes[0].uid == 472
        assert volumes[0].gid == 0

    def test_multi_service_different_users(self):
        """Test multiple services with different users."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": "1000:1000",
                    "volumes": [
                        {"type": "bind", "source": "/data/app", "target": "/app"}
                    ],
                },
                "db": {
                    "image": "postgres",
                    # No user field - runs as root
                    "volumes": [
                        {
                            "type": "bind",
                            "source": "/data/db",
                            "target": "/var/lib/postgresql",
                        }
                    ],
                },
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 2

        app_vol = next(v for v in volumes if v.path == "/data/app")
        assert app_vol.uid == 1000
        assert app_vol.gid == 1000

        db_vol = next(v for v in volumes if v.path == "/data/db")
        assert db_vol.uid is None
        assert db_vol.gid is None

    def test_invalid_user_raises_error(self):
        """Test that malformed user field raises error."""
        from generate_container_packages.template_context import (
            VolumeOwnershipError,
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": ":",  # Invalid - undefined env vars
                    "volumes": [
                        {"type": "bind", "source": "/data/app", "target": "/app"}
                    ],
                }
            }
        }

        with pytest.raises(VolumeOwnershipError):
            _extract_volume_ownership(compose_config)

    def test_short_format_volumes(self):
        """Test extracting ownership with short format volumes."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": "1000:1000",
                    "volumes": [
                        "/data/config:/app/config",
                        "/data/data:/app/data:rw",
                    ],
                }
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 2
        paths = [v.path for v in volumes]
        assert "/data/config" in paths
        assert "/data/data" in paths
        # All should have same ownership from service user
        for vol in volumes:
            assert vol.uid == 1000
            assert vol.gid == 1000

    def test_filters_system_paths(self):
        """Test that system paths are filtered out."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": "1000:1000",
                    "volumes": [
                        "/data/app:/app",
                        "/dev/sda:/dev/sda",
                        "/var/run/docker.sock:/var/run/docker.sock",
                    ],
                }
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 1
        assert volumes[0].path == "/data/app"

    def test_deduplicates_volumes(self):
        """Test that duplicate volumes are deduplicated."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app1": {
                    "image": "app1",
                    "user": "1000:1000",
                    "volumes": ["/data/shared:/app"],
                },
                "app2": {
                    "image": "app2",
                    "user": "1000:1000",
                    "volumes": ["/data/shared:/other"],
                },
            }
        }

        volumes = _extract_volume_ownership(compose_config)
        assert len(volumes) == 1
        assert volumes[0].path == "/data/shared"

    def test_env_var_substitution_in_user(self):
        """Test that env vars in user field are resolved from default_config."""
        from generate_container_packages.template_context import (
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": "${PUID}:${PGID}",
                    "volumes": ["/data/app:/app"],
                }
            }
        }
        default_config = {"PUID": "1000", "PGID": "1000"}

        volumes = _extract_volume_ownership(compose_config, default_config)
        assert len(volumes) == 1
        assert volumes[0].uid == 1000
        assert volumes[0].gid == 1000

    def test_env_var_substitution_missing_vars_raises_error(self):
        """Test that undefined env vars in user field raise error."""
        from generate_container_packages.template_context import (
            VolumeOwnershipError,
            _extract_volume_ownership,
        )

        compose_config = {
            "services": {
                "app": {
                    "image": "myapp",
                    "user": "${PUID}:${PGID}",  # Not in default_config
                    "volumes": ["/data/app:/app"],
                }
            }
        }

        with pytest.raises(VolumeOwnershipError, match="undefined"):
            _extract_volume_ownership(compose_config, {})


class TestVolumeInfo:
    """Tests for VolumeInfo dataclass."""

    def test_volume_info_creation(self):
        """Test creating VolumeInfo with all fields."""
        from generate_container_packages.template_context import VolumeInfo

        vol = VolumeInfo(path="/data/app", uid=1000, gid=1000)
        assert vol.path == "/data/app"
        assert vol.uid == 1000
        assert vol.gid == 1000

    def test_volume_info_none_ownership(self):
        """Test VolumeInfo with None ownership (root)."""
        from generate_container_packages.template_context import VolumeInfo

        vol = VolumeInfo(path="/data/app", uid=None, gid=None)
        assert vol.path == "/data/app"
        assert vol.uid is None
        assert vol.gid is None
