#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that every changelog fragment names a section the changelog defines.

Why
---
``antsibull-changelog lint`` is the real check, and it ran in exactly one
place: ``release.yml``, after the release tag exists. It rejects a fragment
filed under a section ``changelogs/config.yaml`` does not define -- ``bugfix``
instead of ``bugfixes`` -- and it rejects it with a non-zero exit that stops
the release. A fragment like that is valid YAML, so ``yamllint`` accepts it,
and the entry is silently dropped from the release notes if nobody looks.

This check is deliberately not a second implementation of that lint. It
answers one question, the one whose failure mode is both silent and late:
*does every top-level key of every fragment name a configured section?* The
authoritative lint still runs at release time, and the full dependency tree it
needs (pydantic, rstcheck, docutils) is not worth installing into three CI
legs to answer that one question.

Usage
-----
    python scripts/check_changelog_fragments.py            # the census
    python scripts/check_changelog_fragments.py --check    # exit 1 on a problem
"""

from __future__ import absolute_import, division, print_function

import argparse
import os
import sys

import yaml

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAGMENTS_DIR = os.path.join(REPO_ROOT, "changelogs", "fragments")
CONFIG = os.path.join(REPO_ROOT, "changelogs", "config.yaml")


def configured_sections():
    """Return the section names ``changelogs/config.yaml`` defines.

    ``prelude_section_name`` counts as well: it is how a fragment adds a
    release summary, and it is not part of the ``sections`` list.
    """
    with open(CONFIG, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    names = set()
    for entry in config.get("sections") or []:
        # Each entry is [name, title] in this repository's config.
        names.add(entry[0] if isinstance(entry, (list, tuple)) else str(entry))
    prelude = config.get("prelude_section_name")
    if prelude:
        names.add(prelude)
    return names


def fragment_paths():
    return sorted(
        os.path.join(FRAGMENTS_DIR, name)
        for name in os.listdir(FRAGMENTS_DIR)
        if name.endswith((".yml", ".yaml"))
    )


def findings():
    """Return [(fragment, problem)] for every fragment this check rejects."""
    known = configured_sections()
    found = []
    for path in fragment_paths():
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            found.append((name, "is not valid YAML: %s" % exc))
            continue
        if parsed is None:
            found.append((name, "is empty"))
            continue
        if not isinstance(parsed, dict):
            found.append((name, "is not a mapping of section to entries"))
            continue
        for section in parsed:
            if section not in known:
                found.append((name, "uses section %r, which is not one of: %s"
                              % (section, ", ".join(sorted(known)))))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when a fragment names an unknown section")
    args = parser.parse_args(argv)

    found = findings()
    if found:
        print("changelog fragment problems:", file=sys.stderr)
        for name, problem in found:
            print("  - %s %s" % (name, problem), file=sys.stderr)
        if args.check:
            return 1
    if args.check:
        print("changelog fragments: %d fragment(s) use a configured section"
              % len(fragment_paths()))
        return 0
    print("changelog fragments: %d fragment(s), %d problem(s)"
          % (len(fragment_paths()), len(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
