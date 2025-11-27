"""Tests for CasaOS asset manager.

Tests downloading, validating, and managing icons and screenshots
from URLs with retry logic, size validation, and parallel downloads.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from generate_container_packages.converters.casaos.assets import AssetManager
from generate_container_packages.converters.casaos.models import ConversionContext


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create temporary output directory."""
    return tmp_path / "output"


@pytest.fixture
def asset_manager(output_dir: Path) -> AssetManager:
    """Create AssetManager instance."""
    return AssetManager(output_dir)


@pytest.fixture
def conversion_context() -> ConversionContext:
    """Create ConversionContext for testing."""
    return ConversionContext(source_format="casaos", app_id="test-app")


@pytest.fixture
def mock_png_content() -> bytes:
    """Create minimal valid PNG content."""
    # PNG file signature + minimal IHDR chunk
    return (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk length and type
        b"\x00\x00\x00\x10"  # Width: 16
        b"\x00\x00\x00\x10"  # Height: 16
        b"\x08\x02\x00\x00\x00"  # Bit depth, color type, etc.
        b"\x90\x91\x68\x36"  # CRC
        b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
    )


@pytest.fixture
def mock_svg_content() -> bytes:
    """Create minimal valid SVG content."""
    return b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'


class TestAssetManagerInit:
    """Test AssetManager initialization."""

    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        """Test initialization creates output directory if it doesn't exist."""
        output_dir = tmp_path / "new_output"
        assert not output_dir.exists()

        AssetManager(output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_init_with_existing_dir(self, output_dir: Path) -> None:
        """Test initialization with existing directory."""
        output_dir.mkdir(parents=True)
        assert output_dir.exists()

        AssetManager(output_dir)

        assert output_dir.exists()


class TestDownloadFile:
    """Test file download functionality."""

    @patch("requests.get")
    def test_download_success(
        self,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        mock_png_content: bytes,
    ) -> None:
        """Test successful file download."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_png_content
        mock_response.headers = {
            "content-length": str(len(mock_png_content)),
            "content-type": "image/png",
        }
        mock_get.return_value = mock_response

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png", dest_path, timeout=30, max_size_mb=5
        )

        assert success is True
        assert content_type == "image/png"
        assert dest_path.exists()
        assert dest_path.read_bytes() == mock_png_content
        mock_get.assert_called_once()

    @patch("requests.get")
    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_download_retry_on_failure(
        self,
        mock_sleep: Mock,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        mock_png_content: bytes,
    ) -> None:
        """Test download retries on network failure with exponential backoff."""
        # Fail twice, then succeed
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.content = mock_png_content
        mock_response_success.headers = {
            "content-length": str(len(mock_png_content)),
            "content-type": "image/png",
        }

        mock_get.side_effect = [
            requests.RequestException("Network error"),
            requests.RequestException("Network error"),
            mock_response_success,
        ]

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png", dest_path, timeout=30, max_size_mb=5
        )

        assert success is True
        assert content_type == "image/png"
        assert dest_path.exists()
        assert mock_get.call_count == 3
        # Verify exponential backoff: sleep(1), sleep(2)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("requests.get")
    @patch("time.sleep")
    def test_download_fails_after_max_retries(
        self,
        mock_sleep: Mock,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
    ) -> None:
        """Test download fails after max retries exhausted."""
        mock_get.side_effect = requests.RequestException("Network error")

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png", dest_path, timeout=30, max_size_mb=5
        )

        assert success is False
        assert content_type is None
        assert not dest_path.exists()
        # 1 initial attempt + 3 retries = 4 total
        assert mock_get.call_count == 4

    @patch("requests.get")
    def test_download_timeout(
        self,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
    ) -> None:
        """Test download timeout handling."""
        mock_get.side_effect = requests.Timeout("Timeout")

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png", dest_path, timeout=30, max_size_mb=5
        )

        assert success is False
        assert content_type is None
        mock_get.assert_called()
        # Verify timeout was passed to requests.get
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 30

    @patch("requests.get")
    def test_download_size_limit_exceeded(
        self,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
    ) -> None:
        """Test download fails when content exceeds size limit."""
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = large_content
        mock_response.headers = {"content-length": str(len(large_content))}
        mock_get.return_value = mock_response

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png",
            dest_path,
            timeout=30,
            max_size_mb=5,  # 5MB limit
        )

        assert success is False
        assert content_type is None
        # File might be created but should be cleaned up
        if dest_path.exists():
            assert dest_path.stat().st_size == 0 or not dest_path.exists()

    @patch("requests.get")
    def test_download_http_error_status(
        self,
        mock_get: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
    ) -> None:
        """Test download handles HTTP error status codes."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        dest_path = output_dir / "test.png"
        success, content_type = asset_manager._download_file(
            "https://example.com/icon.png", dest_path, timeout=30, max_size_mb=5
        )

        assert success is False
        assert content_type is None
        assert not dest_path.exists()


class TestImageValidation:
    """Test image format and size validation."""

    def test_validate_png_format(
        self, asset_manager: AssetManager, tmp_path: Path, mock_png_content: bytes
    ) -> None:
        """Test PNG format validation passes."""
        image_path = tmp_path / "test.png"
        image_path.write_bytes(mock_png_content)

        result = asset_manager._validate_image(image_path, max_size_mb=5)

        assert result is True

    def test_validate_svg_format(
        self, asset_manager: AssetManager, tmp_path: Path, mock_svg_content: bytes
    ) -> None:
        """Test SVG format validation passes."""
        image_path = tmp_path / "test.svg"
        image_path.write_bytes(mock_svg_content)

        result = asset_manager._validate_image(image_path, max_size_mb=5)

        assert result is True

    def test_validate_invalid_format(
        self, asset_manager: AssetManager, tmp_path: Path
    ) -> None:
        """Test invalid image format validation fails."""
        image_path = tmp_path / "test.txt"
        image_path.write_text("Not an image")

        result = asset_manager._validate_image(image_path, max_size_mb=5)

        assert result is False

    def test_validate_size_limit_exceeded(
        self, asset_manager: AssetManager, tmp_path: Path
    ) -> None:
        """Test size limit validation fails for oversized files."""
        image_path = tmp_path / "large.png"
        # Create a file larger than 5MB
        image_path.write_bytes(b"x" * (6 * 1024 * 1024))

        result = asset_manager._validate_image(image_path, max_size_mb=5)

        assert result is False

    def test_validate_size_within_limit(
        self, asset_manager: AssetManager, tmp_path: Path, mock_png_content: bytes
    ) -> None:
        """Test size limit validation passes for small files."""
        image_path = tmp_path / "small.png"
        image_path.write_bytes(mock_png_content)

        result = asset_manager._validate_image(image_path, max_size_mb=5)

        assert result is True


class TestDownloadIcon:
    """Test icon download functionality."""

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._validate_image"
    )
    def test_download_icon_success(
        self,
        mock_validate: Mock,
        mock_download: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
    ) -> None:
        """Test successful icon download."""
        mock_download.return_value = (True, "image/png")
        mock_validate.return_value = True

        result = asset_manager.download_icon(
            "https://example.com/icon.png", "myapp", conversion_context
        )

        assert result is not None
        assert result.parent == output_dir / "myapp"
        assert result.name == "icon.png"
        mock_download.assert_called_once()
        mock_validate.assert_called_once()
        # Verify tracked in context
        assert str(result) in conversion_context.downloaded_assets

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    def test_download_icon_download_fails(
        self,
        mock_download: Mock,
        asset_manager: AssetManager,
        conversion_context: ConversionContext,
    ) -> None:
        """Test icon download failure adds warning."""
        mock_download.return_value = (False, None)

        result = asset_manager.download_icon(
            "https://example.com/icon.png", "myapp", conversion_context
        )

        assert result is None
        # Verify warning added to context
        assert len(conversion_context.warnings) > 0
        assert "icon" in conversion_context.warnings[0].lower()

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._validate_image"
    )
    def test_download_icon_validation_fails(
        self,
        mock_validate: Mock,
        mock_download: Mock,
        asset_manager: AssetManager,
        conversion_context: ConversionContext,
    ) -> None:
        """Test icon validation failure adds warning."""
        mock_download.return_value = (True, "image/png")
        mock_validate.return_value = False

        result = asset_manager.download_icon(
            "https://example.com/icon.png", "myapp", conversion_context
        )

        assert result is None
        assert len(conversion_context.warnings) > 0
        assert "validation" in conversion_context.warnings[0].lower()

    def test_download_icon_creates_app_directory(
        self,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
    ) -> None:
        """Test icon download creates app directory structure."""
        with patch.object(
            asset_manager, "_download_file", return_value=(True, "image/png")
        ):
            with patch.object(asset_manager, "_validate_image", return_value=True):
                asset_manager.download_icon(
                    "https://example.com/icon.png", "myapp", conversion_context
                )

        app_dir = output_dir / "myapp"
        assert app_dir.exists()
        assert app_dir.is_dir()


class TestDownloadScreenshots:
    """Test screenshot download functionality."""

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._validate_image"
    )
    def test_download_screenshots_success(
        self,
        mock_validate: Mock,
        mock_download: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
    ) -> None:
        """Test successful screenshots download."""
        mock_download.return_value = (True, "image/png")
        mock_validate.return_value = True

        urls = [
            "https://example.com/screen1.png",
            "https://example.com/screen2.png",
            "https://example.com/screen3.png",
        ]

        results = asset_manager.download_screenshots(urls, "myapp", conversion_context)

        assert len(results) == 3
        assert all(r is not None for r in results)
        assert all(r.parent == output_dir / "myapp" / "screenshots" for r in results)
        # Verify all tracked in context
        assert len(conversion_context.downloaded_assets) == 3

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._validate_image"
    )
    def test_download_screenshots_partial_failure(
        self,
        mock_validate: Mock,
        mock_download: Mock,
        asset_manager: AssetManager,
        conversion_context: ConversionContext,
    ) -> None:
        """Test partial screenshot download failure."""
        # First succeeds, second fails, third succeeds
        mock_download.side_effect = [
            (True, "image/png"),
            (False, None),
            (True, "image/png"),
        ]
        mock_validate.return_value = True

        urls = [
            "https://example.com/screen1.png",
            "https://example.com/screen2.png",
            "https://example.com/screen3.png",
        ]

        results = asset_manager.download_screenshots(urls, "myapp", conversion_context)

        # Returns only successful downloads (non-None)
        successful = [r for r in results if r is not None]
        assert len(successful) == 2
        # Verify warning for failed download
        assert len(conversion_context.warnings) > 0

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._download_file"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager._validate_image"
    )
    def test_download_screenshots_parallel(
        self,
        mock_validate: Mock,
        mock_download: Mock,
        asset_manager: AssetManager,
        conversion_context: ConversionContext,
    ) -> None:
        """Test screenshots are downloaded in parallel."""
        # Track call times to verify parallel execution
        call_times = []

        def slow_download(*args, **kwargs):
            call_times.append(time.time())
            time.sleep(0.1)  # Simulate download time
            return (True, "image/png")

        mock_download.side_effect = slow_download
        mock_validate.return_value = True

        urls = [
            "https://example.com/screen1.png",
            "https://example.com/screen2.png",
            "https://example.com/screen3.png",
        ]

        start_time = time.time()
        asset_manager.download_screenshots(urls, "myapp", conversion_context)
        elapsed_time = time.time() - start_time

        # If parallel, should take ~0.1s (one batch)
        # If sequential, would take ~0.3s (three * 0.1s)
        # Allow some overhead
        assert elapsed_time < 0.25  # Parallel execution

    def test_download_screenshots_empty_list(
        self,
        asset_manager: AssetManager,
        conversion_context: ConversionContext,
    ) -> None:
        """Test downloading empty screenshot list."""
        results = asset_manager.download_screenshots([], "myapp", conversion_context)

        assert results == []
        assert len(conversion_context.warnings) == 0


class TestDownloadAllAssets:
    """Test downloading all assets for an app."""

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_icon"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_screenshots"
    )
    def test_download_all_assets_complete(
        self,
        mock_download_screenshots: Mock,
        mock_download_icon: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
    ) -> None:
        """Test downloading all assets (icon + screenshots)."""
        mock_download_icon.return_value = output_dir / "myapp" / "icon.png"
        mock_download_screenshots.return_value = [
            output_dir / "myapp" / "screenshots" / "screen1.png",
            output_dir / "myapp" / "screenshots" / "screen2.png",
        ]

        result = asset_manager.download_all_assets(
            icon_url="https://example.com/icon.png",
            screenshot_urls=[
                "https://example.com/screen1.png",
                "https://example.com/screen2.png",
            ],
            app_id="myapp",
            context=conversion_context,
        )

        assert "icon" in result
        assert "screenshots" in result
        assert result["icon"] is not None
        assert len(result["screenshots"]) == 2

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_icon"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_screenshots"
    )
    def test_download_all_assets_no_icon(
        self,
        mock_download_screenshots: Mock,
        mock_download_icon: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
    ) -> None:
        """Test downloading assets with no icon URL."""
        mock_download_screenshots.return_value = [
            output_dir / "myapp" / "screenshots" / "screen1.png"
        ]

        result = asset_manager.download_all_assets(
            icon_url=None,
            screenshot_urls=["https://example.com/screen1.png"],
            app_id="myapp",
            context=conversion_context,
        )

        assert result["icon"] is None
        assert len(result["screenshots"]) == 1
        mock_download_icon.assert_not_called()

    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_icon"
    )
    @patch(
        "generate_container_packages.converters.casaos.assets.AssetManager.download_screenshots"
    )
    def test_download_all_assets_total_size_limit(
        self,
        mock_download_screenshots: Mock,
        mock_download_icon: Mock,
        asset_manager: AssetManager,
        output_dir: Path,
        conversion_context: ConversionContext,
        tmp_path: Path,
    ) -> None:
        """Test total size limit enforcement across all assets."""
        # Create mock files that would exceed 50MB total
        icon_path = tmp_path / "icon.png"
        icon_path.write_bytes(b"x" * (30 * 1024 * 1024))  # 30MB
        screenshot_path = tmp_path / "screen.png"
        screenshot_path.write_bytes(b"x" * (25 * 1024 * 1024))  # 25MB

        mock_download_icon.return_value = icon_path
        mock_download_screenshots.return_value = [screenshot_path]

        _result = asset_manager.download_all_assets(
            icon_url="https://example.com/icon.png",
            screenshot_urls=["https://example.com/screen.png"],
            app_id="myapp",
            context=conversion_context,
        )

        # Should add warning about exceeding total size limit
        warnings_text = " ".join(conversion_context.warnings).lower()
        assert "50" in warnings_text or "size" in warnings_text
