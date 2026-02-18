"""Tests for init injection."""

from generate_container_packages.init import inject_init


class TestInjectInit:
    """Tests for inject_init function."""

    def test_adds_init_to_single_service(self) -> None:
        """init: true is added to a service."""
        compose = {"services": {"app": {"image": "myapp:latest"}}}
        result = inject_init(compose)

        assert result["services"]["app"]["init"] is True

    def test_adds_init_to_all_services(self) -> None:
        """init: true is added to every service."""
        compose = {
            "services": {
                "app": {"image": "myapp:latest"},
                "db": {"image": "postgres:16"},
                "cache": {"image": "redis:7"},
            }
        }
        result = inject_init(compose)

        for name in ("app", "db", "cache"):
            assert result["services"][name]["init"] is True

    def test_does_not_overwrite_existing_init(self) -> None:
        """Existing init value is preserved."""
        compose = {"services": {"app": {"image": "myapp:latest", "init": False}}}
        result = inject_init(compose)

        assert result["services"]["app"]["init"] is False

    def test_does_not_modify_original(self) -> None:
        """Original compose dict is not modified."""
        compose = {"services": {"app": {"image": "myapp:latest"}}}
        result = inject_init(compose)

        assert "init" not in compose["services"]["app"]
        assert result["services"]["app"]["init"] is True

    def test_empty_services_returns_unchanged(self) -> None:
        """Compose with empty services returns unchanged."""
        compose = {"services": {}}
        result = inject_init(compose)
        assert result == {"services": {}}

    def test_no_services_returns_unchanged(self) -> None:
        """Compose without services key returns unchanged."""
        compose = {"version": "3"}
        result = inject_init(compose)
        assert result == {"version": "3"}

    def test_skips_non_dict_service(self) -> None:
        """Non-dict service entries are skipped without error."""
        compose = {"services": {"app": "not-a-dict"}}
        result = inject_init(compose)
        assert result["services"]["app"] == "not-a-dict"
