#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that an option which is a secret by name cannot reach a log.

Why
---
A credential that reaches a log is a credential that has leaked: Ansible
writes module arguments and results to the controller's log, to ``-v`` output
and to callback plugins. ``no_log: True`` is the only thing that keeps an
option's value out of them, and nothing checked that the options that need it
have it. The reverse failure -- interpolating a secret *value* into a message
-- leaks just as directly, and nothing checked that either.

What it checks
--------------
* every option (module, doc fragment or shared argument spec, at any nesting
  depth) whose name is a secret by construction -- ``password``,
  ``secret_key``, ``private_key``, ``api_key``, ``token``, ... -- and whose
  type is not ``bool`` declares ``no_log: True``. A flag cannot carry a
  secret, so ``rotate_password`` is deliberately out of scope: a name-based
  rule that flagged it would cry wolf and get switched off;
* no message string built with ``%``, ``.format()`` or an f-string
  interpolates a value read from a secret-named option.

The census today is clean -- 31 secret-shaped options, every one already
``no_log``, and zero interpolations -- which is the point: this is the guard
that keeps it that way rather than a bug list.

Usage
-----
    python scripts/check_secret_handling.py            # the census
    python scripts/check_secret_handling.py --check    # exit 1 on any finding
"""

from __future__ import absolute_import, division, print_function

import argparse
import ast
import re
import sys
from pathlib import Path

__metaclass__ = type

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRS = ("modules", "module_utils", "plugin_utils", "doc_fragments",
               "inventory", "lookup", "action", "event_source")

#: Option names that are a secret by construction. The pattern is anchored at
#: the end of the name so ``token_ttl`` and ``secret_name`` are not caught: a
#: name that merely mentions a secret is not a secret.
SECRET_NAME_RE = re.compile(
    r"(^|_)(password|passwd|secret|secret_id|secret_key|private_key|api_key|"
    r"access_key_secret|access_token|refresh_token|sas_token|token)$", re.I)

#: Names that match :data:`SECRET_NAME_RE` but are not credentials. An SDK
#: idempotency token is echoed back in ``tc_api_calls`` on purpose, so a
#: retried run can be told apart from a first one; hiding it would make that
#: trail useless.
NOT_SECRET_NAMES = frozenset(("client_token",))

#: A mapping is an argument spec when its values are option mappings; those
#: carry at least one of these keys.
SPEC_KEYS = frozenset((
    "type", "required", "default", "choices", "no_log", "elements", "options",
    "suboptions", "description", "aliases", "fallback",
))

NESTED_KEYS = ("options", "suboptions")


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
    """True when *node* is a dict of ``name -> option spec``."""
    items = _as_dict(node)
    if not items:
        return False
    specs = 0
    for value in items.values():
        spec = _as_dict(value)
        if spec is not None and set(spec) & SPEC_KEYS:
            specs += 1
    return specs and specs * 2 >= len(items)


def _literal(node, default=None):
    """Return the value of a literal node, or *default*."""
    if isinstance(node, ast.Constant):
        return node.value
    return default


def option_specs(text, path="<string>"):
    """Return ``(option_path, spec_dict, node)`` for every declared option.

    The nested ``options``/``suboptions`` mapping is itself a dict of option
    specs, so it is collected once, through its parent, and skipped when the
    walk reaches it directly -- otherwise ``account.secret_key`` would be
    reported twice, once nested and once as a top-level ``secret_key``.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    nested = set()
    for node in ast.walk(tree):
        items = _as_dict(node) or {}
        for value in items.values():
            spec = _as_dict(value) or {}
            for key in NESTED_KEYS:
                if isinstance(spec.get(key), ast.Dict):
                    nested.add(id(spec[key]))
    found = []
    for node in ast.walk(tree):
        if id(node) in nested or not _is_option_mapping(node):
            continue
        for name, value in _as_dict(node).items():
            spec = _as_dict(value)
            if spec is None:
                continue
            found.append(("%s" % name, spec, value))
            for key in NESTED_KEYS:
                found.extend(_nested_specs(spec.get(key), name))
    return found


def _nested_specs(node, prefix):
    """Return the options nested under ``options``/``suboptions``."""
    if not _is_option_mapping(node):
        return []
    found = []
    for name, value in _as_dict(node).items():
        spec = _as_dict(value)
        if spec is None:
            continue
        path = "%s.%s" % (prefix, name)
        found.append((path, spec, value))
        for nested in NESTED_KEYS:
            found.extend(_nested_specs(spec.get(nested), path))
    return found


def plugin_sources():
    """Return ``(relative_path, path)`` for every plugin source file."""
    sources = []
    for directory in PLUGIN_DIRS:
        root = REPO_ROOT / "plugins" / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            sources.append((str(path.relative_to(REPO_ROOT)), path))
    return sources


def secret_options():
    """Return the secret-shaped options and whether each declares ``no_log``."""
    rows = []
    for relative, path in plugin_sources():
        text = path.read_text(encoding="utf-8")
        for name, spec, node in option_specs(text, relative):
            # A nested option's path is ``parent.child``: the secret is the
            # last segment, so the anchors in SECRET_NAME_RE apply to it.
            if not SECRET_NAME_RE.search(name.rsplit(".", 1)[-1]):
                continue
            if name in NOT_SECRET_NAMES:
                continue
            rows.append(("%s:%d" % (relative, node.lineno), name,
                         _literal(spec.get("type"), "?"),
                         _literal(spec.get("no_log")) is True))
    return sorted(set(rows))


def no_log_findings():
    """Return the secret-shaped options that are not marked ``no_log``."""
    findings = []
    for relative, name, type_name, guarded in secret_options():
        if guarded or type_name == "bool":
            continue
        findings.append(
            "%s: option %r (type %s) is a secret by name and does not declare "
            "no_log: True" % (relative, name, type_name))
    return sorted(findings)


def _secret_references(node):
    """Return the secret-shaped names an expression reads."""
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and SECRET_NAME_RE.search(sub.id) \
                and sub.id not in NOT_SECRET_NAMES:
            found.append(sub.id)
        if isinstance(sub, ast.Subscript):
            index = sub.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str) \
                    and SECRET_NAME_RE.search(index.value) \
                    and index.value not in NOT_SECRET_NAMES:
                found.append(index.value)
    return found


def interpolation_findings():
    """Return the messages that interpolate a secret-shaped value."""
    findings = []
    for relative, path in plugin_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
                    and isinstance(node.left, ast.Constant) \
                    and isinstance(node.left.value, str):
                names = _secret_references(node.right)
            elif isinstance(node, ast.Call) \
                    and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "format":
                names = [name for arg in node.args
                         for name in _secret_references(arg)]
            elif isinstance(node, ast.JoinedStr):
                names = [name for value in node.values
                         if isinstance(value, ast.FormattedValue)
                         for name in _secret_references(value.value)]
            for name in sorted(set(names)):
                findings.append(
                    "%s:%d: a message interpolates %r, which is a secret by "
                    "name" % (relative, node.lineno, name))
    return sorted(set(findings))


def collect_findings():
    """Return the problems of both checks."""
    return sorted(set(no_log_findings()) | set(interpolation_findings()))


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any finding")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    options = secret_options()
    guarded = [row for row in options if row[3]]
    flags = [row for row in options if not row[3] and row[2] == "bool"]
    unguarded = len(options) - len(guarded) - len(flags)
    findings = collect_findings()
    print("%d secret-shaped option(s): %d with no_log: True, %d flag(s) that "
          "carry no secret, %d unguarded"
          % (len(options), len(guarded), len(flags), unguarded), file=out)
    if findings:
        print("findings (%d):" % len(findings), file=out)
        for finding in findings:
            print("  %s" % finding, file=out)
    if findings and args.check:
        print("an option that is a secret by name must carry no_log: True, and "
              "no message may interpolate its value", file=err)
        return 1
    if not findings:
        print("secret handling check OK: no unguarded secret, no interpolation",
              file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
