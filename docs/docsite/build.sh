#!/usr/bin/env bash
# Build the collection docsite into docsite/build/html.
#
# Requirements: the collection must be importable as susunola.tencentcloud,
# i.e. ANSIBLE_COLLECTIONS_PATH must point at the directory that contains
# ansible_collections/. From a checkout of this repository:
#
#   ANSIBLE_COLLECTIONS_PATH=/path/containing/ansible_collections \
#     docsite/build.sh
#
# The script is idempotent and safe to re-run: --cleanup
# similar-files-and-dirs removes generated pages for plugins that no longer
# exist while leaving the hand-written rst/index.rst in place (--cleanup
# everything would delete it and the Sphinx run would fail on a missing
# master document).
#
# ANSIBLE_COLLECTIONS_PATH is mandatory and checked, see below.

set -e

pushd "$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
trap "{ popd; }" EXIT

# antsibull-docs runs with --use-current, so it documents whatever copy of the
# collection ANSIBLE_COLLECTIONS_PATH resolves to -- *not* this checkout. Left
# unset it silently falls back to an installed copy, which is exactly how a
# stale 0.13.0 once overwrote a 1.4.0 tree (wrong version banner, missing
# plugin indices, no error anywhere). Refuse to build unless the resolved copy
# carries the same version as this checkout.
if [ -z "${ANSIBLE_COLLECTIONS_PATH:-}" ]; then
    echo "ANSIBLE_COLLECTIONS_PATH is unset." >&2
    echo "Set it to a directory containing ansible_collections/susunola/" >&2
    echo "tencentcloud -- a symlink to this checkout is enough -- otherwise" >&2
    echo "the docsite describes whichever copy happens to be installed." >&2
    exit 1
fi

repo_version=$(sed -n 's/^version:[[:space:]]*//p' ../../galaxy.yml | head -n 1)
resolved=""
OLDIFS=$IFS
IFS=:
for entry in $ANSIBLE_COLLECTIONS_PATH; do
    candidate="$entry/ansible_collections/susunola/tencentcloud/galaxy.yml"
    if [ -f "$candidate" ]; then
        resolved="$candidate"
        break
    fi
done
IFS=$OLDIFS

if [ -z "$resolved" ]; then
    echo "susunola.tencentcloud not found under ANSIBLE_COLLECTIONS_PATH" >&2
    echo "($ANSIBLE_COLLECTIONS_PATH)." >&2
    exit 1
fi

resolved_version=$(sed -n 's/^version:[[:space:]]*//p' "$resolved" | head -n 1)
if [ "$resolved_version" != "$repo_version" ]; then
    echo "Collection version mismatch." >&2
    echo "  this checkout: $repo_version" >&2
    echo "  resolved copy: $resolved_version ($resolved)" >&2
    echo "Refusing to build the docsite from a different copy." >&2
    exit 1
fi
echo "Documenting susunola.tencentcloud $repo_version from $resolved"

# Create collection documentation
mkdir -p rst
chmod og-w rst  # antsibull-docs wants that directory only writable by owner
antsibull-docs \
    --config-file antsibull-docs.cfg \
    collection \
    --cleanup similar-files-and-dirs \
    --fail-on-error \
    --use-current \
    --dest-dir rst \
    susunola.tencentcloud

# Build Sphinx site
sphinx-build -M html rst build -c . -W --keep-going
