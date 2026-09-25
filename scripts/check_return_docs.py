#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that a module documents what it returns.

Why
---
``RETURN`` is a promise: a playbook registers a module's result and branches on
a key. Nothing compared that promise with ``exit_json``. ``validate-modules``
checks the shape of the block -- that an entry has a description, a ``returned``
and a ``type`` -- and the integration targets assert the keys they happen to
use, which is a handful. So a module could return a key nobody was told about,
and four did:

* ``cvm_instance`` returns ``count``, ``instances`` and ``terminated`` in
  ``exact_count`` mode, which is the whole point of that mode;
* ``tdcpg_account`` returns ``password_rotated``;
* ``tdcpg_instance_state`` returns ``restarted``;
* ``tse_gateway_waf_domains`` returns ``added_domains`` and
  ``removed_domains``.

What it checks
--------------
Every keyword a module passes to ``exit_json`` is either documented in its
``RETURN`` block or is one of the keys Ansible itself adds to every result
(``changed``, ``msg``, ``invocation``, ...). The reverse direction -- a
documented key the module never returns -- is checked as well, but only for
modules that never splat a mapping, because a splat can carry keys this check
cannot read.

A keyword built in a comprehension or passed as ``**splat`` is invisible here,
which is deliberate: the check only reports what it can see.

Usage
-----
    python scripts/check_return_docs.py            # the census
    python scripts/check_return_docs.py --check    # exit 1 on any finding
"""

from __future__ import absolute_import, division, print_function

import argparse
import ast
import glob
import os
import re
import sys

import yaml

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "plugins", "modules")

RETURN_RE = re.compile(r"RETURN\s*=\s*r?(?P<q>'''|\"\"\")(?P<body>.*?)(?P=q)", re.S)

#: Keys Ansible adds to every module result, so documenting them is optional.
BUILTIN_KEYS = {
    "changed", "msg", "failed", "invocation", "diff", "warnings",
    "deprecations", "exception", "skipped",
}

#: The fields a documented return value has to carry.
REQUIRED_FIELDS = ("description", "returned", "type")


def module_paths():
    return sorted(glob.glob(os.path.join(MODULES_DIR, "*.py")))


def documented(body):
    """Return the parsed RETURN mapping, or None when it cannot be read."""
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def returned_keys(source):
    """Return (explicit keywords, whether a mapping is splatted)."""
    keys = set()
    splat = False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return keys, splat
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", "")
        if name != "exit_json":
            continue
        for keyword in node.keywords:
            if keyword.arg is None:
                splat = True
            else:
                keys.add(keyword.arg)
    return keys, splat


def _walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = "%s.%s" % (path, key) if path else str(key)
            yield key, value, here
            yield from _walk(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, "%s[%d]" % (path, index))


def findings():
    """Return [(module, problem)] for every return-documentation problem."""
    found = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        match = RETURN_RE.search(source)
        if not match:
            found.append((name, "has no RETURN block"))
            continue
        parsed = documented(match.group("body"))
        if parsed is None:
            found.append((name, "RETURN is not a mapping"))
            continue
        keys, splat = returned_keys(source)
        for key in sorted(keys - set(parsed) - BUILTIN_KEYS):
            found.append((name, "returns %s, which RETURN does not document" % key))
        if not splat:
            for key in sorted(set(parsed) - keys - BUILTIN_KEYS):
                found.append((name, "documents %s, which the module never returns" % key))
        for key, value, where in _walk(parsed):
            if not isinstance(value, dict) or "description" not in value:
                continue
            for field in REQUIRED_FIELDS:
                if field not in value:
                    found.append((name, "%s has no %s" % (where, field)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any return-documentation problem")
    args = parser.parse_args(argv)

    found = findings()
    if found:
        print("return documentation problems:", file=sys.stderr)
        for name, problem in found:
            print("  - %s %s" % (name, problem), file=sys.stderr)
        if args.check:
            return 1
    if args.check:
        print("return docs: %d module(s) document every key they return"
              % len(module_paths()))
        return 0
    print("return docs: %d module(s), %d problem(s)" % (len(module_paths()), len(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
