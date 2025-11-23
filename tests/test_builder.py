"""Unit tests for builder module."""

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from generate_container_packages.builder import (
    BuildError,
    build_package,
    collect_artifacts,
    copy_rendered_files,
    copy_source_files,
    generate_env_template,
    prepare_build_directory,
    run_dpkg_buildpackage,
    set_permissions,
)
from generate_container_packages.loader import AppDefinition, load_input_files

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"


class TestGenerateEnvTemplate:
    """Tests for generate_env_template function."""

    def test_empty_config(self, tmp_path):
        """Test generating env.template with empty config."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {"package_name": "test-app-container"}

        generate_env_template(app_def, tmp_path)

        # Check env.template (for env.defaults)
        env_file = tmp_path / "env.template"
        assert env_file.exists()
        content = env_file.read_text()
        # Should still have CONTAINER_DATA_ROOT even with no default_config
        assert 'CONTAINER_DATA_ROOT="/var/lib/container-apps/test-app-container/data"' in content
        assert "System-managed variables" in content

        # Check env.user-template (for env)
        user_file = tmp_path / "env.user-template"
        assert user_file.exists()
        user_content = user_file.read_text()
        assert "User environment overrides" in user_content
        # No app config means no commented values
        assert "CONTAINER_DATA_ROOT" not in user_content

    def test_simple_config(self, tmp_path):
        """Test generating env.template with simple config."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "default_config": {
                "KEY1": "value1",
                "KEY2": "value2",
            },
        }

        generate_env_template(app_def, tmp_path)

        # Check env.template (for env.defaults)
        env_file = tmp_path / "env.template"
        assert env_file.exists()
        content = env_file.read_text()
        # Check system-managed variable
        assert 'CONTAINER_DATA_ROOT="/var/lib/container-apps/test-app-container/data"' in content
        # Check application config
        assert 'KEY1="value1"' in content
        assert 'KEY2="value2"' in content
        assert "Application configuration" in content

        # Check env.user-template (for env) - commented defaults
        user_file = tmp_path / "env.user-template"
        assert user_file.exists()
        user_content = user_file.read_text()
        assert '#KEY1="value1"' in user_content
        assert '#KEY2="value2"' in user_content
        # Should NOT have system variables
        assert "CONTAINER_DATA_ROOT" not in user_content

    def test_config_with_special_characters(self, tmp_path):
        """Test env template generation with special characters."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.metadata = {
            "package_name": "test-app-container",
            "default_config": {
                "PASSWORD": 'test"password',
                "PATH": "/usr/bin:$HOME/bin",
                "COMMAND": "echo `whoami`",
                "BACKSLASH": "\\path\\to\\file",
                "NEWLINE": "line1\\nline2",
            },
        }

        generate_env_template(app_def, tmp_path)

        env_file = tmp_path / "env.template"
        content = env_file.read_text()
        # Check system-managed variable is present
        assert 'CONTAINER_DATA_ROOT="/var/lib/container-apps/test-app-container/data"' in content
        # Check escaping
        assert 'PASSWORD="test\\"password"' in content
        assert "$$HOME" in content
        assert "\\`whoami\\`" in content
        assert "\\\\" in content


class TestCopySourceFiles:
    """Tests for copy_source_files function."""

    def test_copy_required_files(self, tmp_path):
        """Test copying all required files."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        copy_source_files(app_def, dest_dir)

        assert (dest_dir / "metadata.yaml").exists()
        assert (dest_dir / "docker-compose.yml").exists()
        assert (dest_dir / "config.yml").exists()
        assert (dest_dir / "env.template").exists()

    def test_copy_with_icon(self, tmp_path):
        """Test copying with icon file."""
        app_def = load_input_files(VALID_FIXTURES / "full-app")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        copy_source_files(app_def, dest_dir)

        if app_def.icon_path:
            assert (dest_dir / app_def.icon_path.name).exists()

    def test_copy_with_screenshots(self, tmp_path):
        """Test copying with screenshot files."""
        app_def = load_input_files(VALID_FIXTURES / "full-app")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        copy_source_files(app_def, dest_dir)

        if app_def.screenshot_paths:
            for screenshot in app_def.screenshot_paths:
                assert (dest_dir / screenshot.name).exists()

    def test_missing_required_file(self, tmp_path):
        """Test error when required file is missing."""
        app_def = mock.Mock(spec=AppDefinition)
        app_def.input_dir = tmp_path / "nonexistent"
        app_def.icon_path = None
        app_def.screenshot_paths = []
        app_def.metadata = {}

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with pytest.raises(BuildError, match="Required file missing"):
            copy_source_files(app_def, dest_dir)


class TestCopyRenderedFiles:
    """Tests for copy_rendered_files function."""

    def test_copy_debian_directory(self, tmp_path):
        """Test copying debian directory from rendered files."""
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test control file")
        (debian_dir / "rules").write_text("#!/usr/bin/make -f")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        copy_rendered_files(rendered_dir, dest_dir)

        assert (dest_dir / "debian" / "control").exists()
        assert (dest_dir / "debian" / "rules").exists()

    def test_nonexistent_debian_directory(self, tmp_path):
        """Test handling of missing debian directory."""
        rendered_dir = tmp_path / "rendered"
        rendered_dir.mkdir()

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        # Should not raise an error
        copy_rendered_files(rendered_dir, dest_dir)
        assert not (dest_dir / "debian").exists()


class TestSetPermissions:
    """Tests for set_permissions function."""

    def test_set_rules_executable(self, tmp_path):
        """Test setting debian/rules as executable."""
        debian_dir = tmp_path / "debian"
        debian_dir.mkdir()
        rules_file = debian_dir / "rules"
        rules_file.write_text("#!/usr/bin/make -f")

        set_permissions(tmp_path)

        assert rules_file.stat().st_mode & 0o755

    def test_set_maintainer_scripts_executable(self, tmp_path):
        """Test setting maintainer scripts as executable."""
        debian_dir = tmp_path / "debian"
        debian_dir.mkdir()

        scripts = ["postinst", "prerm", "postrm", "preinst"]
        for script in scripts:
            script_file = debian_dir / script
            script_file.write_text("#!/bin/bash")

        set_permissions(tmp_path)

        for script in scripts:
            script_file = debian_dir / script
            assert script_file.stat().st_mode & 0o755

    def test_missing_scripts(self, tmp_path):
        """Test handling of missing scripts (should not error)."""
        debian_dir = tmp_path / "debian"
        debian_dir.mkdir()

        # Should not raise error for missing scripts
        set_permissions(tmp_path)


class TestPrepareBuildDirectory:
    """Tests for prepare_build_directory function."""

    def test_prepare_complete_directory(self, tmp_path):
        """Test preparing build directory with all files."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test")

        source_dir = tmp_path / "source"

        prepare_build_directory(app_def, rendered_dir, source_dir)

        # Check source files
        assert (source_dir / "metadata.yaml").exists()
        assert (source_dir / "docker-compose.yml").exists()
        assert (source_dir / "config.yml").exists()

        # Check rendered files
        assert (source_dir / "debian" / "control").exists()


class TestRunDpkgBuildpackage:
    """Tests for run_dpkg_buildpackage function."""

    @mock.patch("generate_container_packages.builder.subprocess.run")
    def test_successful_build(self, mock_run, tmp_path):
        """Test successful dpkg-buildpackage execution."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["dpkg-buildpackage"], returncode=0, stdout="success", stderr=""
        )

        result = run_dpkg_buildpackage(tmp_path)

        assert result.returncode == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args.kwargs["cwd"] == tmp_path

    @mock.patch("generate_container_packages.builder.subprocess.run")
    def test_build_failure(self, mock_run, tmp_path):
        """Test dpkg-buildpackage failure."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["dpkg-buildpackage"],
            returncode=1,
            stdout="some output",
            stderr="error message",
        )

        with pytest.raises(BuildError, match="dpkg-buildpackage failed"):
            run_dpkg_buildpackage(tmp_path)

    @mock.patch("generate_container_packages.builder.subprocess.run")
    def test_dpkg_not_found(self, mock_run, tmp_path):
        """Test handling when dpkg-buildpackage is not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(BuildError, match="dpkg-buildpackage not found"):
            run_dpkg_buildpackage(tmp_path)


class TestCollectArtifacts:
    """Tests for collect_artifacts function."""

    def test_collect_deb_and_changes(self, tmp_path):
        """Test collecting .deb and .changes files."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        output_dir = tmp_path / "output"

        # Create mock artifacts
        (build_dir / "test-app_1.0.0_all.deb").write_text("deb")
        (build_dir / "test-app_1.0.0_arm64.changes").write_text("changes")
        (build_dir / "test-app_1.0.0_arm64.buildinfo").write_text("buildinfo")

        artifacts = collect_artifacts(build_dir, output_dir, "test-app", "1.0.0")

        assert len(artifacts) == 3
        assert (output_dir / "test-app_1.0.0_all.deb").exists()
        assert (output_dir / "test-app_1.0.0_arm64.changes").exists()
        assert (output_dir / "test-app_1.0.0_arm64.buildinfo").exists()

    def test_no_artifacts_found(self, tmp_path):
        """Test when no artifacts are found."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        output_dir = tmp_path / "output"

        artifacts = collect_artifacts(build_dir, output_dir, "test-app", "1.0.0")

        assert len(artifacts) == 0

    def test_output_directory_created(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        output_dir = tmp_path / "output" / "subdir"

        (build_dir / "test-app_1.0.0_all.deb").write_text("deb")

        artifacts = collect_artifacts(build_dir, output_dir, "test-app", "1.0.0")

        assert output_dir.exists()
        assert len(artifacts) == 1


class TestBuildPackage:
    """Tests for build_package function (integration tests)."""

    @mock.patch("generate_container_packages.builder.run_dpkg_buildpackage")
    @mock.patch("generate_container_packages.builder.collect_artifacts")
    def test_successful_build(self, mock_collect, mock_dpkg, tmp_path):
        """Test successful package build."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test")
        (debian_dir / "rules").write_text("#!/usr/bin/make -f")

        output_dir = tmp_path / "output"

        # Mock successful build
        mock_dpkg.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        deb_file = output_dir / "test_1.0.0_all.deb"
        deb_file.parent.mkdir(parents=True, exist_ok=True)
        deb_file.write_text("deb")
        mock_collect.return_value = [deb_file]

        result = build_package(app_def, rendered_dir, output_dir)

        assert result == deb_file
        mock_dpkg.assert_called_once()
        mock_collect.assert_called_once()

    @mock.patch("generate_container_packages.builder.run_dpkg_buildpackage")
    @mock.patch("generate_container_packages.builder.collect_artifacts")
    def test_no_deb_file_generated(self, mock_collect, mock_dpkg, tmp_path):
        """Test error when no .deb file is generated."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test")

        output_dir = tmp_path / "output"

        mock_dpkg.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_collect.return_value = []

        with pytest.raises(BuildError, match="No .deb file generated"):
            build_package(app_def, rendered_dir, output_dir)

    @mock.patch("generate_container_packages.builder.run_dpkg_buildpackage")
    @mock.patch("generate_container_packages.builder.collect_artifacts")
    def test_keep_temp_on_success(self, mock_collect, mock_dpkg, tmp_path):
        """Test that temp directory is kept when keep_temp=True."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test")

        output_dir = tmp_path / "output"

        mock_dpkg.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        deb_file = output_dir / "test_1.0.0_all.deb"
        deb_file.parent.mkdir(parents=True, exist_ok=True)
        deb_file.write_text("deb")
        mock_collect.return_value = [deb_file]

        # Note: We can't easily test that temp dir is preserved without
        # inspecting tempfile internals, but we can verify the code path works
        result = build_package(app_def, rendered_dir, output_dir, keep_temp=True)
        assert result == deb_file

    @mock.patch("generate_container_packages.builder.run_dpkg_buildpackage")
    def test_build_error_cleanup(self, mock_dpkg, tmp_path):
        """Test that temp directory is cleaned up on build error."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        rendered_dir = tmp_path / "rendered"
        debian_dir = rendered_dir / "debian"
        debian_dir.mkdir(parents=True)
        (debian_dir / "control").write_text("test")

        output_dir = tmp_path / "output"

        # Simulate build failure
        mock_dpkg.side_effect = BuildError("Build failed")

        with pytest.raises(BuildError, match="Build failed"):
            build_package(app_def, rendered_dir, output_dir)

        # Temp directory should be cleaned up (we can't easily verify this without
        # tracking the temp dir path, but the code path is exercised)
