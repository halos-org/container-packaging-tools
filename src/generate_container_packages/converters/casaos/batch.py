"""Batch conversion with parallel processing for CasaOS apps.

Provides BatchConverter for converting multiple CasaOS applications
in parallel with configurable worker limits and progress tracking.
"""

import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .assets import AssetManager
from .constants import (
    DEFAULT_ARCHITECTURE,
    DEFAULT_LICENSE,
    DEFAULT_MAINTAINER_DOMAIN,
    DEFAULT_VERSION,
    REQUIRED_ROLE_TAG,
    get_default_mappings_dir,
)
from .models import ConversionContext
from .output import OutputWriter
from .parser import CasaOSParser
from .transformer import MetadataTransformer

logger = logging.getLogger(__name__)


@dataclass
class ConversionJob:
    """Represents a single app conversion job in a batch."""

    app_dir: Path
    app_id: str
    status: str  # 'pending', 'running', 'success', 'failed'
    index: int  # 1-based index in batch
    total: int  # Total number of apps in batch
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """Results from a batch conversion operation."""

    total: int
    success_count: int
    failure_count: int
    errors: list[tuple[str, str]]  # [(app_id, error_message), ...]
    warnings: list[tuple[str, str]]  # [(app_id, warning_message), ...]
    elapsed_seconds: float


class BatchConverter:
    """Converts multiple CasaOS apps in parallel.

    Features:
    - Parallel processing with configurable worker limits
    - Thread-safe error collection and progress tracking
    - Continue-on-error semantics for robustness
    - Optional progress callbacks for monitoring

    Example:
        converter = BatchConverter(max_workers=4)
        result = converter.convert_batch(
            source_dir=Path("casaos_apps"),
            output_dir=Path("converted"),
            download_assets=True,
        )
        print(f"Converted {result.success_count}/{result.total} apps")
    """

    def __init__(self, max_workers: int | None = None):
        """Initialize batch converter.

        Args:
            max_workers: Maximum number of parallel workers.
                If None, defaults to number of CPUs.
                Must be positive integer.

        Raises:
            ValueError: If max_workers is not positive
        """
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers must be positive")

        self.max_workers = max_workers or os.cpu_count() or 1

        # Initialize converter components
        self.parser = CasaOSParser()

    def scan_apps(self, source_dir: Path) -> list[Path]:
        """Scan directory for valid CasaOS apps.

        An app is considered valid if it's a directory containing
        a docker-compose.yml file.

        Args:
            source_dir: Directory to scan for apps

        Returns:
            List of paths to app directories

        Raises:
            ValueError: If source_dir doesn't exist or isn't a directory
        """
        source_dir = Path(source_dir)

        if not source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")

        if not source_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {source_dir}")

        apps = []
        for item in source_dir.iterdir():
            if item.is_dir() and (item / "docker-compose.yml").exists():
                apps.append(item)

        return sorted(apps)  # Sort for deterministic ordering

    def convert_batch(
        self,
        source_dir: Path,
        output_dir: Path,
        download_assets: bool = False,
        mappings_dir: Path | None = None,
        upstream_url: str | None = None,
        progress_callback: Callable[[ConversionJob], None] | None = None,
    ) -> BatchResult:
        """Convert multiple CasaOS apps in parallel.

        Args:
            source_dir: Directory containing app subdirectories
            output_dir: Output directory for converted apps
            download_assets: Whether to download icons/screenshots
            mappings_dir: Custom mappings directory (optional)
            upstream_url: Upstream repository URL for source tracking
            progress_callback: Optional callback for progress updates

        Returns:
            BatchResult with conversion statistics and errors

        Example:
            def on_progress(job):
                print(f"[{job.index}/{job.total}] {job.app_id}: {job.status}")

            result = converter.convert_batch(
                source_dir=Path("apps"),
                output_dir=Path("converted"),
                progress_callback=on_progress,
            )
        """
        start_time = time.time()

        # Scan for apps
        app_dirs = self.scan_apps(source_dir)
        total = len(app_dirs)

        if total == 0:
            return BatchResult(
                total=0,
                success_count=0,
                failure_count=0,
                errors=[],
                warnings=[],
                elapsed_seconds=0.0,
            )

        # Determine mappings directory
        if mappings_dir is None:
            mappings_dir = get_default_mappings_dir()

        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare jobs
        jobs = []
        for i, app_dir in enumerate(app_dirs, 1):
            job = ConversionJob(
                app_dir=app_dir,
                app_id=app_dir.name,  # Will be updated after parsing
                status="pending",
                index=i,
                total=total,
            )
            jobs.append(job)

        # Convert apps in parallel
        success_count = 0
        failure_count = 0
        errors = []
        warnings = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_job = {}
            for job in jobs:
                future = executor.submit(
                    self._convert_single_app,
                    job,
                    output_dir,
                    download_assets,
                    mappings_dir,
                    upstream_url,
                )
                future_to_job[future] = job

            # Collect results as they complete
            for future in as_completed(future_to_job):
                job = future_to_job[future]

                try:
                    result = future.result()
                    if result["success"]:
                        job.status = "success"
                        success_count += 1
                    else:
                        job.status = "failed"
                        failure_count += 1
                        errors.append((job.app_id, result["error"]))

                    # Collect warnings
                    for warning in result.get("warnings", []):
                        warnings.append((job.app_id, warning))
                        job.warnings.append(warning)

                    if result.get("error"):
                        job.error = result["error"]

                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                    failure_count += 1
                    errors.append((job.app_id, str(e)))

                # Call progress callback
                if progress_callback:
                    progress_callback(job)

        elapsed = time.time() - start_time

        return BatchResult(
            total=total,
            success_count=success_count,
            failure_count=failure_count,
            errors=errors,
            warnings=warnings,
            elapsed_seconds=elapsed,
        )

    def _convert_single_app(
        self,
        job: ConversionJob,
        output_dir: Path,
        download_assets: bool,
        mappings_dir: Path,
        upstream_url: str | None,
    ) -> dict:
        """Convert a single app (executed in worker thread).

        Args:
            job: Conversion job with app info
            output_dir: Output directory for converted app
            download_assets: Whether to download assets
            mappings_dir: Mappings directory
            upstream_url: Upstream URL for tracking

        Returns:
            Dict with keys: success (bool), error (str), warnings (list)
        """
        try:
            job.status = "running"

            # Parse CasaOS app
            compose_file = job.app_dir / "docker-compose.yml"
            casaos_app = self.parser.parse_from_file(compose_file)

            # Update job with actual app ID
            job.app_id = casaos_app.id

            # Create conversion context
            context = ConversionContext(
                source_format="casaos",
                app_id=casaos_app.id,
                warnings=[],
                errors=[],
                downloaded_assets=[],
            )

            # Transform to HaLOS format
            transformer = MetadataTransformer(mappings_dir)
            transformed = transformer.transform(
                casaos_app,
                context,
                source_file_path=compose_file,
                source_url=upstream_url,
            )

            # Enrich metadata with required fields
            metadata = transformed["metadata"]
            self._enrich_metadata(metadata, casaos_app)

            # Write output files
            app_output_dir = output_dir / casaos_app.id
            writer = OutputWriter(app_output_dir)
            writer.write_package(
                metadata,
                transformed["config"],
                transformed["compose"],
                context,
            )

            # Download assets if requested
            if download_assets:
                try:
                    asset_manager = AssetManager(app_output_dir)
                    asset_manager.download_all_assets(
                        casaos_app.icon,
                        casaos_app.screenshots or [],
                        casaos_app.id,
                        context,
                    )
                except Exception as e:
                    context.warnings.append(f"Asset download failed: {e}")

            return {
                "success": True,
                "error": None,
                "warnings": context.warnings,
            }

        except Exception as e:
            logger.error(
                f"Failed to convert app {job.app_id} from {job.app_dir}: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "warnings": [],
            }

    def _enrich_metadata(self, metadata: dict, casaos_app) -> None:  # noqa: F821
        """Enrich metadata with required fields that CasaOS doesn't provide.

        Uses shared constants from the constants module to ensure consistency
        across all converter components.

        Args:
            metadata: Metadata dictionary to enrich (modified in-place)
            casaos_app: Parsed CasaOS application data
        """

        if "version" not in metadata or not metadata["version"]:
            metadata["version"] = DEFAULT_VERSION

        if "maintainer" not in metadata or not metadata["maintainer"]:
            dev_name = casaos_app.developer if casaos_app.developer else "Unknown"
            metadata["maintainer"] = f"{dev_name} <{DEFAULT_MAINTAINER_DOMAIN}>"

        if "license" not in metadata or not metadata["license"]:
            metadata["license"] = DEFAULT_LICENSE

        if "tags" not in metadata or not metadata["tags"]:
            metadata["tags"] = casaos_app.tags if casaos_app.tags else []

        if REQUIRED_ROLE_TAG not in metadata["tags"]:
            metadata["tags"].insert(0, REQUIRED_ROLE_TAG)

        if "architecture" not in metadata or not metadata["architecture"]:
            metadata["architecture"] = DEFAULT_ARCHITECTURE
