⚠️ **THESE RULES ONLY APPLY TO FILES IN /container-packaging-tools/** ⚠️

# Container Packaging Tools

Tooling for generating Debian packages from container application definitions.

**Local Instructions**: For environment-specific instructions and configurations, see @CLAUDE.local.md (not committed to version control).

## Git Workflow Policy

**IMPORTANT:** Always ask before pushing, creating/pushing tags, or running destructive git operations that affect remote repositories. Local commits and branch operations are fine.

**Branch Workflow:** Never push to main directly - always use feature branches and PRs.

## Project Purpose

This package provides `generate-container-packages` command that converts simple container app definitions into full Debian packages. The goal is to make it easy for developers to add new container apps without understanding Debian packaging internals.

## Repository Structure

```
container-packaging-tools/
├── src/
│   ├── generate_container_packages.py  # Main script
│   ├── templates/                      # Jinja2 templates for Debian files
│   │   ├── control.template
│   │   ├── rules.template
│   │   ├── postinst.template
│   │   └── systemd.service.template
│   └── schemas/                        # JSON schemas for validation
│       ├── metadata.schema.json
│       └── config.schema.json
├── debian/                             # Debian packaging for this tool
│   ├── control
│   ├── rules
│   └── ...
├── tests/                              # Unit tests
├── docs/
│   └── DESIGN.md                       # Detailed design
├── requirements.txt                    # Python dependencies
├── pyproject.toml                      # Python packaging
└── README.md
```

## Development

**Tech Stack**:
- Python 3.11+
- Jinja2 for templating
- jsonschema for validation
- Click for CLI

**Setup**:
```bash
pip install -e .[dev]
```

**Testing**:
```bash
pytest
mypy src/
ruff check src/
```

## Building the Package

```bash
dpkg-buildpackage -us -uc
```

## Related

- **Parent**: [../CLAUDE.md](../CLAUDE.md) - Workspace documentation
- **Users**: [halos-marine-containers](https://github.com/hatlabs/halos-marine-containers)
