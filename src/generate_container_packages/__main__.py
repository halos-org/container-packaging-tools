"""Entry point for generate-container-packages command."""

import sys

from generate_container_packages import __version__


def main():
    """Main entry point for CLI."""
    print("Container Packaging Tools")
    print(f"Version: {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
