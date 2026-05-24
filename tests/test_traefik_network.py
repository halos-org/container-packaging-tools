"""Tests for Traefik proxy-network injection."""

from generate_container_packages.traefik import inject_proxy_network


class TestInjectProxyNetwork:
    """Tests for inject_proxy_network function."""

    def test_adds_network_to_compose(self) -> None:
        """Network is added to compose when not host networking."""
        compose = {"services": {"app": {}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "networks" in result
        assert "halos-proxy-network" in result["networks"]
        assert result["networks"]["halos-proxy-network"]["external"] is True

    def test_adds_network_to_service(self) -> None:
        """Service gets network reference added."""
        compose = {"services": {"app": {}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "networks" in result["services"]["app"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]

    def test_host_network_no_changes(self) -> None:
        """Host networking apps don't get network added."""
        compose = {"services": {"app": {"network_mode": "host"}}}
        result = inject_proxy_network(compose, is_host_network=True)

        assert "networks" not in result or "halos-proxy-network" not in result.get(
            "networks", {}
        )

    def test_preserves_existing_networks(self) -> None:
        """Existing networks are preserved."""
        compose = {
            "services": {"app": {"networks": ["existing-net"]}},
            "networks": {"existing-net": {}},
        }
        result = inject_proxy_network(compose, is_host_network=False)

        assert "existing-net" in result["networks"]
        assert "halos-proxy-network" in result["networks"]
        assert "existing-net" in result["services"]["app"]["networks"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]

    def test_converts_list_networks_to_list_with_new_network(self) -> None:
        """List-format service networks get new network appended."""
        compose = {"services": {"app": {"networks": ["existing"]}}}
        result = inject_proxy_network(compose, is_host_network=False)

        assert "existing" in result["services"]["app"]["networks"]
        assert "halos-proxy-network" in result["services"]["app"]["networks"]
