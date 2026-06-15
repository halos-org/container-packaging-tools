"""Generate the prestart OIDC section from a declarative routing.auth.oidc config.

For a native-OAuth app (`mode: oidc`), the generated prestart resolves the external
port (port-based redirects), appends the container's OIDC env vars to runtime.env,
and writes the Authelia client snippet to /etc/halos/oidc-clients.d/<client_id>.yml.

The snippet is written at prestart time (not build time) because port-based redirect
URIs embed the runtime-assigned port, and the core Authelia merger only expands the
literal ${HALOS_DOMAIN} token — every other dynamic value must be fully resolved
before the snippet is written. The client secret itself is generated once by postinst
(is_oidc_app); the prestart only reads it.
"""

from typing import Any

# Authelia issuer is always served at /sso by halos-core-containers.
_ISSUER_URL = "https://${HALOS_DOMAIN}/sso"


def _secret_file(package_name: str) -> str:
    return f"/var/lib/container-apps/{package_name}/data/oidc-secret"


def _redirect_uri(style: str, path: str, *, literal_domain: bool) -> str:
    """Build a redirect URI.

    literal_domain=True keeps ``${HALOS_DOMAIN}`` literal (for the Authelia snippet,
    which the merger expands per hostname). False lets it expand at prestart write
    time (for the container's own runtime.env value). The external port, when used,
    is always the resolved shell value ``${EXTERNAL_PORT}``.
    """
    domain = r"\${HALOS_DOMAIN}" if literal_domain else "${HALOS_DOMAIN}"
    port = ":${EXTERNAL_PORT}" if style == "port" else ""
    return f"https://{domain}{port}{path}"


def generate_oidc_section(
    oidc: dict[str, Any], app_id: str, package_name: str
) -> list[str]:
    """Return the bash lines for the prestart OIDC section.

    Args:
        oidc: the ``routing.auth.oidc`` config dict.
        app_id: app identifier (port-registry key and default client_id).
        package_name: package name (used for the secret-file path).
    """
    client_id = oidc.get("client_id") or app_id
    client_name = oidc["client_name"]
    scopes = oidc.get("scopes", ["openid", "profile", "email", "groups"])
    consent_mode = oidc.get("consent_mode", "implicit")
    token_auth = oidc.get("token_endpoint_auth_method", "client_secret_basic")
    redirect = oidc["redirect"]
    style = redirect["style"]
    path = redirect["path"]
    env_map: dict[str, str] = oidc.get("env", {})

    secret_file = _secret_file(package_name)

    lines = [
        "",
        "# --- OIDC client registration (generated from routing.auth.oidc) ---",
        f'OIDC_SECRET_FILE="{secret_file}"',
    ]

    # Port-based redirects need the runtime-assigned external port; validate it.
    if style == "port":
        lines.extend(
            [
                'EXTERNAL_PORT="$(grep "^'
                + app_id
                + '=" /etc/halos/port-registry 2>/dev/null | cut -d= -f2)"',
                'case "$EXTERNAL_PORT" in',
                '    ""|*[!0-9]*)',
                f'        echo "ERROR: no valid external port for {app_id} in'
                ' /etc/halos/port-registry" >&2',
                "        exit 1",
                "        ;;",
                "esac",
            ]
        )

    # Append the container's OIDC env vars (runtime.env, append-only).
    source_values = {
        "secret": '$(cat "$OIDC_SECRET_FILE")',
        "issuer": _ISSUER_URL,
        "redirect": _redirect_uri(style, path, literal_domain=False),
        "external_port": "${EXTERNAL_PORT}",
        "client_id": client_id,
    }
    for var_name, source in env_map.items():
        value = source_values[source]
        lines.append(f'echo "{var_name}={value}" >> "$RUNTIME_ENV"')

    # Write the Authelia client snippet (literal ${HALOS_DOMAIN}; port resolved).
    snippet_redirect = _redirect_uri(style, path, literal_domain=True)
    lines.extend(
        [
            "mkdir -p /etc/halos/oidc-clients.d",
            f"cat > /etc/halos/oidc-clients.d/{client_id}.yml << EOF",
            f"client_id: {client_id}",
            f"client_name: {client_name}",
            f"client_secret_file: {secret_file}",
            "redirect_uris:",
            f"  - '{snippet_redirect}'",
            f"scopes: [{', '.join(scopes)}]",
            f"consent_mode: {consent_mode}",
            f"token_endpoint_auth_method: {token_auth}",
            "EOF",
        ]
    )

    return lines
