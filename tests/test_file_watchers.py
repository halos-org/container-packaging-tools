"""Tests for file watcher support (systemd path units)."""

from pathlib import Path

import pytest

from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates
from generate_container_packages.template_context import (
    _build_file_watchers_context,
    build_context,
)
from generate_container_packages.validator import validate_input_directory
from schemas.metadata import FileWatcher, FileWatcherAction, PackageMetadata

VALID_FIXTURES = Path("tests/fixtures/valid")


class TestFileWatcherModels:
    """Tests for file watcher Pydantic models."""

    def test_file_watcher_action_restart_only(self):
        """Test FileWatcherAction with restart_service only."""
        action = FileWatcherAction(restart_service=True)
        assert action.restart_service is True
        assert action.script is None

    def test_file_watcher_action_script_only(self):
        """Test FileWatcherAction with script only."""
        action = FileWatcherAction(script="/usr/bin/reload-config")
        assert action.restart_service is False
        assert action.script == "/usr/bin/reload-config"

    def test_file_watcher_action_both(self):
        """Test FileWatcherAction with both restart_service and script."""
        action = FileWatcherAction(
            restart_service=True, script="/usr/bin/pre-reload-hook"
        )
        assert action.restart_service is True
        assert action.script == "/usr/bin/pre-reload-hook"

    def test_file_watcher_action_requires_at_least_one(self):
        """Test that FileWatcherAction requires at least one action."""
        with pytest.raises(ValueError, match="at least one of"):
            FileWatcherAction()

    def test_file_watcher_action_no_restart_no_script(self):
        """Test that FileWatcherAction fails with neither action."""
        with pytest.raises(ValueError, match="at least one of"):
            FileWatcherAction(restart_service=False, script=None)

    def test_file_watcher_valid(self):
        """Test valid FileWatcher configuration."""
        watcher = FileWatcher(
            name="config-reload",
            watch_path="/etc/myapp/config.d/",
            watch_type="directory_modified",
            on_change=FileWatcherAction(restart_service=True),
        )
        assert watcher.name == "config-reload"
        assert watcher.watch_path == "/etc/myapp/config.d/"
        assert watcher.watch_type == "directory_modified"

    def test_file_watcher_default_watch_type(self):
        """Test FileWatcher default watch_type is directory_modified."""
        watcher = FileWatcher(
            name="test",
            watch_path="/etc/test/",
            on_change=FileWatcherAction(restart_service=True),
        )
        assert watcher.watch_type == "directory_modified"

    def test_file_watcher_invalid_name(self):
        """Test FileWatcher rejects invalid names."""
        with pytest.raises(ValueError):
            FileWatcher(
                name="Invalid Name",  # Has spaces and uppercase
                watch_path="/etc/test/",
                on_change=FileWatcherAction(restart_service=True),
            )

    def test_file_watcher_name_with_hyphen(self):
        """Test FileWatcher accepts names with hyphens."""
        watcher = FileWatcher(
            name="config-reload-handler",
            watch_path="/etc/test/",
            on_change=FileWatcherAction(restart_service=True),
        )
        assert watcher.name == "config-reload-handler"

    def test_file_watcher_all_watch_types(self):
        """Test all valid watch_type values."""
        for watch_type in ["directory_modified", "path_changed", "path_exists"]:
            watcher = FileWatcher(
                name="test",
                watch_path="/etc/test/",
                watch_type=watch_type,
                on_change=FileWatcherAction(restart_service=True),
            )
            assert watcher.watch_type == watch_type

    def test_file_watcher_relative_path_rejected(self):
        """Test FileWatcher rejects relative paths."""
        with pytest.raises(ValueError, match="absolute path"):
            FileWatcher(
                name="test",
                watch_path="etc/test/",  # Relative path
                on_change=FileWatcherAction(restart_service=True),
            )

    def test_file_watcher_action_relative_script_rejected(self):
        """Test FileWatcherAction rejects relative script paths."""
        with pytest.raises(ValueError, match="absolute path"):
            FileWatcherAction(script="bin/reload-config")  # Relative path

    def test_file_watcher_action_absolute_script_accepted(self):
        """Test FileWatcherAction accepts absolute script paths."""
        action = FileWatcherAction(script="/usr/bin/reload-config")
        assert action.script == "/usr/bin/reload-config"


class TestDuplicateWatcherNames:
    """Tests for duplicate watcher name validation."""

    def test_duplicate_watcher_names_rejected(self):
        """Test that duplicate watcher names are rejected."""
        with pytest.raises(ValueError, match="Duplicate file_watcher names"):
            PackageMetadata(
                name="Test App",
                app_id="test-app",
                version="1.0.0",
                description="Test application",
                maintainer="Test <test@example.com>",
                license="MIT",
                tags=["role::container-app"],
                debian_section="net",
                architecture="all",
                file_watchers=[
                    FileWatcher(
                        name="config-reload",
                        watch_path="/etc/test/",
                        on_change=FileWatcherAction(restart_service=True),
                    ),
                    FileWatcher(
                        name="config-reload",  # Duplicate name
                        watch_path="/etc/other/",
                        on_change=FileWatcherAction(restart_service=True),
                    ),
                ],
            )

    def test_unique_watcher_names_accepted(self):
        """Test that unique watcher names are accepted."""
        metadata = PackageMetadata(
            name="Test App",
            app_id="test-app",
            version="1.0.0",
            description="Test application",
            maintainer="Test <test@example.com>",
            license="MIT",
            tags=["role::container-app"],
            debian_section="net",
            architecture="all",
            file_watchers=[
                FileWatcher(
                    name="config-reload",
                    watch_path="/etc/test/",
                    on_change=FileWatcherAction(restart_service=True),
                ),
                FileWatcher(
                    name="oidc-clients",
                    watch_path="/etc/other/",
                    on_change=FileWatcherAction(restart_service=True),
                ),
            ],
        )
        assert len(metadata.file_watchers) == 2


class TestFileWatchersContext:
    """Tests for file watchers template context building."""

    def test_build_file_watchers_context_none(self):
        """Test context with no file watchers."""
        result = _build_file_watchers_context(None)
        assert result == []

    def test_build_file_watchers_context_empty(self):
        """Test context with empty file watchers list."""
        result = _build_file_watchers_context([])
        assert result == []

    def test_build_file_watchers_context_single(self):
        """Test context with single file watcher."""
        watchers = [
            {
                "name": "config-reload",
                "watch_path": "/etc/myapp/",
                "watch_type": "directory_modified",
                "on_change": {"restart_service": True},
            }
        ]
        result = _build_file_watchers_context(watchers)

        assert len(result) == 1
        assert result[0]["name"] == "config-reload"
        assert result[0]["watch_path"] == "/etc/myapp/"
        assert result[0]["watch_type"] == "directory_modified"
        assert result[0]["restart_service"] is True
        assert result[0]["script"] is None

    def test_build_file_watchers_context_multiple(self):
        """Test context with multiple file watchers."""
        watchers = [
            {
                "name": "config-reload",
                "watch_path": "/etc/myapp/",
                "on_change": {"restart_service": True},
            },
            {
                "name": "oidc-clients",
                "watch_path": "/etc/halos/oidc-clients.d/",
                "watch_type": "path_changed",
                "on_change": {"script": "/usr/bin/reload-oidc"},
            },
        ]
        result = _build_file_watchers_context(watchers)

        assert len(result) == 2
        assert result[0]["name"] == "config-reload"
        assert result[0]["restart_service"] is True
        assert result[1]["name"] == "oidc-clients"
        assert result[1]["script"] == "/usr/bin/reload-oidc"


class TestFileWatchersLoading:
    """Tests for loading apps with file watchers."""

    def test_load_watcher_app(self):
        """Test loading watcher-app fixture."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        # Validate first
        result = validate_input_directory(fixture_dir)
        assert result.success, f"Validation failed: {result.errors}"

        # Load
        app_def = load_input_files(fixture_dir)

        # Verify file_watchers loaded
        assert "file_watchers" in app_def.metadata
        watchers = app_def.metadata["file_watchers"]
        assert len(watchers) == 3

        # Check first watcher
        assert watchers[0]["name"] == "config-reload"
        assert watchers[0]["watch_type"] == "directory_modified"
        assert watchers[0]["on_change"]["restart_service"] is True

    def test_build_context_with_file_watchers(self):
        """Test building template context with file watchers."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        context = build_context(app_def)

        assert context["has_file_watchers"] is True
        assert len(context["file_watchers"]) == 3

        # Check flattened structure
        watcher = context["file_watchers"][0]
        assert watcher["name"] == "config-reload"
        assert watcher["restart_service"] is True
        assert watcher["script"] is None


class TestFileWatchersRendering:
    """Tests for rendering file watcher templates."""

    def test_render_watcher_app(self, tmp_path):
        """Test rendering templates for watcher-app."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        debian_dir = tmp_path / "debian"

        # Verify main service exists
        assert (debian_dir / "watcher-test-app-container.service").exists()

        # Verify watcher path units
        assert (
            debian_dir / "watcher-test-app-container-watcher-config-reload.path"
        ).exists()
        assert (
            debian_dir / "watcher-test-app-container-watcher-oidc-clients.path"
        ).exists()
        assert (
            debian_dir / "watcher-test-app-container-watcher-combined-watcher.path"
        ).exists()

        # Verify watcher service units
        assert (
            debian_dir / "watcher-test-app-container-watcher-config-reload.service"
        ).exists()
        assert (
            debian_dir / "watcher-test-app-container-watcher-oidc-clients.service"
        ).exists()
        assert (
            debian_dir / "watcher-test-app-container-watcher-combined-watcher.service"
        ).exists()

    def test_path_unit_content(self, tmp_path):
        """Test content of rendered .path unit."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        path_file = (
            tmp_path
            / "debian"
            / "watcher-test-app-container-watcher-config-reload.path"
        )
        content = path_file.read_text()

        # Check unit structure
        assert "[Unit]" in content
        assert "[Path]" in content
        assert "[Install]" in content

        # Check watch directive (PathModified for directory_modified type)
        assert "PathModified=/etc/halos/watcher-app.d/" in content

        # Check unit reference
        assert (
            "Unit=watcher-test-app-container-watcher-config-reload.service" in content
        )

        # Check install target
        assert "WantedBy=watcher-test-app-container.service" in content

    def test_watcher_service_restart_only(self, tmp_path):
        """Test watcher service with restart_service only."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        service_file = (
            tmp_path
            / "debian"
            / "watcher-test-app-container-watcher-config-reload.service"
        )
        content = service_file.read_text()

        assert "Type=oneshot" in content
        assert (
            "ExecStart=/bin/systemctl restart watcher-test-app-container.service"
            in content
        )

    def test_watcher_service_script_only(self, tmp_path):
        """Test watcher service with script only."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        service_file = (
            tmp_path
            / "debian"
            / "watcher-test-app-container-watcher-oidc-clients.service"
        )
        content = service_file.read_text()

        assert "Type=oneshot" in content
        assert "ExecStart=/usr/bin/reload-oidc-clients" in content
        # Should NOT have ExecStartPost since no restart_service
        assert "ExecStartPost" not in content

    def test_watcher_service_script_and_restart(self, tmp_path):
        """Test watcher service with both script and restart_service."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        service_file = (
            tmp_path
            / "debian"
            / "watcher-test-app-container-watcher-combined-watcher.service"
        )
        content = service_file.read_text()

        assert "Type=oneshot" in content
        assert "ExecStart=/usr/bin/pre-reload-hook" in content
        assert (
            "ExecStartPost=/bin/systemctl restart watcher-test-app-container.service"
            in content
        )

    def test_rules_installs_watcher_units(self, tmp_path):
        """Test that rules.j2 installs watcher units."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        rules_file = tmp_path / "debian" / "rules"
        content = rules_file.read_text()

        # Check path unit installation
        assert "watcher-test-app-container-watcher-config-reload.path" in content
        assert "watcher-test-app-container-watcher-oidc-clients.path" in content

        # Check service unit installation
        assert "watcher-test-app-container-watcher-config-reload.service" in content

    def test_postinst_enables_and_starts_path_units(self, tmp_path):
        """Test that postinst enables and starts path units."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        postinst_file = tmp_path / "debian" / "postinst"
        content = postinst_file.read_text()

        # Check enable
        assert (
            "systemctl enable watcher-test-app-container-watcher-config-reload.path"
            in content
        )
        assert (
            "systemctl enable watcher-test-app-container-watcher-oidc-clients.path"
            in content
        )

        # Check start
        assert (
            "systemctl start watcher-test-app-container-watcher-config-reload.path"
            in content
        )
        assert (
            "systemctl start watcher-test-app-container-watcher-oidc-clients.path"
            in content
        )

    def test_prerm_stops_watcher_units(self, tmp_path):
        """Test that prerm stops path and service units."""
        fixture_dir = VALID_FIXTURES / "watcher-app"

        app_def = load_input_files(fixture_dir)
        render_all_templates(app_def, tmp_path)

        prerm_file = tmp_path / "debian" / "prerm"
        content = prerm_file.read_text()

        # Check path units stopped and disabled
        assert (
            "systemctl stop watcher-test-app-container-watcher-config-reload.path"
            in content
        )
        assert (
            "systemctl disable watcher-test-app-container-watcher-config-reload.path"
            in content
        )

        # Check watcher services also stopped
        assert (
            "systemctl stop watcher-test-app-container-watcher-config-reload.service"
            in content
        )


class TestNoFileWatchers:
    """Tests for apps without file watchers."""

    def test_simple_app_no_file_watchers(self, tmp_path):
        """Test that simple-app doesn't generate watcher files."""
        fixture_dir = VALID_FIXTURES / "simple-app"

        app_def = load_input_files(fixture_dir)
        context = build_context(app_def)

        assert context["has_file_watchers"] is False
        assert context["file_watchers"] == []

        render_all_templates(app_def, tmp_path)

        debian_dir = tmp_path / "debian"

        # No watcher files should exist
        watcher_files = list(debian_dir.glob("*-watcher-*.path"))
        assert len(watcher_files) == 0

        watcher_services = list(debian_dir.glob("*-watcher-*.service"))
        assert len(watcher_services) == 0
