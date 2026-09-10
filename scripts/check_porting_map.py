#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Keep docs/porting.md's module-name table honest.

``docs/porting.md`` is a translation table: one column names a Terraform
resource, the next names the collection module that replaces it. The modules
in that table exist in ``plugins/modules/`` *today*, but a rename lands in
the modules and never touches the prose — so the guide rots silently, and
every reader who trusts it writes a module name that no longer resolves.

This script parses the markdown tables in ``docs/porting.md`` and asserts that
every bare ``susunola.tencentcloud.<name>`` or ``<name>`` token appearing in a
table cell that names a collection module actually resolves to a file under
``plugins/modules/``. It cannot prove the guide is right, only that it does not
name modules that have been renamed or removed.

Run ``python scripts/check_porting_map.py --check`` in CI; exit 1 on any
unresolved name.
"""

from __future__ import absolute_import, division, print_function

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTING_DOC = REPO_ROOT / "docs" / "porting.md"
MODULES_DIR = REPO_ROOT / "plugins" / "modules"

# Tokens that look like module names but are not — product-domain nouns used in
# prose, action-group names, and the provider's own identifiers. Kept small and
# explicit so a real miss is never swallowed.
ALLOWED_NON_MODULES = {
    "all",            # group/susunola.tencentcloud.all action group
    "tencentcloud",   # the provider name
    "group",
}

_BACKTICK_RE = re.compile(r"`([^`]+)`")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.*)\|\s*$")
_FQCN_RE = re.compile(r"^susunola\.tencentcloud\.([A-Za-z0-9_]+)$")
# A mapping row names exactly one module in its second cell: a single
# backtick wrapping a bare stem or an FQCN, with nothing else around it. This
# is what the two resource-map tables in docs/porting.md look like, and it is
# narrow enough to ignore the prose cells in every other table (option names,
# method names, Terraform keywords).
_MAP_CELL_RE = re.compile(r"^`(?:susunola\.tencentcloud\.)?[A-Za-z0-9_]+`$")
# A row is a resource-map row when its first cell names a real Terraform
# provider resource (a backticked `tencentcloud_<word>`, not the `<x>` /
# placeholder form used in the conceptual mental-model table). That is the
# signal that the second cell is meant to be a module name rather than prose.
_TF_RESOURCE_RE = re.compile(r"`tencentcloud_[a-z][a-z0-9_]*`")


def module_names():
    """The set of module stems that currently ship."""
    if not MODULES_DIR.is_dir():
        return set()
    return {p.stem for p in MODULES_DIR.glob("*.py")}


def mapping_module(cells):
    """The collection module named by a porting.md mapping row, or None.

    A mapping row names exactly one module in its second cell: a single
    backtick wrapping a bare stem or an FQCN, with nothing else around it. This
    is what the two resource-map tables in docs/porting.md look like, and it is
    narrow enough to ignore the prose cells in every other table (option names,
    method names, Terraform keywords).
    """
    if len(cells) < 2:
        return None
    # Only resource-map rows name a module: the first cell must name a real
    # Terraform provider resource (not the "<x>" placeholder from the mental
    # model table). This keeps the conceptual and credential tables out.
    if not _TF_RESOURCE_RE.search(cells[0]):
        return None
    col2 = cells[1].strip()
    if not _MAP_CELL_RE.match(col2):
        return None
    token = _BACKTICK_RE.findall(col2)[0]
    m = _FQCN_RE.match(token)
    name = m.group(1) if m else token
    if name in ALLOWED_NON_MODULES:
        return None
    return name


def table_rows(text):
    """Yield (line_no, [cell, ...]) for each markdown table row in text."""
    for i, line in enumerate(text.splitlines(), 1):
        if _TABLE_ROW_RE.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Skip the separator row (---|---).
            if all(set(c) <= set("-: ") for c in cells):
                continue
            yield i, cells


def check(doc_path=None):
    """Return (problems, seen) where problems is a list of error strings."""
    doc_path = doc_path or PORTING_DOC
    problems = []
    seen = set()
    if not doc_path.is_file():
        return ["docs/porting.md is missing"], seen

    names = module_names()
    text = doc_path.read_text(encoding="utf-8")

    for line_no, cells in table_rows(text):
        name = mapping_module(cells)
        if name is None:
            continue
        seen.add(name)
        if name not in names:
            problems.append(
                "%s:%d: `%s` is not a module in plugins/modules/"
                % (doc_path.name, line_no, name)
            )
    return problems, seen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any named module is missing from plugins/modules/",
    )
    parser.add_argument(
        "--path",
        default=str(PORTING_DOC),
        help="path to the porting doc (default: docs/porting.md)",
    )
    args = parser.parse_args(argv)

    problems, seen = check(Path(args.path).resolve())
    if problems:
        for p in problems:
            print("FAIL %s" % p, file=sys.stderr)
        print(
            "check_porting_map: %d unresolved module name(s) in %d table row(s)"
            % (len(problems), len(seen)),
            file=sys.stderr,
        )
        if args.check:
            return 1
    else:
        print(
            "check_porting_map: OK — %d module name(s) in docs/porting.md resolve"
            % len(seen)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
