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
# Note: These imports are wrapped in try/except to gracefully handle cases where
# converter dependencies (e.g., Pillow for image processing) are not installed.
# The convert-casaos subcommand checks CONVERTER_AVAILABLE and fails gracefully
# if dependencies are missing. This allows the main build command to work without
# converter dependencies installed.
#
# String literal type hints ("CasaOSParser") are used throughout to avoid requiring
# these imports for type checking, at the cost of reduced IDE support.
try:
    from generate_container_packages.converters.casaos.assets import AssetManager
    from generate_container_packages.converters.casaos.batch import BatchConverter
    from generate_container_packages.converters.casaos.constants import (
        DEFAULT_ARCHITECTURE,
        DEFAULT_LICENSE,
        DEFAULT_MAINTAINER_DOMAIN,
        DEFAULT_VERSION,
        REQUIRED_ROLE_TAG,
    )
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


def _enrich_metadata(metadata: dict, casaos_app: "CasaOSApp") -> None:  # noqa: F821
    """Enrich metadata with required fields that CasaOS doesn't provide.

    CasaOS app definitions often lack required HaLOS metadata fields.
    This function adds sensible defaults for missing required fields.

    Args:
        metadata: Metadata dictionary to enrich (modified in-place)
        casaos_app: Parsed CasaOS application data

    Fields enriched:
        - version: Defaults to DEFAULT_VERSION if missing
        - maintainer: Generated from developer name with default domain
        - license: Defaults to DEFAULT_LICENSE if missing
        - tags: Ensures REQUIRED_ROLE_TAG is present
        - architecture: Defaults to DEFAULT_ARCHITECTURE if missing
    """
    if "version" not in metadata or not metadata["version"]:
        metadata["version"] = DEFAULT_VERSION

    if "maintainer" not in metadata or not metadata["maintainer"]:
        # Format: "Name <email@domain.com>"
        dev_name = casaos_app.developer if casaos_app.developer else "Unknown"
        metadata["maintainer"] = f"{dev_name} <{DEFAULT_MAINTAINER_DOMAIN}>"

    if "license" not in metadata or not metadata["license"]:
        metadata["license"] = DEFAULT_LICENSE

    if "tags" not in metadata or not metadata["tags"]:
        # Must have at least one tag, and must include REQUIRED_ROLE_TAG
        metadata["tags"] = casaos_app.tags if casaos_app.tags else []

    # Ensure role::container-app tag is always present
    if REQUIRED_ROLE_TAG not in metadata["tags"]:
        metadata["tags"].insert(0, REQUIRED_ROLE_TAG)

    if "architecture" not in metadata or not metadata["architecture"]:
        # Must be single value from: 'all', 'amd64', 'arm64', 'armhf'
        metadata["architecture"] = DEFAULT_ARCHITECTURE


def convert_casaos_command(args: argparse.Namespace) -> int:
    """Execute convert-casaos subcommand.

    Converts CasaOS application definitions to HaLOS container store format.
    Supports single app conversion, batch mode, and sync mode with update detection.

    Args:
        args: Parsed command-line arguments with attributes:
            - source: Path to docker-compose.yml or directory
            - output: Output directory path
            - batch: Enable batch conversion mode
            - sync: Enable sync/update detection mode
            - download_assets: Download icons and screenshots
            - mappings_dir: Custom mappings directory
            - upstream_url: Source URL for tracking

    Returns:
        Exit code (0 for success, non-zero for errors)

    Examples:
        Single file conversion:
            args.source = "app/docker-compose.yml"
            args.output = "./converted"

        Batch conversion:
            args.source = "apps/"
            args.batch = True
            args.output = "./converted"

        Sync mode (update detection):
            args.source = "upstream/"
            args.batch = True
            args.sync = True
            args.output = "./converted"
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
            from generate_container_packages.converters.casaos.constants import (
                get_default_mappings_dir,
            )

            mappings_dir = get_default_mappings_dir()

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
        _enrich_metadata(metadata, casaos_app)

        # Write output files (create app-specific subdirectory)
        app_output_dir = output_dir / casaos_app.id
        writer = OutputWriter(app_output_dir)
        writer.write_package(
            metadata,
            transformed["config"],
            transformed["compose"],
            context,
        )

        # Download assets if requested
        # Note: Asset download failures are non-fatal - they generate warnings
        # but don't fail the conversion. This is intentional because:
        # 1. Assets (icons/screenshots) are supplementary, not required
        # 2. Network issues shouldn't block otherwise valid conversions
        # 3. Missing assets can be added later manually if needed
        # The user is informed via warning messages in the output.
        if args.download_assets:
            try:
                logger.info("Downloading assets...")
                asset_manager = AssetManager(app_output_dir)
                asset_manager.download_all_assets(casaos_app, context)
            except Exception as e:
                logger.warning(f"Asset download failed: {e}")
                context.warnings.append(f"Asset download failed: {e}")

        # Report results
        print(f"\nSuccess! Converted app: {casaos_app.name}")
        print(f"  App ID: {casaos_app.id}")
        print(f"  Output: {app_output_dir}")

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

    Batch mode processes all apps in the source directory, continuing even if
    individual apps fail. The final exit code indicates whether ANY failures
    occurred, but all convertible apps will be processed.

    Failure Behavior:
        - Individual app failures are logged and counted
        - Conversion continues with remaining apps
        - Exit code is non-zero if any app failed
        - Summary shows success/failure counts

    This "continue on error" behavior is intentional for large batch operations
    where you want to convert as many apps as possible. If strict fail-fast
    behavior is needed, process apps individually.

    Args:
        source_path: Directory containing multiple app subdirectories
        output_dir: Output directory for converted apps
        parser: CasaOS parser instance
        transformer: Metadata transformer instance
        args: Command-line arguments

    Returns:
        Exit code (0 if all succeeded, non-zero if any failed)
    """
    if not source_path.is_dir():
        logger.error("Batch mode requires a directory")
        print("ERROR: Batch mode requires a directory", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Handle sync mode
    if args.sync:
        return _convert_sync(source_path, output_dir, parser, transformer, args)

    # Use BatchConverter for parallel processing
    max_workers = args.workers if hasattr(args, "workers") and args.workers else None

    try:
        batch_converter = BatchConverter(max_workers=max_workers)
    except ValueError as e:
        logger.error(f"Invalid workers configuration: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Determine mappings directory
    if hasattr(args, "mappings_dir") and args.mappings_dir:
        mappings_dir = Path(args.mappings_dir)
    else:
        mappings_dir = None  # BatchConverter will use defaults

    # Define progress callback for non-quiet mode
    def progress_callback(job) -> None:
        if not args.quiet:
            status_symbol = "✓" if job.status == "success" else "✗"
            if job.status in ["success", "failed"]:
                print(f"[{job.index}/{job.total}] {job.app_id}... {status_symbol}")

    # Convert apps in parallel
    logger.info(f"Starting batch conversion with {batch_converter.max_workers} workers")

    result = batch_converter.convert_batch(
        source_dir=source_path,
        output_dir=output_dir,
        download_assets=args.download_assets
        if hasattr(args, "download_assets")
        else False,
        mappings_dir=mappings_dir,
        upstream_url=args.upstream_url if hasattr(args, "upstream_url") else None,
        progress_callback=progress_callback if not args.quiet else None,
    )

    # Print summary
    if result.total == 0:
        print("No apps found in source directory")
    else:
        print(f"\nBatch conversion complete ({result.elapsed_seconds:.1f}s):")
        print(f"  Success: {result.success_count}")
        print(f"  Failed: {result.failure_count}")
        print(f"  Total: {result.total}")

    # Show errors if any
    if result.errors and not args.quiet:
        print("\nErrors:")
        for app_id, error in result.errors[:10]:  # Show first 10
            print(f"  {app_id}: {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more errors")

    return EXIT_SUCCESS if result.failure_count == 0 else EXIT_BUILD_ERROR


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
            for app_id in report.new_apps:
                print(f"  + {app_id}")

        if report.updated_apps:
            print("\nUpdated apps:")
            for app in report.updated_apps:
                print(f"  ~ {app.app_id}")

        if report.removed_apps:
            print("\nRemoved apps:")
            for app_id in report.removed_apps:
                print(f"  - {app_id}")

    # Convert new and updated apps
    apps_to_convert = []

    # new_apps is list[str] (app IDs)
    for app_id in report.new_apps:
        apps_to_convert.append(upstream_dir / app_id)

    # updated_apps is list[UpdatedApp] (objects with app_id attribute)
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

    parser.add_argument(
        "--workers",
        type=int,
        metavar="N",
        help="Number of parallel workers for batch conversion (default: CPU count)",
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
