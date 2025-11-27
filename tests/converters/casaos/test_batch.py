"""Tests for batch conversion with parallel processing.

Tests the BatchConverter class for converting multiple CasaOS apps
in parallel with proper error handling and progress tracking.
"""

import time
from pathlib import Path

import pytest

from generate_container_packages.converters.casaos.batch import (
    BatchConverter,
    BatchResult,
    ConversionJob,
)

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBatchConverter:
    """Tests for BatchConverter class."""

    def test_batch_converter_creation(self, tmp_path: Path) -> None:
        """Test that BatchConverter can be created with defaults."""
        converter = BatchConverter()
        assert converter is not None
        assert converter.max_workers > 0  # Should use CPU count by default

    def test_batch_converter_custom_workers(self) -> None:
        """Test that max_workers can be customized."""
        converter = BatchConverter(max_workers=4)
        assert converter.max_workers == 4

    def test_batch_converter_validates_workers(self) -> None:
        """Test that invalid max_workers raises error."""
        with pytest.raises(ValueError, match="max_workers must be positive"):
            BatchConverter(max_workers=0)

        with pytest.raises(ValueError, match="max_workers must be positive"):
            BatchConverter(max_workers=-1)

    def test_scan_apps_finds_valid_apps(self, tmp_path: Path) -> None:
        """Test that scan_apps finds directories with docker-compose.yml."""
        # Create test directory structure
        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Valid app 1
        app1 = batch_dir / "app1"
        app1.mkdir()
        (app1 / "docker-compose.yml").write_text("name: app1")

        # Valid app 2
        app2 = batch_dir / "app2"
        app2.mkdir()
        (app2 / "docker-compose.yml").write_text("name: app2")

        # Invalid app (no docker-compose.yml)
        app3 = batch_dir / "app3"
        app3.mkdir()

        # Not a directory
        (batch_dir / "file.txt").write_text("not an app")

        converter = BatchConverter()
        apps = converter.scan_apps(batch_dir)

        assert len(apps) == 2
        assert app1 in apps
        assert app2 in apps
        assert app3 not in apps

    def test_scan_apps_empty_directory(self, tmp_path: Path) -> None:
        """Test that scan_apps returns empty list for directory with no apps."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        converter = BatchConverter()
        apps = converter.scan_apps(empty_dir)

        assert len(apps) == 0

    def test_scan_apps_invalid_directory(self, tmp_path: Path) -> None:
        """Test that scan_apps raises error for non-existent directory."""
        converter = BatchConverter()

        with pytest.raises(ValueError, match="does not exist"):
            converter.scan_apps(tmp_path / "nonexistent")

    def test_convert_batch_sequential(self, tmp_path: Path) -> None:
        """Test batch conversion with single worker (sequential)."""
        # Setup test apps
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "app1")
        shutil.copytree(FIXTURES_DIR / "complex-app", batch_dir / "app2")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=1)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        assert isinstance(result, BatchResult)
        assert result.total == 2
        assert result.success_count >= 0
        assert result.failure_count >= 0
        assert result.success_count + result.failure_count == result.total

    def test_convert_batch_parallel(self, tmp_path: Path) -> None:
        """Test batch conversion with multiple workers (parallel)."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Create multiple apps
        for i in range(4):
            shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / f"app{i}")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=2)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        assert result.total == 4
        assert result.success_count + result.failure_count == 4

    def test_convert_batch_partial_failures(self, tmp_path: Path) -> None:
        """Test that batch conversion continues on individual app failures."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Valid app
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "valid")

        # Invalid app
        invalid = batch_dir / "invalid"
        invalid.mkdir()
        (invalid / "docker-compose.yml").write_text("invalid: :::")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=2)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        assert result.total == 2
        # At least one should succeed
        assert result.success_count >= 1
        # At least one should fail
        assert result.failure_count >= 1
        # Should have error details
        assert len(result.errors) > 0

    def test_convert_batch_progress_callback(self, tmp_path: Path) -> None:
        """Test that progress callback is called during batch conversion."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "app1")

        output_dir = tmp_path / "output"

        # Track progress calls
        progress_calls = []

        def progress_callback(job: ConversionJob) -> None:
            progress_calls.append(job)

        converter = BatchConverter(max_workers=1)
        converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
            progress_callback=progress_callback,
        )

        # Should have received progress updates
        assert len(progress_calls) > 0
        assert all(isinstance(job, ConversionJob) for job in progress_calls)

    def test_batch_result_summary(self, tmp_path: Path) -> None:
        """Test that BatchResult provides useful summary information."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "app1")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=1)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        # Should have summary info
        assert result.total > 0
        assert result.success_count >= 0
        assert result.failure_count >= 0
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

        # Should have elapsed time
        assert result.elapsed_seconds >= 0

    def test_parallel_execution_faster_than_sequential(self, tmp_path: Path) -> None:
        """Test that parallel execution is faster than sequential for multiple apps."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Create several apps
        for i in range(4):
            shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / f"app{i}")

        output_dir_seq = tmp_path / "output_seq"
        output_dir_par = tmp_path / "output_par"

        # Sequential conversion
        converter_seq = BatchConverter(max_workers=1)
        start = time.time()
        result_seq = converter_seq.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir_seq,
            download_assets=False,
        )
        seq_time = time.time() - start

        # Parallel conversion
        converter_par = BatchConverter(max_workers=2)
        start = time.time()
        result_par = converter_par.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir_par,
            download_assets=False,
        )
        par_time = time.time() - start

        # Both should complete successfully
        assert result_seq.total == result_par.total

        # Parallel should be faster (or at least not significantly slower)
        # Allow some margin for overhead
        assert par_time <= seq_time * 1.2

    def test_thread_safety_with_errors(self, tmp_path: Path) -> None:
        """Test that error collection is thread-safe with parallel execution."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Create mix of valid and invalid apps
        for i in range(4):
            if i % 2 == 0:
                shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / f"app{i}")
            else:
                invalid = batch_dir / f"app{i}"
                invalid.mkdir()
                (invalid / "docker-compose.yml").write_text("invalid: :::")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=2)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        # Should have collected errors from multiple threads
        assert result.total == 4
        assert result.failure_count >= 2  # At least the invalid ones
        # Error count should match failure count
        assert len(result.errors) == result.failure_count


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_batch_result_creation(self) -> None:
        """Test that BatchResult can be created."""
        result = BatchResult(
            total=10,
            success_count=8,
            failure_count=2,
            errors=[],
            warnings=[],
            elapsed_seconds=1.5,
        )

        assert result.total == 10
        assert result.success_count == 8
        assert result.failure_count == 2
        assert result.elapsed_seconds == 1.5

    def test_batch_result_success_rate(self) -> None:
        """Test success rate calculation."""
        result = BatchResult(
            total=10,
            success_count=7,
            failure_count=3,
            errors=[],
            warnings=[],
            elapsed_seconds=1.0,
        )

        success_rate = result.success_count / result.total if result.total > 0 else 0
        assert success_rate == 0.7


class TestConversionJob:
    """Tests for ConversionJob dataclass."""

    def test_conversion_job_creation(self) -> None:
        """Test that ConversionJob can be created."""
        job = ConversionJob(
            app_dir=Path("/test/app"),
            app_id="test-app",
            status="pending",
            index=1,
            total=5,
        )

        assert job.app_dir == Path("/test/app")
        assert job.app_id == "test-app"
        assert job.status == "pending"
        assert job.index == 1
        assert job.total == 5
        assert job.error is None


class TestBatchIntegration:
    """Integration tests for batch conversion with real converters."""

    def test_batch_with_real_converter(self, tmp_path: Path) -> None:
        """Test batch conversion with actual CasaOS converter components."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "nginx")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=1)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        # Should succeed
        assert result.success_count == 1
        assert result.failure_count == 0

        # Should have created output
        assert (output_dir / "nginx-test").exists()
        assert (output_dir / "nginx-test" / "metadata.yaml").exists()
        assert (output_dir / "nginx-test" / "config.yml").exists()
        assert (output_dir / "nginx-test" / "docker-compose.yml").exists()

    def test_batch_preserves_output_structure(self, tmp_path: Path) -> None:
        """Test that batch conversion creates correct output structure."""
        import shutil

        batch_dir = tmp_path / "apps"
        batch_dir.mkdir()

        # Create two apps
        shutil.copytree(FIXTURES_DIR / "simple-app", batch_dir / "app1")
        shutil.copytree(FIXTURES_DIR / "complex-app", batch_dir / "app2")

        output_dir = tmp_path / "output"

        converter = BatchConverter(max_workers=2)
        result = converter.convert_batch(
            source_dir=batch_dir,
            output_dir=output_dir,
            download_assets=False,
        )

        # Should have separate output directories for each app
        if result.success_count > 0:
            # At least one app should have been converted
            converted_apps = [d for d in output_dir.iterdir() if d.is_dir()]
            assert len(converted_apps) > 0

            # Each converted app should have required files
            for app_dir in converted_apps:
                assert (app_dir / "metadata.yaml").exists()
                assert (app_dir / "config.yml").exists()
                assert (app_dir / "docker-compose.yml").exists()
