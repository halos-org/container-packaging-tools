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

# Converter imports (lazy import to avoid dependency issues)
try:
    from generate_container_packages.converters.casaos.assets import AssetManager
    from generate_container_packages.converters.casaos.models import ConversionContext
    from generate_container_packages.converters.casaos.output import OutputWriter
    from generate_container_packages.converters.casaos.parser import CasaOSParser
    from generate_container_packages.converters.casaos.transformer import (
        MetadataTransformer,
    )
    from generate_container_packages.converters.casaos.updater import (
        CasaOSUpdateDetector,
    )

    CONVERTER_AVAILABLE = True
except ImportError:
    CONVERTER_AVAILABLE = False

# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_TEMPLATE_ERROR = 2
EXIT_BUILD_ERROR = 3
EXIT_DEPENDENCY_ERROR = 4

logger = logging.getLogger(__name__)


def convert_casaos_command(args: argparse.Namespace) -> int:
    """Execute convert-casaos subcommand.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    if not CONVERTER_AVAILABLE:
        logger.error(
            "CasaOS converter is not available. Please install required dependencies."
        )
        return EXIT_DEPENDENCY_ERROR

    try:
        # Validate arguments
        if args.sync and not args.batch:
            logger.error("--sync requires --batch mode")
            print("ERROR: --sync requires --batch mode", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        source_path = Path(args.source).resolve()
        output_dir = Path(args.output).resolve()

        # Check source exists
        if not source_path.exists():
            logger.error(f"Source does not exist: {source_path}")
            print(f"ERROR: Source does not exist: {source_path}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        # Determine mappings directory
        if args.mappings_dir:
            mappings_dir = Path(args.mappings_dir).resolve()
        else:
            # Use default mappings from package
            mappings_dir = Path(__file__).parent.parent.parent / "mappings" / "casaos"

        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize converter components
        parser = CasaOSParser()
        transformer = MetadataTransformer(mappings_dir)

        # Determine mode: batch or single
        if args.batch:
            return _convert_batch(
                source_path,
                output_dir,
                parser,
                transformer,
                args,
            )
        else:
            return _convert_single(
                source_path,
                output_dir,
                parser,
                transformer,
                args,
            )

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nERROR: {e}\n", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_BUILD_ERROR


def _convert_single(
    source_path: Path,
    output_dir: Path,
    parser: "CasaOSParser",
    transformer: "MetadataTransformer",
    args: argparse.Namespace,
) -> int:
    """Convert a single CasaOS app.

    Args:
        source_path: Path to docker-compose.yml or directory containing it
        output_dir: Output directory for converted app
        parser: CasaOS parser instance
        transformer: Metadata transformer instance
        args: Command-line arguments

    Returns:
        Exit code
    """
    try:
        # Determine input file
        if source_path.is_file():
            compose_file = source_path
        elif source_path.is_dir():
            compose_file = source_path / "docker-compose.yml"
            if not compose_file.exists():
                logger.error(f"docker-compose.yml not found in {source_path}")
                print(
                    f"ERROR: docker-compose.yml not found in {source_path}",
                    file=sys.stderr,
                )
                return EXIT_VALIDATION_ERROR
        else:
            logger.error(f"Invalid source: {source_path}")
            return EXIT_VALIDATION_ERROR

        logger.info(f"Converting {compose_file}...")

        # Parse CasaOS app
        casaos_app = parser.parse_from_file(compose_file)

        # Create conversion context
        context = ConversionContext(
            source_format="casaos",
            app_id=casaos_app.id,
            warnings=[],
            errors=[],
            downloaded_assets=[],
        )

        # Transform to HaLOS format
        transformed = transformer.transform(
            casaos_app,
            context,
            source_file_path=compose_file,
            source_url=args.upstream_url if hasattr(args, "upstream_url") else None,
        )

        # Enrich metadata with required fields that CasaOS doesn't provide
        metadata = transformed["metadata"]
        if "version" not in metadata or not metadata["version"]:
            metadata["version"] = "1.0.0"
        if "maintainer" not in metadata or not metadata["maintainer"]:
            # Format: "Name <email@domain.com>"
            dev_name = casaos_app.developer if casaos_app.developer else "Unknown"
            metadata["maintainer"] = f"{dev_name} <auto-converted@casaos.io>"
        if "license" not in metadata or not metadata["license"]:
            metadata["license"] = "Unknown"
        if "tags" not in metadata or not metadata["tags"]:
            # Must have at least one tag, and must include 'role::container-app'
            metadata["tags"] = casaos_app.tags if casaos_app.tags else []
        # Ensure role::container-app tag is always present
        if "role::container-app" not in metadata["tags"]:
            metadata["tags"].insert(0, "role::container-app")
        if "architecture" not in metadata or not metadata["architecture"]:
            # Must be single value from: 'all', 'amd64', 'arm64', 'armhf'
            metadata["architecture"] = "all"  # Default to all architectures

        # Write output files
        writer = OutputWriter(output_dir)
        writer.write_package(
            metadata,
            transformed["config"],
            transformed["compose"],
            context,
        )

        # Download assets if requested
        if args.download_assets:
            try:
                logger.info("Downloading assets...")
                asset_manager = AssetManager(output_dir / casaos_app.id)
                asset_manager.download_all_assets(casaos_app, context)
            except Exception as e:
                logger.warning(f"Asset download failed: {e}")
                context.warnings.append(f"Asset download failed: {e}")

        # Report results
        app_dir = output_dir / casaos_app.id
        print(f"\nSuccess! Converted app: {casaos_app.name}")
        print(f"  App ID: {casaos_app.id}")
        print(f"  Output: {app_dir}")

        if context.warnings:
            print(f"\nWarnings ({len(context.warnings)}):")
            for warning in context.warnings:
                print(f"  - {warning}")

        logger.info("✓ Conversion complete")
        return EXIT_SUCCESS

    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        print(f"\nERROR: Validation failed\n{e}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        print(f"\nERROR: Conversion failed: {e}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return EXIT_BUILD_ERROR


def _convert_batch(
    source_path: Path,
    output_dir: Path,
    parser: "CasaOSParser",
    transformer: "MetadataTransformer",
    args: argparse.Namespace,
) -> int:
    """Convert multiple CasaOS apps in batch mode.

    Args:
        source_path: Directory containing multiple app subdirectories
        output_dir: Output directory for converted apps
        parser: CasaOS parser instance
        transformer: Metadata transformer instance
        args: Command-line arguments

    Returns:
        Exit code
    """
    if not source_path.is_dir():
        logger.error("Batch mode requires a directory")
        print("ERROR: Batch mode requires a directory", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Handle sync mode
    if args.sync:
        return _convert_sync(source_path, output_dir, parser, transformer, args)

    # Find all apps (directories containing docker-compose.yml)
    app_dirs = [
        d
        for d in source_path.iterdir()
        if d.is_dir() and (d / "docker-compose.yml").exists()
    ]

    if not app_dirs:
        logger.warning(f"No apps found in {source_path}")
        print(f"No apps found in {source_path}")
        return EXIT_SUCCESS

    logger.info(f"Found {len(app_dirs)} apps to convert")
    print(f"Converting {len(app_dirs)} apps...")

    # Convert each app
    success_count = 0
    failure_count = 0

    for i, app_dir in enumerate(app_dirs, 1):
        logger.info(f"[{i}/{len(app_dirs)}] Converting {app_dir.name}...")
        if not args.quiet:
            print(f"[{i}/{len(app_dirs)}] {app_dir.name}...", end=" ")

        try:
            # Use _convert_single for each app
            result = _convert_single(app_dir, output_dir, parser, transformer, args)
            if result == EXIT_SUCCESS:
                success_count += 1
                if not args.quiet:
                    print("✓")
            else:
                failure_count += 1
                if not args.quiet:
                    print("✗")
        except Exception as e:
            failure_count += 1
            logger.error(f"Failed to convert {app_dir.name}: {e}")
            if not args.quiet:
                print(f"✗ ({e})")

    # Print summary
    print("\nBatch conversion complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed: {failure_count}")
    print(f"  Total: {len(app_dirs)}")

    return EXIT_SUCCESS if failure_count == 0 else EXIT_BUILD_ERROR


def _convert_sync(
    upstream_dir: Path,
    converted_dir: Path,
    parser: "CasaOSParser",
    transformer: "MetadataTransformer",
    args: argparse.Namespace,
) -> int:
    """Sync mode: detect and convert only new/updated apps.

    Args:
        upstream_dir: Directory with upstream CasaOS apps
        converted_dir: Directory with previously converted apps
        parser: CasaOS parser instance
        transformer: Metadata transformer instance
        args: Command-line arguments

    Returns:
        Exit code
    """
    logger.info("Running in sync mode - detecting changes...")

    # Use update detector
    detector = CasaOSUpdateDetector(upstream_dir, converted_dir)
    report = detector.detect_changes()

    # Print report
    print("\nSync Report:")
    print(f"  New apps: {len(report.new_apps)}")
    print(f"  Updated apps: {len(report.updated_apps)}")
    print(f"  Removed apps: {len(report.removed_apps)}")

    if not args.quiet:
        if report.new_apps:
            print("\nNew apps:")
            for app in report.new_apps:
                print(f"  + {app.app_id}")

        if report.updated_apps:
            print("\nUpdated apps:")
            for app in report.updated_apps:
                print(f"  ~ {app.app_id}")

        if report.removed_apps:
            print("\nRemoved apps:")
            for app in report.removed_apps:
                print(f"  - {app.app_id}")

    # Convert new and updated apps
    apps_to_convert = []

    for new_app in report.new_apps:
        apps_to_convert.append(upstream_dir / new_app.app_id)

    for updated_app in report.updated_apps:
        apps_to_convert.append(upstream_dir / updated_app.app_id)

    if not apps_to_convert:
        print("\nNo apps need conversion.")
        return EXIT_SUCCESS

    print(f"\nConverting {len(apps_to_convert)} apps...")

    # Convert each app
    success_count = 0
    failure_count = 0

    for i, app_dir in enumerate(apps_to_convert, 1):
        logger.info(f"[{i}/{len(apps_to_convert)}] Converting {app_dir.name}...")
        if not args.quiet:
            print(f"[{i}/{len(apps_to_convert)}] {app_dir.name}...", end=" ")

        try:
            result = _convert_single(app_dir, converted_dir, parser, transformer, args)
            if result == EXIT_SUCCESS:
                success_count += 1
                if not args.quiet:
                    print("✓")
            else:
                failure_count += 1
                if not args.quiet:
                    print("✗")
        except Exception as e:
            failure_count += 1
            logger.error(f"Failed to convert {app_dir.name}: {e}")
            if not args.quiet:
                print(f"✗ ({e})")

    # Print summary
    print("\nSync complete:")
    print(f"  Converted: {success_count}")
    print(f"  Failed: {failure_count}")

    return EXIT_SUCCESS if failure_count == 0 else EXIT_BUILD_ERROR


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Check if using convert-casaos subcommand
    # This allows backward compatibility with positional INPUT_DIR
    if len(sys.argv) > 1 and sys.argv[1] == "convert-casaos":
        parser = create_argument_parser()
        # Skip 'convert-casaos' from sys.argv when parsing
        args = parser.parse_args(sys.argv[2:])
        setup_logging(args)
        return convert_casaos_command(args)

    # Default behavior: build package (backward compatibility)
    parser = create_build_argument_parser()
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

            # Check build dependencies before building
            check_dependencies()

            # Step 4: Build package
            output_dir = Path(args.output).resolve()
            logger.info(f"Building package (output: {output_dir})...")
            deb_file = build_package(
                app_def, rendered_dir, output_dir, keep_temp=args.keep_temp
            )
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

    except (ImportError, FileNotFoundError) as e:
        logger.error(f"Dependency check failed: {e}")
        print(f"\nERROR: {e}\n", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR

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


def create_build_argument_parser() -> argparse.ArgumentParser:
    """Create argument parser for default build command (backward compatibility).

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
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    return parser


def create_argument_parser() -> argparse.ArgumentParser:
    """Create argument parser for convert-casaos subcommand.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="generate-container-packages convert-casaos",
        description="Convert CasaOS application definitions to HaLOS container store format",
    )

    parser.add_argument(
        "source",
        metavar="SOURCE",
        help="Source file or directory (docker-compose.yml or directory containing it)",
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="DIR",
        default="./converted",
        help="Output directory for converted apps (default: ./converted)",
    )

    parser.add_argument(
        "--mappings-dir",
        metavar="DIR",
        help="Custom mappings directory (optional)",
    )

    parser.add_argument(
        "--upstream-url",
        metavar="URL",
        help="Upstream repository URL for source tracking (optional)",
    )

    parser.add_argument(
        "--download-assets",
        action="store_true",
        help="Download icons and screenshots (default: skip)",
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode - convert multiple apps from directory",
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync mode - detect and convert only new/updated apps (requires --batch)",
    )

    # Verbosity options
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (show progress details)",
    )
    verbosity.add_argument(
        "--debug", action="store_true", help="Debug output (show all details)"
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet mode (errors only)"
    )

    # Version
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

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
