"""Unit tests for assets directory support."""

from pathlib import Path

import pytest

from generate_container_packages.loader import load_input_files

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"


class TestAssetsLoading:
    """Tests for assets directory detection in loader."""

    def test_load_app_with_assets(self):
        """Test loading an app that has an assets directory."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")

        assert app_def.assets_dir is not None
        assert app_def.assets_dir.exists()
        assert app_def.assets_dir.name == "assets"

    def test_asset_files_detected(self):
        """Test that asset files are enumerated correctly."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")

        assert len(app_def.asset_files) == 4
        # Convert to strings for easier comparison
        asset_names = [str(f.path) for f in app_def.asset_files]
        assert "nginx.conf" in asset_names
        assert "templates/index.html" in asset_names
        assert "templates/error.html" in asset_names
        assert "bin/setup.sh" in asset_names

    def test_executable_files_detected(self):
        """Test that executable files are detected correctly."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")

        # Find the setup.sh asset
        setup_asset = next(
            (f for f in app_def.asset_files if str(f.path) == "bin/setup.sh"), None
        )
        assert setup_asset is not None
        assert setup_asset.executable is True

        # Non-executable files should have executable=False
        nginx_asset = next(
            (f for f in app_def.asset_files if str(f.path) == "nginx.conf"), None
        )
        assert nginx_asset is not None
        assert nginx_asset.executable is False

    def test_load_app_without_assets(self):
        """Test loading an app without assets directory."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        assert app_def.assets_dir is None
        assert app_def.asset_files == []

    def test_asset_files_sorted(self):
        """Test that asset files are sorted for deterministic output."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")

        asset_names = [str(f.path) for f in app_def.asset_files]
        assert asset_names == sorted(asset_names)


class TestAssetsCopying:
    """Tests for copying assets during build."""

    def test_copy_assets_to_build_dir(self, tmp_path):
        """Test that assets are copied to build directory."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # Check assets directory was copied
        assets_dir = output_dir / "assets"
        assert assets_dir.exists()
        assert (assets_dir / "nginx.conf").exists()
        assert (assets_dir / "templates" / "index.html").exists()
        assert (assets_dir / "templates" / "error.html").exists()
        assert (assets_dir / "bin" / "setup.sh").exists()

    def test_copy_assets_preserves_content(self, tmp_path):
        """Test that asset file content is preserved."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # Check content
        nginx_conf = output_dir / "assets" / "nginx.conf"
        content = nginx_conf.read_text()
        assert "server {" in content
        assert "listen 80;" in content

    def test_no_assets_copied_when_none_exist(self, tmp_path):
        """Test that no assets directory is created when app has none."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # No assets directory should exist
        assets_dir = output_dir / "assets"
        assert not assets_dir.exists()


class TestAssetsTemplateContext:
    """Tests for assets in template context."""

    def test_has_assets_true(self):
        """Test has_assets is True when assets exist."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        context = build_context(app_def)

        assert context["has_assets"] is True

    def test_has_assets_false(self):
        """Test has_assets is False when no assets."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        context = build_context(app_def)

        assert context["has_assets"] is False

    def test_asset_files_in_context(self):
        """Test asset files are passed to context."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        context = build_context(app_def)

        assert "asset_files" in context
        assert len(context["asset_files"]) == 4
        # Asset files should be dicts with path and executable keys
        paths = [a["path"] for a in context["asset_files"]]
        assert "nginx.conf" in paths
        assert "templates/index.html" in paths
        assert "bin/setup.sh" in paths

    def test_executable_flag_in_context(self):
        """Test that executable flag is passed to context."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        context = build_context(app_def)

        # Find the setup.sh asset in context
        setup_asset = next(
            (a for a in context["asset_files"] if a["path"] == "bin/setup.sh"), None
        )
        assert setup_asset is not None
        assert setup_asset["executable"] is True

        # Non-executable file
        nginx_asset = next(
            (a for a in context["asset_files"] if a["path"] == "nginx.conf"), None
        )
        assert nginx_asset is not None
        assert nginx_asset["executable"] is False

    def test_empty_asset_files_when_no_assets(self):
        """Test asset_files is empty when no assets."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        context = build_context(app_def)

        assert context["asset_files"] == []


class TestAssetsIntegration:
    """Integration tests for assets feature."""

    @pytest.mark.integration
    def test_assets_in_rendered_rules(self, tmp_path):
        """Test that assets are included in rendered debian/rules."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        # Check rules file includes asset installation
        rules_file = output_dir / "debian" / "rules"
        assert rules_file.exists()
        content = rules_file.read_text()

        # Should have install commands for assets
        assert "assets/nginx.conf" in content
        assert "assets/templates/index.html" in content
        assert "assets/templates/error.html" in content
        assert "assets/bin/setup.sh" in content

    @pytest.mark.integration
    def test_executable_assets_have_755_permissions(self, tmp_path):
        """Test that executable assets are installed with 755 permissions."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "app-with-assets")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        rules_file = output_dir / "debian" / "rules"
        content = rules_file.read_text()

        # Executable file (bin/setup.sh) should have 755 permissions
        assert "install -D -m 755 assets/bin/setup.sh" in content

        # Non-executable files should have 644 permissions
        assert "install -D -m 644 assets/nginx.conf" in content
        assert "install -D -m 644 assets/templates/index.html" in content

    @pytest.mark.integration
    def test_no_assets_section_when_no_assets(self, tmp_path):
        """Test that no assets section is rendered when no assets."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        rules_file = output_dir / "debian" / "rules"
        content = rules_file.read_text()

        # Should NOT have any assets-related install commands
        assert "assets/" not in content
