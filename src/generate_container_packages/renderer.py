"""Jinja2 template rendering engine for package file generation."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError

from generate_container_packages.loader import AppDefinition
from generate_container_packages.template_context import build_context


def setup_jinja_environment(template_dir: Path) -> Environment:
    """Set up Jinja2 environment with template directory.

    Args:
        template_dir: Path to directory containing Jinja2 templates

    Returns:
        Configured Jinja2 Environment

    Raises:
        FileNotFoundError: If template directory doesn't exist
    """
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,  # Don't escape - we're generating config files, not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    return env


def render_all_templates(
    app_def: AppDefinition, output_dir: Path, template_dir: Path | None = None
) -> None:
    """Render all templates and write to output directory.

    Args:
        app_def: Application definition with all parsed data
        output_dir: Directory to write rendered files
        template_dir: Template directory (defaults to installed location or local)

    Raises:
        TemplateError: If template rendering fails
        OSError: If file writing fails
    """
    # Determine template directory
    if template_dir is None:
        template_dir = _find_template_directory()

    # Set up Jinja2 environment
    env = setup_jinja_environment(template_dir)

    # Build template context
    context = build_context(app_def)

    # Create output directories
    debian_dir = output_dir / "debian"
    debian_dir.mkdir(parents=True, exist_ok=True)

    # Define templates to render
    templates = {
        # Debian control files
        "debian/control.j2": debian_dir / "control",
        "debian/rules.j2": debian_dir / "rules",
        "debian/changelog.j2": debian_dir / "changelog",
        "debian/copyright.j2": debian_dir / "copyright",
        # Maintainer scripts
        "debian/postinst.j2": debian_dir / "postinst",
        "debian/prerm.j2": debian_dir / "prerm",
        "debian/postrm.j2": debian_dir / "postrm",
        # systemd service
        "systemd/service.j2": debian_dir / f"{context['package']['name']}.service",
        # AppStream metadata
        "appstream/metainfo.xml.j2": debian_dir
        / f"{context['package']['name']}.metainfo.xml",
    }

    # Render each template
    for template_path, output_path in templates.items():
        try:
            template = env.get_template(template_path)
            rendered = template.render(context)
            write_rendered_file(rendered, output_path)
        except TemplateError as e:
            raise TemplateError(
                f"Failed to render template {template_path}: {e}"
            ) from e

    # Copy static files (compat)
    _copy_static_files(template_dir, debian_dir)

    # Set executable permissions on debian/rules and maintainer scripts
    _set_executable_permissions(debian_dir)


def write_rendered_file(content: str, output_path: Path) -> None:
    """Write rendered content to file.

    Args:
        content: Rendered template content
        output_path: Path to write file

    Raises:
        OSError: If file writing fails
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def _find_template_directory() -> Path:
    """Find template directory (installed or local).

    Returns:
        Path to templates directory

    Tries these locations in order:
    1. Installed location: /usr/share/container-packaging-tools/templates/
    2. Development location: ../templates/ relative to this file
    """
    # Try installed location first
    installed_path = Path("/usr/share/container-packaging-tools/templates")
    if installed_path.exists():
        return installed_path

    # Fall back to development location (relative to this file)
    dev_path = Path(__file__).parent.parent.parent / "templates"
    if dev_path.exists():
        return dev_path

    raise FileNotFoundError(
        f"Cannot find templates directory. Checked:\n  - {installed_path}\n  - {dev_path}"
    )


def _copy_static_files(template_dir: Path, output_dir: Path) -> None:
    """Copy static template files (non-.j2 files).

    Args:
        template_dir: Source template directory
        output_dir: Destination directory
    """
    # Copy debian/compat (static file)
    compat_src = template_dir / "debian" / "compat"
    if compat_src.exists():
        compat_dst = output_dir / "compat"
        compat_dst.write_text(compat_src.read_text())


def _set_executable_permissions(debian_dir: Path) -> None:
    """Set executable permissions on scripts.

    Args:
        debian_dir: Path to debian/ directory
    """
    # Scripts that need to be executable
    executable_files = [
        "rules",
        "postinst",
        "prerm",
        "postrm",
    ]

    for filename in executable_files:
        filepath = debian_dir / filename
        if filepath.exists():
            # Set executable: owner, group, others (755)
            os.chmod(filepath, 0o755)
