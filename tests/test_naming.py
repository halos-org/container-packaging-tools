"""Unit tests for package naming module."""

import pytest

from generate_container_packages.naming import (
    compute_package_name,
    derive_app_id,
    expand_dependencies,
    expand_dependency,
)


class TestComputePackageName:
    """Tests for compute_package_name function."""

    def test_with_prefix(self):
        """Test package name with prefix."""
        result = compute_package_name("signalk-server", prefix="marine")
        assert result == "marine-signalk-server-container"

    def test_without_prefix(self):
        """Test package name without prefix."""
        result = compute_package_name("homarr", prefix=None)
        assert result == "homarr-container"

    def test_empty_prefix(self):
        """Test package name with empty string prefix."""
        result = compute_package_name("grafana", prefix="")
        assert result == "grafana-container"

    def test_custom_suffix(self):
        """Test package name with custom suffix."""
        result = compute_package_name("myapp", prefix="halos", suffix="pkg")
        assert result == "halos-myapp-pkg"

    def test_no_suffix(self):
        """Test package name with empty suffix."""
        result = compute_package_name("myapp", prefix="halos", suffix="")
        assert result == "halos-myapp"

    def test_various_prefixes(self):
        """Test different prefix values."""
        assert compute_package_name("app", prefix="marine") == "marine-app-container"
        assert compute_package_name("app", prefix="halos") == "halos-app-container"
        assert compute_package_name("app", prefix="casaos") == "casaos-app-container"

    def test_complex_app_id(self):
        """Test with complex app_id containing hyphens."""
        result = compute_package_name("signal-k-server", prefix="marine")
        assert result == "marine-signal-k-server-container"


class TestDeriveAppId:
    """Tests for derive_app_id function."""

    def test_simple_name(self):
        """Test deriving app_id from simple directory name."""
        assert derive_app_id("grafana") == "grafana"

    def test_uppercase_to_lowercase(self):
        """Test that uppercase is converted to lowercase."""
        assert derive_app_id("Grafana") == "grafana"
        assert derive_app_id("INFLUXDB") == "influxdb"
        assert derive_app_id("SignalK") == "signalk"

    def test_underscore_to_hyphen(self):
        """Test that underscores are converted to hyphens."""
        assert derive_app_id("signal_k_server") == "signal-k-server"
        assert derive_app_id("my_cool_app") == "my-cool-app"

    def test_spaces_to_hyphen(self):
        """Test that spaces are converted to hyphens."""
        assert derive_app_id("my app") == "my-app"
        assert derive_app_id("Signal K Server") == "signal-k-server"

    def test_special_characters_removed(self):
        """Test that special characters are removed or converted."""
        assert derive_app_id("app@v2") == "app-v2"
        assert derive_app_id("my.app.name") == "my-app-name"

    def test_consecutive_hyphens_collapsed(self):
        """Test that consecutive hyphens are collapsed to single hyphen."""
        assert derive_app_id("my--app") == "my-app"
        assert derive_app_id("app___name") == "app-name"
        assert derive_app_id("app - name") == "app-name"

    def test_leading_trailing_hyphens_stripped(self):
        """Test that leading/trailing hyphens are stripped."""
        assert derive_app_id("-myapp") == "myapp"
        assert derive_app_id("myapp-") == "myapp"
        assert derive_app_id("-myapp-") == "myapp"
        assert derive_app_id("--myapp--") == "myapp"

    def test_preserves_valid_names(self):
        """Test that already valid names are preserved."""
        assert derive_app_id("signalk-server") == "signalk-server"
        assert derive_app_id("influxdb") == "influxdb"
        assert derive_app_id("my-cool-app-v2") == "my-cool-app-v2"

    def test_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            derive_app_id("")

    def test_only_special_chars_raises(self):
        """Test that string with only special chars raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            derive_app_id("@#$%")


class TestExpandDependency:
    """Tests for expand_dependency function."""

    def test_at_reference_with_prefix(self):
        """Test expanding @ reference with prefix."""
        result = expand_dependency("@influxdb", prefix="marine")
        assert result == "marine-influxdb-container"

    def test_at_reference_without_prefix(self):
        """Test expanding @ reference without prefix."""
        result = expand_dependency("@influxdb", prefix=None)
        assert result == "influxdb-container"

    def test_system_package_unchanged(self):
        """Test that system packages are unchanged."""
        assert expand_dependency("docker-ce", prefix="marine") == "docker-ce"
        assert expand_dependency("nginx", prefix="marine") == "nginx"
        assert expand_dependency("python3", prefix="halos") == "python3"

    def test_system_package_with_version(self):
        """Test that system packages with version constraints are unchanged."""
        result = expand_dependency("docker-ce (>= 20.10)", prefix="marine")
        assert result == "docker-ce (>= 20.10)"

    def test_full_package_name_unchanged(self):
        """Test that explicit full package names are unchanged."""
        result = expand_dependency("casaos-redis-container", prefix="marine")
        assert result == "casaos-redis-container"

    def test_alternative_packages_unchanged(self):
        """Test that alternative package syntax is unchanged."""
        result = expand_dependency(
            "docker-ce (>= 20.10) | docker.io (>= 20.10)", prefix="marine"
        )
        assert result == "docker-ce (>= 20.10) | docker.io (>= 20.10)"

    def test_complex_at_reference(self):
        """Test @ reference with complex app_id."""
        result = expand_dependency("@signal-k-server", prefix="marine")
        assert result == "marine-signal-k-server-container"

    def test_at_only_raises(self):
        """Test that @ alone raises ValueError."""
        with pytest.raises(ValueError, match="without an app_id"):
            expand_dependency("@", prefix="marine")


class TestExpandDependencies:
    """Tests for expand_dependencies function (batch processing)."""

    def test_expand_list(self):
        """Test expanding a list of dependencies."""
        deps = ["docker-ce (>= 20.10)", "@influxdb", "@grafana"]
        result = expand_dependencies(deps, prefix="marine")

        assert result == [
            "docker-ce (>= 20.10)",
            "marine-influxdb-container",
            "marine-grafana-container",
        ]

    def test_empty_list(self):
        """Test expanding empty list."""
        assert expand_dependencies([], prefix="marine") == []

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert expand_dependencies(None, prefix="marine") is None

    def test_mixed_dependencies(self):
        """Test mix of system packages, @ refs, and full names."""
        deps = [
            "docker-ce (>= 20.10) | docker.io (>= 20.10)",
            "@influxdb",
            "nginx",
            "casaos-redis-container",
            "@signal-k-server",
        ]
        result = expand_dependencies(deps, prefix="marine")

        assert result == [
            "docker-ce (>= 20.10) | docker.io (>= 20.10)",
            "marine-influxdb-container",
            "nginx",
            "casaos-redis-container",
            "marine-signal-k-server-container",
        ]


class TestEdgeCases:
    """Edge case tests for naming module."""

    def test_numeric_app_id(self):
        """Test app_id starting with number (should still work for derive)."""
        # Directory names can start with numbers
        result = derive_app_id("2fauth")
        assert result == "2fauth"

    def test_very_long_app_id(self):
        """Test very long app_id."""
        long_name = "a" * 100
        result = compute_package_name(long_name, prefix="marine")
        assert result == f"marine-{long_name}-container"

    def test_unicode_characters_in_derive(self):
        """Test unicode characters are handled in derive_app_id."""
        # Unicode should be stripped/converted
        result = derive_app_id("app-über-cool")
        # Should handle gracefully - either strip or convert
        assert "-" not in result or result.isascii() or "uber" in result.lower()
