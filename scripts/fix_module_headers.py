#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Insert the GPL-3.0-or-later header into module files that lack it.

Background
----------
``validate-modules`` requires the string ``GNU General Public License`` and a
version marker (``v3.0`` or ``version 3``) within the **first 20 lines** of
every module:

    header = '\\n'.join(self.text.split('\\n')[:20])
    if ('GNU General Public License' not in header or
            ('version 3' not in header and 'v3.0' not in header)):
        ...missing-gplv3-license

The collection is licensed GPL-3.0-or-later as a whole (``galaxy.yml``,
``LICENSE``, ``COPYING``), so a module missing the header is a per-file
declaration gap, not a licensing question.  ``docs/roadmap.md`` records the
result of leaving these in ``tests/sanity/ignore-*.txt``: 161 modules carried
a suppression for a two-line fix, and modules added afterwards were not even
suppressed -- they simply failed, invisible behind an earlier failing CI step.

Usage
-----
    python scripts/fix_module_headers.py           # insert missing headers
    python scripts/fix_module_headers.py --check   # exit 1 if any are missing
"""

from __future__ import absolute_import, division, print_function

import argparse
import glob
import os
import re
import sys

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_GLOB = os.path.join(REPO_ROOT, "plugins", "modules", "*.py")

# Mirrors the text used by modules that already pass the check, so the tree
# stays uniform (plugins/modules/vpc.py is the reference).
COPYRIGHT = "# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors"
LICENSE = ("# GNU General Public License v3.0+ "
           "(see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)")

# validate-modules only inspects the first 20 lines.
HEADER_WINDOW = 20
LICENSE_RE = re.compile(r"GNU General Public License")
VERSION_RE = re.compile(r"version 3|v3\.0", re.I)


def has_header(text):
    """True when the licence declaration is visible to validate-modules."""
    window = "\n".join(text.split("\n")[:HEADER_WINDOW])
    return bool(LICENSE_RE.search(window) and VERSION_RE.search(window))


def insert_at(lines):
    """Index just past the leading shebang/coding comment block.

    Comments and blank lines carry no semantics, so inserting there keeps
    ``from __future__`` first among statements and leaves the AST unchanged.
    """
    index = 0
    last_comment = -1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            last_comment = index
            index += 1
        elif not stripped:
            index += 1
        else:
            break
    return last_comment + 1


def add_header(text):
    """Return *text* with the header inserted, or the original when present."""
    if has_header(text):
        return text
    lines = text.split("\n")
    at = insert_at(lines)
    # A blank separator only when the following line is not already blank.
    block = [COPYRIGHT, LICENSE]
    if at < len(lines) and lines[at].strip():
        block.append("")
    return "\n".join(lines[:at] + block + lines[at:])


def module_paths():
    return sorted(glob.glob(MODULE_GLOB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report modules missing the header without editing")
    args = parser.parse_args()

    missing = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if has_header(text):
            continue
        missing.append(path)
        if not args.check:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(add_header(text))

    if args.check:
        if missing:
            for path in missing:
                print("%s: missing GPLv3 header in the first %d lines"
                      % (os.path.relpath(path, REPO_ROOT), HEADER_WINDOW))
            print("module headers: %d file(s) missing the GPLv3 declaration" % len(missing))
            return 1
        print("module headers: GPLv3 declared by all %d module file(s)" % len(module_paths()))
        return 0

    print("inserted the GPLv3 header into %d module file(s)" % len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
