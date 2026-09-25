#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cross-reference a module with its read-only counterpart in ``seealso``.

Why
---
No module in the collection had a ``seealso`` block, so nothing pointed a
reader from ``vpc`` to ``vpc_info`` or back.  That is the one navigation step
users need most: they read a write module, and want to know how to list what it
manages without changing anything.

The link is mechanical and checkable: 365 write modules have a matching
``_info`` module, and the counterpart's own ``short_description`` says what it
does, so the description is quoted rather than invented.

Deliberately not included: ``seealso`` links to the Tencent Cloud API
reference.  Building that URL needs the numeric product id, which is not in
the repository, and a guessed URL that 404s is worse than no link.

Usage
-----
    python scripts/add_module_seealso.py           # insert
    python scripts/add_module_seealso.py --check   # exit 1 if any are missing
"""

from __future__ import absolute_import, division, print_function

import argparse
import glob
import os
import re
import sys

import yaml

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "plugins", "modules")
FQCN = "susunola.tencentcloud."

_DOC_RE = re.compile(
    r"(?P<open>DOCUMENTATION\s*=\s*r?)(?P<q>'''|\"\"\")(?P<body>.*?)(?P=q)", re.S)


def modules():
    return sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(MODULES_DIR, "*.py")))


def counterpart(name, known):
    """The read-only partner of *name*, or its write partner, or None."""
    if name.endswith("_info"):
        write = name[: -len("_info")]
        return write if write in known else None
    info = name + "_info"
    return info if info in known else None


def short_description(name):
    with open(os.path.join(MODULES_DIR, name + ".py"), encoding="utf-8") as handle:
        match = _DOC_RE.search(handle.read())
    doc = yaml.safe_load(match.group("body"))
    return (doc.get("short_description") or "").strip().rstrip(".")


def build_block(name, known):
    """Return the ``seealso`` lines for *name*, or [] when it has no partner."""
    other = counterpart(name, known)
    if other is None:
        return []
    return [
        "seealso:",
        "  - module: %s%s" % (FQCN, other),
        "    description: %s." % short_description(other),
    ]


def add_seealso(source, name, known):
    """Return (new_source, changed)."""
    match = _DOC_RE.search(source)
    if not match:
        return source, False
    body = match.group("body")
    if re.search(r"^seealso:", body, re.M):
        return source, False
    block = build_block(name, known)
    if not block:
        return source, False
    # ``seealso`` sits with the other top-level keys, before ``author``.
    author = re.search(r"^author:.*$", body, re.M)
    if author:
        new_body = body[: author.start()] + "\n".join(block) + "\n" + body[author.start():]
    else:
        new_body = body.rstrip("\n") + "\n" + "\n".join(block) + "\n"
    start = match.start("body")
    return source[:start] + new_body + source[match.end("body"):], True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report modules missing the cross-reference")
    args = parser.parse_args()

    known = set(modules())
    missing = []
    for name in sorted(known):
        path = os.path.join(MODULES_DIR, name + ".py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source, changed = add_seealso(source, name, known)
        if not changed:
            continue
        missing.append(name)
        if not args.check:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(new_source)

    expected = [n for n in known if counterpart(n, known)]
    if args.check:
        if missing:
            for name in missing:
                print("plugins/modules/%s.py: no seealso cross-reference" % name)
            print("seealso: %d of %d module(s) with a counterpart lack the link"
                  % (len(missing), len(expected)))
            return 1
        print("seealso: all %d module(s) with a counterpart cross-reference it"
              % len(expected))
        return 0

    print("added a seealso cross-reference to %d module(s)" % len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
