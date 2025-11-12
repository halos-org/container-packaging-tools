"""Entry point for generate-container-packages command."""

import sys

from generate_container_packages.cli import main

if __name__ == "__main__":
    sys.exit(main())
