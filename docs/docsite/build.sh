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

set -e

pushd "$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
trap "{ popd; }" EXIT

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
