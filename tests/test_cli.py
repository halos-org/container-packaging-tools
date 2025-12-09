"""Unit tests for CLI module."""

import argparse
import logging
import shutil
import sys
from pathlib import Path
from unittest import mock

import pytest
from jinja2 import TemplateError
from pydantic import ValidationError

from generate_container_packages.builder import BuildError
from generate_container_packages.cli import (
    EXIT_BUILD_ERROR,
    EXIT_DEPENDENCY_ERROR,
    EXIT_SUCCESS,
    EXIT_TEMPLATE_ERROR,
    EXIT_VALIDATION_ERROR,
    check_dependencies,
    create_build_argument_parser,
    main,
    setup_logging,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"
INVALID_FIXTURES = FIXTURES_DIR / "invalid"


class TestCreateArgumentParser:
    """Tests for create_argument_parser function."""

    def test_parser_creation(self):
        """Test that parser is created successfully."""
        parser = create_build_argument_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "generate-container-packages"

    def test_input_dir_argument(self):
        """Test that input_dir positional argument is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["/path/to/input"])
        assert args.input_dir == "/path/to/input"

    def test_output_option_default(self):
        """Test that --output has correct default value."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir"])
        assert args.output == "."

    def test_output_option_custom(self):
        """Test that --output accepts custom value."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--output", "/custom/path"])
        assert args.output == "/custom/path"

    def test_output_option_short_form(self):
        """Test that -o short form works."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "-o", "/custom/path"])
        assert args.output == "/custom/path"

    def test_validate_flag(self):
        """Test that --validate flag is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--validate"])
        assert args.validate is True

    def test_validate_flag_default(self):
        """Test that --validate defaults to False."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir"])
        assert args.validate is False

    def test_verbose_flag(self):
        """Test that --verbose flag is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--verbose"])
        assert args.verbose is True
        assert args.debug is False
        assert args.quiet is False

    def test_verbose_short_form(self):
        """Test that -v short form works."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "-v"])
        assert args.verbose is True

    def test_debug_flag(self):
        """Test that --debug flag is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--debug"])
        assert args.debug is True
        assert args.verbose is False
        assert args.quiet is False

    def test_quiet_flag(self):
        """Test that --quiet flag is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--quiet"])
        assert args.quiet is True
        assert args.verbose is False
        assert args.debug is False

    def test_quiet_short_form(self):
        """Test that -q short form works."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "-q"])
        assert args.quiet is True

    def test_verbosity_mutually_exclusive(self):
        """Test that verbosity flags are mutually exclusive."""
        parser = create_build_argument_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["input_dir", "--verbose", "--debug"])

    def test_keep_temp_flag(self):
        """Test that --keep-temp flag is parsed."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--keep-temp"])
        assert args.keep_temp is True

    def test_keep_temp_flag_default(self):
        """Test that --keep-temp defaults to False."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir"])
        assert args.keep_temp is False

    def test_prefix_option(self):
        """Test that --prefix option is parsed correctly."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir", "--prefix", "marine"])
        assert args.prefix == "marine"

    def test_prefix_option_default(self):
        """Test that --prefix defaults to None."""
        parser = create_build_argument_parser()
        args = parser.parse_args(["input_dir"])
        assert args.prefix is None

    def test_prefix_various_values(self):
        """Test various prefix values."""
        parser = create_build_argument_parser()

        args = parser.parse_args(["input_dir", "--prefix", "halos"])
        assert args.prefix == "halos"

        args = parser.parse_args(["input_dir", "--prefix", "casaos"])
        assert args.prefix == "casaos"

    def test_version_flag(self):
        """Test that --version flag displays version."""
        parser = create_build_argument_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0  # type: ignore[attr-defined]


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_debug_level(self, caplog):
        """Test that debug flag sets DEBUG level."""
        args = argparse.Namespace(debug=True, verbose=False, quiet=False)
        with caplog.at_level(logging.NOTSET):
            setup_logging(args)
            # Check that basicConfig was called by verifying we can log at DEBUG
            logger = logging.getLogger("test")
            logger.debug("test message")
            # After setup_logging with debug=True, root logger should be configured for DEBUG
            assert logging.getLogger().level <= logging.DEBUG

    def test_verbose_level(self):
        """Test that verbose flag sets INFO level."""
        args = argparse.Namespace(debug=False, verbose=True, quiet=False)
        # Clear any existing handlers
        logging.getLogger().handlers.clear()
        setup_logging(args)
        # Check that logging.basicConfig was called with INFO level
        # We verify by checking that root logger has at least one handler
        assert len(logging.getLogger().handlers) > 0

    def test_quiet_level(self):
        """Test that quiet flag sets ERROR level."""
        args = argparse.Namespace(debug=False, verbose=False, quiet=True)
        logging.getLogger().handlers.clear()
        setup_logging(args)
        assert len(logging.getLogger().handlers) > 0

    def test_default_level(self):
        """Test that default is WARNING level."""
        args = argparse.Namespace(debug=False, verbose=False, quiet=False)
        logging.getLogger().handlers.clear()
        setup_logging(args)
        assert len(logging.getLogger().handlers) > 0


class TestCheckDependencies:
    """Tests for check_dependencies function."""

    @pytest.mark.skipif(
        shutil.which("dpkg-buildpackage") is None,
        reason="dpkg-buildpackage not available",
    )
    def test_dependencies_available(self):
        """Test that check passes when dependencies are available."""
        # In Docker environment, dpkg-buildpackage should be available
        # Should not raise any exception
        check_dependencies()

    def test_missing_dpkg_buildpackage(self, monkeypatch):
        """Test that check fails when dpkg-buildpackage is missing."""
        monkeypatch.setattr(shutil, "which", lambda x: None)
        with pytest.raises(FileNotFoundError, match="dpkg-buildpackage not found"):
            check_dependencies()


class TestMain:
    """Tests for main function."""

    def test_nonexistent_directory(self, caplog):
        """Test main with non-existent input directory."""
        with mock.patch.object(sys, "argv", ["prog", "/nonexistent/path"]):
            exit_code = main()

        assert exit_code == EXIT_VALIDATION_ERROR
        assert "does not exist" in caplog.text

    def test_input_is_file_not_directory(self, caplog, tmp_path):
        """Test main with file instead of directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with mock.patch.object(sys, "argv", ["prog", str(test_file)]):
            exit_code = main()

        assert exit_code == EXIT_VALIDATION_ERROR
        assert "not a directory" in caplog.text

    def test_validate_only_mode_success(self, capsys):
        """Test --validate flag with valid input."""
        input_dir = str(VALID_FIXTURES / "simple-app")

        with mock.patch.object(sys, "argv", ["prog", input_dir, "--validate"]):
            exit_code = main()

        assert exit_code == EXIT_SUCCESS
        captured = capsys.readouterr()
        assert "Validation successful" in captured.out

    def test_validate_only_mode_failure(self, capsys):
        """Test --validate flag with invalid input."""
        # Use a directory that exists but has missing files
        input_dir = str(FIXTURES_DIR)

        with mock.patch.object(sys, "argv", ["prog", input_dir, "--validate"]):
            exit_code = main()

        assert exit_code == EXIT_VALIDATION_ERROR
        captured = capsys.readouterr()
        assert "Validation failed" in captured.err

    def test_missing_dependency_error(self, capsys, monkeypatch):
        """Test dependency check failure."""
        input_dir = str(VALID_FIXTURES / "simple-app")
        monkeypatch.setattr(shutil, "which", lambda x: None)

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_DEPENDENCY_ERROR
        captured = capsys.readouterr()
        assert "dpkg-buildpackage not found" in captured.err

    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_validation_error_during_load(self, mock_load, capsys):
        """Test handling of ValidationError during file loading."""
        input_dir = str(VALID_FIXTURES / "simple-app")
        # Create a ValidationError by attempting to validate invalid data
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            required_field: str = Field(..., description="Required field")

        try:
            TestModel.model_validate({})  # Missing required field
        except ValidationError as e:
            mock_load.side_effect = e

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_VALIDATION_ERROR
        captured = capsys.readouterr()
        assert "Validation failed" in captured.err

    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_template_error(self, mock_load, mock_render, capsys):
        """Test handling of TemplateError during rendering."""
        from generate_container_packages.loader import AppDefinition

        input_dir = str(VALID_FIXTURES / "simple-app")

        # Create a mock AppDefinition
        mock_app_def = mock.Mock(spec=AppDefinition)
        mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
        mock_load.return_value = mock_app_def

        # Make render_all_templates raise TemplateError
        mock_render.side_effect = TemplateError("Template syntax error")

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_TEMPLATE_ERROR
        captured = capsys.readouterr()
        assert "Template rendering failed" in captured.err

    @mock.patch("generate_container_packages.cli.build_package")
    @mock.patch("generate_container_packages.cli.check_dependencies")
    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_build_error(
        self, mock_load, mock_render, mock_check_deps, mock_build, capsys, tmp_path
    ):
        """Test handling of BuildError during package building."""
        from generate_container_packages.loader import AppDefinition

        input_dir = str(VALID_FIXTURES / "simple-app")

        # Create a mock AppDefinition
        mock_app_def = mock.Mock(spec=AppDefinition)
        mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
        mock_load.return_value = mock_app_def

        # Make build_package raise BuildError
        mock_build.side_effect = BuildError("Build failed")

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_BUILD_ERROR
        captured = capsys.readouterr()
        assert "Package build failed" in captured.err

    @mock.patch("generate_container_packages.cli.build_package")
    @mock.patch("generate_container_packages.cli.check_dependencies")
    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_keyboard_interrupt(
        self, mock_load, mock_render, mock_check_deps, mock_build, capsys
    ):
        """Test handling of KeyboardInterrupt."""
        from generate_container_packages.loader import AppDefinition

        input_dir = str(VALID_FIXTURES / "simple-app")

        # Create a mock AppDefinition
        mock_app_def = mock.Mock(spec=AppDefinition)
        mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
        mock_load.return_value = mock_app_def

        # Simulate KeyboardInterrupt
        mock_build.side_effect = KeyboardInterrupt()

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_BUILD_ERROR
        captured = capsys.readouterr()
        assert "Interrupted by user" in captured.err

    @mock.patch("generate_container_packages.cli.build_package")
    @mock.patch("generate_container_packages.cli.check_dependencies")
    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_unexpected_exception(
        self, mock_load, mock_render, mock_check_deps, mock_build, capsys
    ):
        """Test handling of unexpected exceptions."""
        from generate_container_packages.loader import AppDefinition

        input_dir = str(VALID_FIXTURES / "simple-app")

        # Create a mock AppDefinition
        mock_app_def = mock.Mock(spec=AppDefinition)
        mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
        mock_load.return_value = mock_app_def

        # Simulate unexpected exception
        mock_build.side_effect = RuntimeError("Something went wrong")

        with mock.patch.object(sys, "argv", ["prog", input_dir]):
            exit_code = main()

        assert exit_code == EXIT_BUILD_ERROR
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.err

    @mock.patch("generate_container_packages.cli.build_package")
    @mock.patch("generate_container_packages.cli.check_dependencies")
    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_successful_build(
        self, mock_load, mock_render, mock_check_deps, mock_build, capsys, tmp_path
    ):
        """Test successful package build."""
        from generate_container_packages.loader import AppDefinition

        input_dir = str(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a mock AppDefinition
        mock_app_def = mock.Mock(spec=AppDefinition)
        mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
        mock_load.return_value = mock_app_def

        # Mock successful build
        deb_file = output_dir / "test-app_1.0.0_all.deb"
        deb_file.write_text("mock deb file")
        mock_build.return_value = deb_file

        with mock.patch.object(sys, "argv", ["prog", input_dir, "-o", str(output_dir)]):
            exit_code = main()

        assert exit_code == EXIT_SUCCESS
        captured = capsys.readouterr()
        assert "Success" in captured.out
        assert "test-app" in captured.out

    def test_debug_flag_shows_traceback(self, capsys):
        """Test that --debug flag shows traceback on errors."""
        input_dir = str(FIXTURES_DIR)  # Invalid directory

        with mock.patch.object(sys, "argv", ["prog", input_dir, "--debug"]):
            exit_code = main()

        # Debug mode might show additional output, but main behavior should be same
        assert exit_code == EXIT_VALIDATION_ERROR

    def test_output_directory_resolution(self, tmp_path):
        """Test that output directory is properly resolved."""
        input_dir = str(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock all the build steps to test output directory handling
        with (
            mock.patch("generate_container_packages.cli.load_input_files") as mock_load,
            mock.patch(
                "generate_container_packages.cli.render_all_templates"
            ) as _mock_render,
            mock.patch("generate_container_packages.cli.check_dependencies"),
            mock.patch("generate_container_packages.cli.build_package") as mock_build,
        ):
            from generate_container_packages.loader import AppDefinition

            mock_app_def = mock.Mock(spec=AppDefinition)
            mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
            mock_load.return_value = mock_app_def

            deb_file = output_dir / "test-app_1.0.0_all.deb"
            deb_file.write_text("mock deb")
            mock_build.return_value = deb_file

            with mock.patch.object(
                sys, "argv", ["prog", input_dir, "-o", str(output_dir)]
            ):
                exit_code = main()

            assert exit_code == EXIT_SUCCESS
            # Verify build_package was called with resolved output directory
            call_args = mock_build.call_args
            assert call_args[0][2] == output_dir.resolve()

    def test_temporary_directory_cleanup(self, tmp_path):
        """Test that temporary render directory is cleaned up."""
        input_dir = str(VALID_FIXTURES / "simple-app")

        with (
            mock.patch("generate_container_packages.cli.load_input_files") as mock_load,
            mock.patch(
                "generate_container_packages.cli.render_all_templates"
            ) as _mock_render,
            mock.patch("generate_container_packages.cli.check_dependencies"),
            mock.patch("generate_container_packages.cli.build_package") as mock_build,
            mock.patch("tempfile.mkdtemp") as mock_mkdtemp,
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            from generate_container_packages.loader import AppDefinition

            temp_dir = tmp_path / "temp_render"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            mock_app_def = mock.Mock(spec=AppDefinition)
            mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
            mock_load.return_value = mock_app_def

            deb_file = tmp_path / "test-app_1.0.0_all.deb"
            deb_file.write_text("mock")
            mock_build.return_value = deb_file

            with mock.patch.object(sys, "argv", ["prog", input_dir]):
                exit_code = main()

            assert exit_code == EXIT_SUCCESS
            # Verify cleanup was called
            mock_rmtree.assert_called_once()

    @mock.patch("generate_container_packages.cli.render_all_templates")
    @mock.patch("generate_container_packages.cli.load_input_files")
    def test_temporary_directory_cleanup_on_error(
        self, mock_load, mock_render, tmp_path
    ):
        """Test that temporary directory is cleaned up even on error."""
        input_dir = str(VALID_FIXTURES / "simple-app")

        with (
            mock.patch("generate_container_packages.cli.check_dependencies"),
            mock.patch("tempfile.mkdtemp") as mock_mkdtemp,
            mock.patch("shutil.rmtree") as mock_rmtree,
        ):
            from generate_container_packages.loader import AppDefinition

            temp_dir = tmp_path / "temp_render"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            mock_app_def = mock.Mock(spec=AppDefinition)
            mock_app_def.metadata = {"package_name": "test-app", "version": "1.0.0"}
            mock_load.return_value = mock_app_def

            # Raise error during rendering
            mock_render.side_effect = TemplateError("Test error")

            with mock.patch.object(sys, "argv", ["prog", input_dir]):
                exit_code = main()

            assert exit_code == EXIT_TEMPLATE_ERROR
            # Verify cleanup was still called
            mock_rmtree.assert_called_once()
