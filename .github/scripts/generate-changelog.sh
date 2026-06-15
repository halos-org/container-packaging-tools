#!/bin/bash
set -euo pipefail

# Generate debian/changelog dynamically for CI builds
# Usage: generate-changelog.sh --upstream <version> --revision <N>
# Example: generate-changelog.sh --upstream 0.2.0 --revision 2
#
# Generates a debian/changelog entry with format: <upstream>-<revision>

UPSTREAM=""
REVISION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --upstream)
            UPSTREAM="$2"
            shift 2
            ;;
        --revision)
            REVISION="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown option $1" >&2
            echo "Usage: $0 --upstream <version> --revision <N>" >&2
            exit 1
            ;;
    esac
done

if [ -z "$UPSTREAM" ] || [ -z "$REVISION" ]; then
    echo "Error: Both --upstream and --revision are required" >&2
    echo "Usage: $0 --upstream <version> --revision <N>" >&2
    exit 1
fi

# Package name
PACKAGE_NAME="container-packaging-tools"

# Debian version format: upstream-revision
DEBIAN_VERSION="${UPSTREAM}-${REVISION}"

# Distribution (unstable for CI builds)
DISTRIBUTION="unstable"

# Urgency
URGENCY="medium"

# Maintainer information
MAINTAINER_NAME="${MAINTAINER_NAME:-Matti Airas}"
MAINTAINER_EMAIL="${MAINTAINER_EMAIL:-matti.airas@hatlabs.fi}"

# Date in RFC 2822 format
DATE=$(date -R)

# Fold commit subjects into changelog bullets wrapped at 80 columns. lintian's
# debian-changelog-line-too-long warning is fatal in the release build
# (--fail-on warning), and conventional-commit subjects can exceed the limit
# once the "  * " prefix is added.
wrap_changes() {
    while IFS= read -r subject; do
        [ -z "$subject" ] && continue
        printf '%s\n' "$subject" \
            | fold -s -w 76 \
            | sed -e 's/[[:space:]]*$//' -e '1s/^/  * /' -e '1!s/^/    /'
    done
}

# Get commits since last published (non-pre-release) tag.
LAST_TAG=$(git tag -l "v*" --sort=-version:refname | grep -v "_pre" | head -n1 || echo "")

# tformat (not format) terminates every subject with a newline so the read
# loop in wrap_changes does not drop the last commit.
if [ -n "$LAST_TAG" ]; then
    CHANGES=$(git log "${LAST_TAG}"..HEAD --pretty=tformat:"%s" --no-merges -- | wrap_changes)
else
    # No previous tags, use recent commits
    CHANGES=$(git log -10 --pretty=tformat:"%s" --no-merges | wrap_changes)
fi

# If no changes (shouldn't happen), use a default message
if [ -z "$CHANGES" ]; then
    CHANGES="  * Build ${REVISION}"
fi

# Generate debian/changelog entry
cat > debian/changelog <<EOF
${PACKAGE_NAME} (${DEBIAN_VERSION}) ${DISTRIBUTION}; urgency=${URGENCY}

${CHANGES}

 -- ${MAINTAINER_NAME} <${MAINTAINER_EMAIL}>  ${DATE}
EOF

echo "Generated debian/changelog:"
echo "  Version: ${DEBIAN_VERSION}"
echo "  Distribution: ${DISTRIBUTION}"
cat debian/changelog
