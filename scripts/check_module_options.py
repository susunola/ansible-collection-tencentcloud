#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that an option a module declares is an option the module reads.

Why
---
``validate-modules`` checks that the documentation matches the argument spec,
and the example checker checks that the examples pass options the spec
declares. Nothing checked the other direction: a declared option that no code
path reads. ``ckafka_topic`` declared ``tags`` and never sent it, so a user
who set tags got a topic without them and no warning -- the same failure the
plugin option check found in ``tencentcloud_sg.include_sgless``.

What it checks
--------------
Every top-level option of every module must be read somewhere: its name
appears as a string literal beyond its own declaration, or in one of the
module helpers the module imports (``cos.resolve_appid(module)`` reads
``appid`` inside ``module_utils/cos.py``, and that counts).

Two things are deliberately out of scope:

* **nested options.** A sub-option may be consumed by a generic mapper that
  renames keys -- ``mqtt_instance._items`` turns ``vpc_id`` into ``VpcId``
  with ``str.capitalize`` -- so requiring a literal read would cry wolf.
* **an option with one choice.** ``tse_governance_host_retirement`` offers
  ``state: absent`` (choices and default both ``absent``) so the module
  matches the collection's convention; a constant cannot be branched on, so
  there is nothing to read.

Usage
-----
    python scripts/check_module_options.py            # the census
    python scripts/check_module_options.py --check    # exit 1 on any finding
"""

from __future__ import absolute_import, division, print_function

import argparse
import ast
import re
import sys
from pathlib import Path

__metaclass__ = type

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "plugins" / "modules"

#: A helper the module imports, e.g.
#: ``from ...plugins.module_utils.cos import resolve_appid``.
HELPER_RE = re.compile(
    r"from ansible_collections\.susunola\.tencentcloud\.plugins\."
    r"(module_utils|plugin_utils)(?:\.(\w+))?\s+import\s+([^\n]+)")

SPEC_KEYS = frozenset((
    "type", "required", "default", "choices", "no_log", "elements", "options",
    "suboptions", "description", "aliases", "fallback",
))


def _as_dict(node):
    """Return ``{key: value}`` for a dict literal of string keys, else None."""
    if not isinstance(node, ast.Dict):
        return None
    items = {}
    for key, value in zip(node.keys, node.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            return None
        items[key.value] = value
    return items


def _is_option_mapping(node):
    """True when *node* is a dict of ``name -> option spec``.

    A dict whose keys are all option-spec keys is itself a spec -- the
    ``rule = {"type": "dict", "options": {...}}`` a module defines once and
    reuses -- not a mapping of option names.
    """
    items = _as_dict(node)
    if not items or set(items) <= SPEC_KEYS:
        return False
    specs = sum(1 for value in items.values()
                if set(_as_dict(value) or {}) & SPEC_KEYS)
    return bool(specs) and specs * 2 >= len(items)


def _literal(node, default=None):
    """Return the value of a literal node, or *default*."""
    return node.value if isinstance(node, ast.Constant) else default


def declared_options(tree):
    """Return ``{option: (spec, node)}`` for every top-level argument spec.

    A nested ``options``/``suboptions`` mapping is skipped: it is reached
    through its parent, and sub-options are out of scope.
    """
    nested = set()
    for node in ast.walk(tree):
        for value in (_as_dict(node) or {}).values():
            spec = _as_dict(value) or {}
            for key in ("options", "suboptions"):
                if isinstance(spec.get(key), ast.Dict):
                    nested.add(id(spec[key]))
    declared = {}
    for node in ast.walk(tree):
        if id(node) in nested or not _is_option_mapping(node):
            continue
        for name, value in _as_dict(node).items():
            spec = _as_dict(value)
            if spec is not None:
                declared.setdefault(name, (spec, value))
    return declared


def imported_helpers(text):
    """Return the helper source files a module imports."""
    paths = set()
    for match in HELPER_RE.finditer(text):
        package, module, names = match.groups()
        if module:
            paths.add(REPO_ROOT / "plugins" / package / ("%s.py" % module))
            continue
        for name in names.split("#")[0].split(","):
            name = name.strip().split(" as ")[0].strip()
            if name:
                paths.add(REPO_ROOT / "plugins" / package / ("%s.py" % name))
    return sorted(path for path in paths if path.is_file())


def option_occurrences(text, option):
    """Return how often *option* appears as a string literal in *text*."""
    return len(re.findall(r"""["']%s["']""" % re.escape(option), text))


def unread_options(path):
    """Return ``(option, line, reason)`` for the unread options of one module."""
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    helper_text = "\n".join(helper.read_text(encoding="utf-8")
                            for helper in imported_helpers(text))
    findings = []
    for option, (spec, node) in sorted(declared_options(tree).items()):
        choices = spec.get("choices")
        values = [_literal(entry) for entry in choices.elts] \
            if isinstance(choices, (ast.List, ast.Tuple)) else None
        if values and len(values) == 1 and _literal(spec.get("default")) == values[0]:
            continue  # a constant: there is nothing to branch on
        occurrences = option_occurrences(text, option)
        if occurrences + option_occurrences(helper_text, option) > 1:
            continue  # declared once, read somewhere else
        findings.append((option, node.lineno,
                         "no code path reads it (checked the module and the "
                         "helpers it imports)"))
    return findings


def module_paths():
    """Return every module source file, sorted."""
    return sorted(MODULES_DIR.glob("*.py")) if MODULES_DIR.is_dir() else []


def findings():
    """Return the problems for the whole collection."""
    problems = []
    for path in module_paths():
        relative = str(path.relative_to(REPO_ROOT))
        for option, line, reason in unread_options(path):
            problems.append("%s:%d: option %r is declared but %s"
                            % (relative, line, option, reason))
    return sorted(problems)


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any finding")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    problems = findings()
    print("%d module(s) checked, %d declared option(s) nothing reads"
          % (len(module_paths()), len(problems)), file=out)
    if problems:
        print("findings (%d):" % len(problems), file=out)
        for problem in problems:
            print("  %s" % problem, file=out)
    if problems and args.check:
        print("a declared option must be one the module reads: send it to the "
              "API, drop it, or document why it is inert", file=err)
        return 1
    if not problems:
        print("module option check OK: every declared option is read", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
