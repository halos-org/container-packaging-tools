"""Unit tests for default-data directory support."""

from pathlib import Path

import pytest

from generate_container_packages.loader import load_input_files

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_FIXTURES = FIXTURES_DIR / "valid"


class TestDefaultDataLoading:
    """Tests for default-data directory detection in loader."""

    def test_load_app_with_default_data(self):
        """Test loading an app that has a default-data directory."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")

        assert app_def.default_data_dir is not None
        assert app_def.default_data_dir.exists()
        assert app_def.default_data_dir.name == "default-data"

    def test_default_data_files_detected(self):
        """Test that default data files are enumerated correctly."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")

        assert len(app_def.default_data_files) == 3
        # Convert to strings for easier comparison
        file_names = [str(f.path) for f in app_def.default_data_files]
        assert ".signalk/security.json" in file_names
        assert ".signalk/defaults.json" in file_names
        assert "scripts/init.sh" in file_names

    def test_executable_files_detected(self):
        """Test that executable files are detected correctly."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")

        # Find the init.sh file
        init_file = next(
            (f for f in app_def.default_data_files if str(f.path) == "scripts/init.sh"),
            None,
        )
        assert init_file is not None
        assert init_file.executable is True

        # Non-executable files should have executable=False
        security_file = next(
            (
                f
                for f in app_def.default_data_files
                if str(f.path) == ".signalk/security.json"
            ),
            None,
        )
        assert security_file is not None
        assert security_file.executable is False

    def test_load_app_without_default_data(self):
        """Test loading an app without default-data directory."""
        app_def = load_input_files(VALID_FIXTURES / "simple-app")

        assert app_def.default_data_dir is None
        assert app_def.default_data_files == []

    def test_default_data_files_sorted(self):
        """Test that default data files are sorted for deterministic output."""
        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")

        file_names = [str(f.path) for f in app_def.default_data_files]
        assert file_names == sorted(file_names)


class TestDefaultDataCopying:
    """Tests for copying default-data during build."""

    def test_copy_default_data_to_build_dir(self, tmp_path):
        """Test that default-data is copied to build directory."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # Check default-data directory was copied
        default_data_dir = output_dir / "default-data"
        assert default_data_dir.exists()
        assert (default_data_dir / ".signalk" / "security.json").exists()
        assert (default_data_dir / ".signalk" / "defaults.json").exists()
        assert (default_data_dir / "scripts" / "init.sh").exists()

    def test_copy_default_data_preserves_content(self, tmp_path):
        """Test that default data file content is preserved."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # Check content
        security_json = output_dir / "default-data" / ".signalk" / "security.json"
        content = security_json.read_text()
        assert '"strategy"' in content
        assert '"users"' in content

    def test_no_default_data_copied_when_none_exist(self, tmp_path):
        """Test that no default-data directory is created when app has none."""
        from generate_container_packages.builder import copy_source_files

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "build"
        output_dir.mkdir()

        copy_source_files(app_def, output_dir)

        # No default-data directory should exist
        default_data_dir = output_dir / "default-data"
        assert not default_data_dir.exists()


class TestDefaultDataTemplateContext:
    """Tests for default-data in template context."""

    def test_has_default_data_true(self):
        """Test has_default_data is True when default-data exists."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        context = build_context(app_def)

        assert context["has_default_data"] is True

    def test_has_default_data_false(self):
        """Test has_default_data is False when no default-data."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        context = build_context(app_def)

        assert context["has_default_data"] is False

    def test_default_data_files_in_context(self):
        """Test default data files are passed to context."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        context = build_context(app_def)

        assert "default_data_files" in context
        assert len(context["default_data_files"]) == 3
        # Default data files should be dicts with path and executable keys
        paths = [d["path"] for d in context["default_data_files"]]
        assert ".signalk/security.json" in paths
        assert ".signalk/defaults.json" in paths
        assert "scripts/init.sh" in paths

    def test_executable_flag_in_context(self):
        """Test that executable flag is passed to context."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        context = build_context(app_def)

        # Find the init.sh file in context
        init_file = next(
            (
                d
                for d in context["default_data_files"]
                if d["path"] == "scripts/init.sh"
            ),
            None,
        )
        assert init_file is not None
        assert init_file["executable"] is True

        # Non-executable file
        security_file = next(
            (
                d
                for d in context["default_data_files"]
                if d["path"] == ".signalk/security.json"
            ),
            None,
        )
        assert security_file is not None
        assert security_file["executable"] is False

    def test_empty_default_data_files_when_no_default_data(self):
        """Test default_data_files is empty when no default-data."""
        from generate_container_packages.template_context import build_context

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        context = build_context(app_def)

        assert context["default_data_files"] == []


class TestDefaultDataIntegration:
    """Integration tests for default-data feature."""

    @pytest.mark.integration
    def test_default_data_in_rendered_rules(self, tmp_path):
        """Test that default-data is included in rendered debian/rules."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        # Check rules file includes default-data installation
        rules_file = output_dir / "debian" / "rules"
        assert rules_file.exists()
        content = rules_file.read_text()

        # Should have install commands for default-data
        assert "default-data/.signalk/security.json" in content
        assert "default-data/.signalk/defaults.json" in content
        assert "default-data/scripts/init.sh" in content

    @pytest.mark.integration
    def test_executable_default_data_have_755_permissions(self, tmp_path):
        """Test that executable default-data files are installed with 755 permissions."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        rules_file = output_dir / "debian" / "rules"
        content = rules_file.read_text()

        # Executable file (scripts/init.sh) should have 755 permissions
        assert "install -D -m 755 default-data/scripts/init.sh" in content

        # Non-executable files should have 644 permissions
        assert "install -D -m 644 default-data/.signalk/security.json" in content
        assert "install -D -m 644 default-data/.signalk/defaults.json" in content

    @pytest.mark.integration
    def test_no_default_data_section_when_no_default_data(self, tmp_path):
        """Test that no default-data section is rendered when no default-data."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        rules_file = output_dir / "debian" / "rules"
        content = rules_file.read_text()

        # Should NOT have any default-data-related install commands
        assert "default-data/" not in content

    @pytest.mark.integration
    def test_postinst_includes_default_data_copy(self, tmp_path):
        """Test that postinst includes default-data copy logic."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "app-with-default-data")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        # Check postinst includes default-data copy logic
        postinst_file = output_dir / "debian" / "postinst"
        assert postinst_file.exists()
        content = postinst_file.read_text()

        # Should have default-data copy logic
        assert "default-data" in content
        assert "CONTAINER_DATA_ROOT" in content
        # Should only copy if destination doesn't exist
        assert '[ ! -f "$dst_file" ]' in content

    @pytest.mark.integration
    def test_postinst_no_default_data_when_none_exist(self, tmp_path):
        """Test that postinst doesn't include default-data copy when none exist."""
        from generate_container_packages.loader import load_input_files
        from generate_container_packages.renderer import render_all_templates

        app_def = load_input_files(VALID_FIXTURES / "simple-app")
        output_dir = tmp_path / "rendered"

        render_all_templates(app_def, output_dir)

        # Check postinst doesn't include default-data logic
        postinst_file = output_dir / "debian" / "postinst"
        content = postinst_file.read_text()

        # Should NOT have default-data copy logic
        assert "default-data" not in content
