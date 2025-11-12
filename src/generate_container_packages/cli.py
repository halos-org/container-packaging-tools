"""Command-line interface for generate-container-packages."""

import argparse
import logging
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from jinja2 import TemplateError
from pydantic import ValidationError

from generate_container_packages import __version__
from generate_container_packages.builder import BuildError, build_package
from generate_container_packages.loader import load_input_files
from generate_container_packages.renderer import render_all_templates
from generate_container_packages.validator import validate_input_directory

# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_TEMPLATE_ERROR = 2
EXIT_BUILD_ERROR = 3
EXIT_DEPENDENCY_ERROR = 4

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    # Configure logging based on verbosity
    setup_logging(args)

    try:
        # Convert input_dir to Path
        input_dir = Path(args.input_dir).resolve()

        if not input_dir.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return EXIT_VALIDATION_ERROR

        if not input_dir.is_dir():
            logger.error(f"Input path is not a directory: {input_dir}")
            return EXIT_VALIDATION_ERROR

        # Step 1: Validate input files
        logger.info(f"Validating input directory: {input_dir}")
        validation_result = validate_input_directory(input_dir)

        if not validation_result.success:
            logger.error("Validation failed.")
            print("\nERROR: Validation failed\n", file=sys.stderr)
            for error in validation_result.errors:
                print(f"  - {error}", file=sys.stderr)
            for warning in validation_result.warnings:
                print(f"  (warning) {warning.message}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        # Display warnings even on success
        for warning in validation_result.warnings:
            logger.warning(f"{warning.message}")

        logger.info("✓ Validation passed")

        if args.validate:
            print("Validation successful!")
            if validation_result.warnings:
                print("\nWarnings:")
                for warning in validation_result.warnings:
                    print(f"  - {warning.message}")
            return EXIT_SUCCESS

        # Check build dependencies only if actually building
        try:
            check_dependencies()
        except (ImportError, FileNotFoundError) as e:
            logger.error(f"Dependency check failed: {e}")
            print(f"\nERROR: {e}\n", file=sys.stderr)
            return EXIT_DEPENDENCY_ERROR

        # Step 2: Load input files
        logger.info("Loading input files...")
        app_def = load_input_files(input_dir)
        logger.info("✓ Files loaded")

        # Step 3: Render templates
        logger.info("Rendering templates...")
        rendered_dir = Path(tempfile.mkdtemp(prefix="render-"))

        try:
            render_all_templates(app_def, rendered_dir)
            logger.info("✓ Templates rendered")

            # Step 4: Build package
            output_dir = Path(args.output).resolve()
            logger.info(f"Building package (output: {output_dir})...")
            deb_file = build_package(app_def, rendered_dir, output_dir, keep_temp=args.keep_temp)
            logger.info(f"✓ Package built successfully: {deb_file}")

            # Success message
            pkg_name = app_def.metadata["package_name"]
            print(f"\nSuccess! Package generated: {deb_file.name}")
            print(f"  Package: {pkg_name}")
            print(f"  Version: {app_def.metadata['version']}")
            print(f"  Output: {output_dir}")

            return EXIT_SUCCESS
        finally:
            # Clean up temporary rendered directory
            if rendered_dir.exists():
                shutil.rmtree(rendered_dir)

    except ValidationError as e:
        logger.error("Validation failed:")
        print("\nERROR: Validation failed\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    except TemplateError as e:
        logger.error(f"Template rendering failed: {e}")
        print("\nERROR: Template rendering failed\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_TEMPLATE_ERROR

    except BuildError as e:
        logger.error(f"Package build failed: {e}")
        print("\nERROR: Package build failed\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_BUILD_ERROR

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        return EXIT_BUILD_ERROR

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print("\nERROR: Unexpected error\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        if args.debug or args.verbose:
            traceback.print_exc()
        return EXIT_BUILD_ERROR


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="generate-container-packages",
        description="Generate Debian packages from container application definitions",
        epilog="For more information, see the documentation.",
    )

    # Positional arguments
    parser.add_argument(
        "input_dir",
        metavar="INPUT_DIR",
        help="Directory containing application definition files",
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        metavar="DIR",
        default=".",
        help="Output directory for generated packages (default: current directory)",
    )

    # Validation options
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate input files only, do not build package",
    )

    # Verbosity options
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (show progress details)",
    )
    verbosity_group.add_argument(
        "--debug", action="store_true", help="Debug output (show all details)"
    )
    verbosity_group.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet mode (errors only)"
    )

    # Build options
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary build directory (useful for debugging)",
    )

    # Version
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on command-line arguments.

    Args:
        args: Parsed command-line arguments
    """
    if args.debug:
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    elif args.quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def check_dependencies() -> None:
    """Check that required system dependencies are available.

    Raises:
        ImportError: If required Python dependencies are missing
        FileNotFoundError: If required system tools are missing
    """
    # Check Python dependencies
    try:
        import jinja2  # noqa: F401
        import pydantic  # noqa: F401
        import yaml  # noqa: F401
    except ImportError as e:
        module_name = getattr(e, "name", None) or "unknown module"
        raise ImportError(
            f"Missing required Python dependency: {module_name}\nInstall with: pip install -e ."
        ) from e

    # Check system tools (dpkg-buildpackage)
    if not shutil.which("dpkg-buildpackage"):
        raise FileNotFoundError(
            "dpkg-buildpackage not found.\nInstall with: sudo apt install dpkg-dev debhelper"
        )


if __name__ == "__main__":
    sys.exit(main())
