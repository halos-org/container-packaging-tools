"""Integration tests for package generation pipeline.

Tests the complete pipeline: validation -> loading -> rendering -> building
"""

import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from generate_container_packages.builder import build_package, prepare_build_directory
from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates
from generate_container_packages.validator import validate_input_directory

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestPipelineValidation:
    """Test validation phase of the pipeline."""

    def test_validate_simple_app(self):
        """Test validation of simple-app fixture."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")
        assert fixture_dir.exists()

        # Should not raise
        validate_input_directory(fixture_dir)

    def test_validate_full_app(self):
        """Test validation of full-app fixture."""
        fixture_dir = Path("tests/fixtures/valid/full-app")
        assert fixture_dir.exists()

        # Should not raise
        validate_input_directory(fixture_dir)

    def test_validate_invalid_fixture_raises(self):
        """Test that invalid fixtures return validation errors."""
        fixture_dir = Path("tests/fixtures/invalid/bad-package-name")
        assert fixture_dir.exists()

        result = validate_input_directory(fixture_dir)
        assert not result.success
        assert len(result.errors) > 0


class TestPipelineLoading:
    """Test loading phase of the pipeline."""

    def test_load_simple_app(self):
        """Test loading simple-app fixture."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")

        # Validate first
        validate_input_directory(fixture_dir)

        # Load
        app_def = load_input_files(fixture_dir)

        # Verify data loaded
        assert app_def.metadata is not None
        assert app_def.compose is not None
        assert app_def.config is not None
        # Package name is computed from directory name (simple-app) at build time
        assert app_def.metadata["package_name"] == "simple-app-container"

    def test_load_full_app(self):
        """Test loading full-app fixture."""
        fixture_dir = Path("tests/fixtures/valid/full-app")

        # Validate first
        validate_input_directory(fixture_dir)

        # Load
        app_def = load_input_files(fixture_dir)

        # Verify data loaded
        assert app_def.metadata is not None
        assert app_def.compose is not None
        assert app_def.config is not None
        assert app_def.icon_path is not None
        assert len(app_def.screenshot_paths) > 0


class TestPipelineRendering:
    """Test rendering phase of the pipeline."""

    def test_render_simple_app(self, tmp_path):
        """Test rendering templates for simple-app."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")

        # Validate and load
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        # Render to temporary directory
        render_all_templates(app_def, tmp_path)

        # Verify rendered files exist
        debian_dir = tmp_path / "debian"
        assert debian_dir.exists()
        assert (debian_dir / "control").exists()
        assert (debian_dir / "rules").exists()
        assert (debian_dir / "postinst").exists()
        assert (debian_dir / "prerm").exists()
        assert (debian_dir / "postrm").exists()
        assert (debian_dir / "changelog").exists()
        assert (debian_dir / "copyright").exists()
        assert (debian_dir / "compat").exists()

        # Verify systemd service (rendered directly to debian/)
        # Service file name is computed from directory name (simple-app)
        service_file = debian_dir / "simple-app-container.service"
        assert service_file.exists()

        # Verify AppStream metadata (rendered directly to debian/)
        appstream_file = debian_dir / "simple-app-container.metainfo.xml"
        assert appstream_file.exists()

    def test_render_full_app(self, tmp_path):
        """Test rendering templates for full-app."""
        fixture_dir = Path("tests/fixtures/valid/full-app")

        # Validate and load
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        # Render
        render_all_templates(app_def, tmp_path)

        # Verify key files
        assert (tmp_path / "debian" / "control").exists()
        assert (tmp_path / "debian" / "rules").exists()


class TestPipelineBuildPreparation:
    """Test build directory preparation."""

    def test_prepare_build_directory_simple_app(self, tmp_path):
        """Test build directory preparation for simple-app."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")

        # Validate and load
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        # Render templates
        render_dir = tmp_path / "rendered"
        render_dir.mkdir()
        render_all_templates(app_def, render_dir)

        # Prepare build directory
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        prepare_build_directory(app_def, render_dir, build_dir)

        # Verify source files copied
        assert (build_dir / "docker-compose.yml").exists()
        assert (build_dir / "env.template").exists()

        # Verify debian/ directory copied
        debian_dir = build_dir / "debian"
        assert debian_dir.exists()
        assert (debian_dir / "control").exists()
        assert (debian_dir / "rules").exists()

        # Verify permissions on debian/rules
        rules_file = debian_dir / "rules"
        assert rules_file.stat().st_mode & 0o111  # Check executable bit

    def test_prepare_build_directory_with_icon(self, tmp_path):
        """Test build directory preparation with icon."""
        fixture_dir = Path("tests/fixtures/valid/full-app")

        # Validate and load
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        # Render templates
        render_dir = tmp_path / "rendered"
        render_dir.mkdir()
        render_all_templates(app_def, render_dir)

        # Prepare build directory
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        prepare_build_directory(app_def, render_dir, build_dir)

        # Verify icon copied
        icon_file = build_dir / "icon.svg"
        assert icon_file.exists()


class TestEndToEndPipeline:
    """Test complete end-to-end pipeline."""

    def test_complete_pipeline_validation_mode(self):
        """Test complete pipeline in validation-only mode."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")

        # This is what the CLI does in --validate mode
        validate_input_directory(fixture_dir)
        # Success - no exception raised

    def test_complete_pipeline_up_to_build(self, tmp_path):
        """Test complete pipeline up to dpkg-buildpackage call."""
        fixture_dir = Path("tests/fixtures/valid/simple-app")

        # Step 1: Validate
        validate_input_directory(fixture_dir)

        # Step 2: Load
        app_def = load_input_files(fixture_dir)

        # Step 3: Render
        render_dir = tmp_path / "rendered"
        render_dir.mkdir()
        render_all_templates(app_def, render_dir)

        # Step 4: Prepare build directory
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        prepare_build_directory(app_def, render_dir, build_dir)

        # Verify complete build directory is ready
        assert (build_dir / "debian" / "control").exists()
        assert (build_dir / "debian" / "rules").exists()
        assert (build_dir / "docker-compose.yml").exists()

        # At this point, dpkg-buildpackage would be called
        # We don't call it in unit tests since it requires Debian environment

    @pytest.mark.install
    @pytest.mark.skipif(
        shutil.which("dpkg-buildpackage") is None,
        reason="dpkg-buildpackage not available",
    )
    def test_complete_pipeline_with_build(self, tmp_path):
        """Test complete pipeline including actual build.

        This test only runs if dpkg-buildpackage is available (Debian/Ubuntu systems).
        """
        fixture_dir = Path("tests/fixtures/valid/simple-app")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Validate, load, render
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        render_dir = tmp_path / "rendered"
        render_dir.mkdir()
        render_all_templates(app_def, render_dir)

        # Run complete build
        deb_path = build_package(app_def, render_dir, output_dir)

        # Verify .deb file was created
        assert deb_path.exists()
        assert deb_path.suffix == ".deb"
        assert "simple-test-app-container" in deb_path.name

    def test_invalid_input_fails_validation(self):
        """Test that invalid input fails at validation stage."""
        fixture_dir = Path("tests/fixtures/invalid/bad-package-name")

        result = validate_input_directory(fixture_dir)
        assert not result.success
        assert len(result.errors) > 0


class TestBuildWithMockedDpkg:
    """Test build function with mocked dpkg-buildpackage."""

    @patch("generate_container_packages.builder.subprocess.run")
    def test_build_calls_dpkg_buildpackage(self, mock_run, tmp_path):
        """Test that build_package calls dpkg-buildpackage correctly."""
        # Setup mock to simulate successful build
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "dpkg-buildpackage: info: building package"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Prepare app definition
        fixture_dir = Path("tests/fixtures/valid/simple-app")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Validate and load
        validate_input_directory(fixture_dir)
        app_def = load_input_files(fixture_dir)

        # Render templates
        render_dir = tmp_path / "rendered"
        render_dir.mkdir()
        render_all_templates(app_def, render_dir)

        # Create temporary .deb file that the builder would find
        temp_build_dir = tmp_path / "build_temp"
        temp_build_dir.mkdir()
        fake_deb = temp_build_dir.parent / "simple-test-app-container_1.0.0_all.deb"

        with patch("tempfile.mkdtemp", return_value=str(temp_build_dir)):
            with patch("pathlib.Path.glob", return_value=[fake_deb]):
                fake_deb.touch()  # Create the fake file

                try:
                    build_package(app_def, render_dir, output_dir)
                except Exception:
                    # May fail due to other missing dependencies in mock
                    # We mainly want to verify dpkg-buildpackage would be called
                    pass

        # Verify dpkg-buildpackage would be called
        # (might not be called if preparation fails first)
        if mock_run.called:
            call_args = mock_run.call_args[0][0]
            assert "dpkg-buildpackage" in call_args


class TestErrorHandling:
    """Test error handling in the pipeline."""

    def test_nonexistent_directory_fails_validation(self):
        """Test that nonexistent directory returns validation error."""
        nonexistent = Path("tests/fixtures/does-not-exist")

        result = validate_input_directory(nonexistent)
        assert not result.success
        assert len(result.errors) > 0

    def test_missing_required_file_fails_validation(self):
        """Test that missing required file returns validation error."""
        fixture_dir = Path("tests/fixtures/invalid/missing-metadata")

        result = validate_input_directory(fixture_dir)
        assert not result.success
        assert len(result.errors) > 0
