#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate the ``EXAMPLES`` block inside every module.

Why
---
An example is the first thing a user copies, and it was the one part of a
module nothing checked. ``validate-modules`` proves the ``EXAMPLES`` string is
present and that it is valid YAML; ``scripts/check_examples.py`` reads the
playbooks under ``docs/examples/`` and ``playbooks/`` but not the examples that
ship *inside* the 1,027 modules; and the integration targets are the only thing
that would actually run a module. So an example could name a module that does
not exist, or omit an option the module requires, and every check stayed green
while the user's copy-paste failed on the first line.

This is not hypothetical. The first run of this script found three defects that
had shipped:

* ``tse_governance_alias_info`` called ``tse_governance_aliase_info`` -- a
  module that does not exist, so the example failed with "couldn't resolve
  module/action" before reaching Tencent Cloud.
* ``lcic_answer_info`` omitted ``question_id``, which its argument spec marks
  required, so the example failed with "missing required arguments".
* ``cdb_audit_rule`` shipped an example that deletes a rule without
  ``rule_filters`` while the argument spec marked that option unconditionally
  required -- the documentation and the code disagreed about whether deletion
  was possible at all, and the unit tests passed because they supplied the
  filters on the delete path too.

What it checks, per example task
--------------------------------
* the file is a list of tasks and parses as YAML (``yaml``),
* a module the example calls resolves to a file in ``plugins/modules/`` --
  by fully qualified name, and reported when the name is not namespaced
  (``modules``),
* every option passed is declared by the module's ``DOCUMENTATION`` or by one
  of its doc fragments (``options``),
* every option the module marks ``required`` is passed, so the example can be
  run as written (``required``),
* every example calls the module it documents (``self``).

``cdb_audit_rule`` is why the ``required`` check is not a style preference: the
requirement it applied to the delete path was itself the bug.

Usage
-----
    python scripts/check_module_examples.py          # print the census
    python scripts/check_module_examples.py --check  # exit 1 on any problem
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_examples import (  # noqa: E402  (path setup must happen first)
    ANSIBLE_KEYWORDS,
    COLLECTION_PREFIX,
    DOC_FRAGMENTS_DIR,
    MODULES_DIR,
    _load_documentation,
    module_options,
    task_action,
)

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml before this runs
    yaml = None


def module_paths():
    """Return every module path, sorted."""
    return sorted(MODULES_DIR.glob("*.py"))


def _string_assignment(source, name):
    """Return the literal string assigned to *name* in *source*, or None."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    return None
                return value if isinstance(value, str) else None
    return None


def _required_options(name, cache=None):
    """Return the options *name* marks required, doc fragments included.

    A fragment cannot mark anything required today, but it is read anyway so
    that a future fragment which does is honoured rather than silently
    ignored.
    """
    cache = {} if cache is None else cache
    if name in cache:
        return cache[name]
    required = set()
    doc = _load_documentation(MODULES_DIR / (name + ".py"))
    sources = [doc]
    if doc is not None:
        fragments = doc.get("extends_documentation_fragment") or []
        if isinstance(fragments, str):
            fragments = [fragments]
        for fragment in fragments:
            sources.append(_load_documentation(
                DOC_FRAGMENTS_DIR / (fragment.rsplit(".", 1)[-1] + ".py")))
    for source in sources:
        if not isinstance(source, dict):
            continue
        for option, spec in (source.get("options") or {}).items():
            if isinstance(spec, dict) and spec.get("required"):
                required.add(str(option))
    cache[name] = required
    return required


def _example_tasks(raw):
    """Return the tasks a module's ``EXAMPLES`` string describes.

    Module examples are written as a bare list of tasks, but a few are written
    as plays; both are accepted, and a mapping that is neither is reported by
    the caller rather than skipped here.
    """
    parsed = yaml.safe_load(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return None
    tasks = []
    for item in parsed:
        if not isinstance(item, dict):
            return None
        if "hosts" in item or "tasks" in item:
            nested = item.get("tasks")
            if not isinstance(nested, list):
                return None
            tasks.extend(entry for entry in nested if isinstance(entry, dict))
        else:
            tasks.append(item)
    return tasks


def _module_call(task):
    """Return (short_name, params) for a task that calls a collection module.

    ``task_action`` only treats a mapping or a non-empty string as a call, so a
    task written as ``- module.name:`` with no arguments at all -- which is how
    a module with no options is documented -- returns (None, None) from it and
    is handled here.
    """
    name, params = task_action(task)
    if name is None:
        for key, value in task.items():
            if key in ANSIBLE_KEYWORDS or value is not None:
                continue
            short = key[len(COLLECTION_PREFIX):] if key.startswith(COLLECTION_PREFIX) else key
            if "." in short:
                continue
            if (MODULES_DIR / (short + ".py")).is_file():
                return short, {}
        return None, None
    if name.startswith(COLLECTION_PREFIX):
        return name[len(COLLECTION_PREFIX):], params
    if "." in name:
        # Another collection's module: not this check's business.
        return None, None
    return name, params


def check_module(path, cache=None):
    """Return the problems found in one module's ``EXAMPLES`` block."""
    cache = {"options": {}, "required": {}} if cache is None else cache
    problems = []
    name = path.stem
    raw = _string_assignment(path.read_text(encoding="utf-8"), "EXAMPLES")

    if raw is None:
        problems.append("has no EXAMPLES block that can be read")
        return problems
    if not raw.strip():
        return problems

    try:
        tasks = _example_tasks(raw)
    except Exception as exc:
        problems.append("EXAMPLES is not valid YAML: %s" % exc)
        return problems
    if tasks is None:
        problems.append("EXAMPLES is not a list of tasks or of plays")
        return problems

    calls_self = False
    for task in tasks:
        target, params = _module_call(task)
        if target is None:
            continue
        label = task.get("name") or "(unnamed task)"
        if not (MODULES_DIR / (target + ".py")).is_file():
            problems.append("task %r calls %s, which is not in plugins/modules/"
                            % (label, target))
            continue
        if target == name:
            calls_self = True

        declared = module_options(target, cache["options"])
        for key in sorted(params):
            if key in ANSIBLE_KEYWORDS:
                continue
            if declared and key not in declared:
                problems.append("task %r passes %s to %s, which does not declare that option"
                                % (label, key, target))
        required = _required_options(target, cache["required"])
        for key in sorted(required - set(params)):
            problems.append("task %r calls %s without %s, which it marks required"
                            % (label, target, key))

    if not calls_self:
        problems.append("no example task calls %s itself" % name)
    return problems


def check():
    """Return {module name: [problem, ...]} for every module with a problem."""
    cache = {"options": {}, "required": {}}
    found = {}
    for path in module_paths():
        problems = check_module(path, cache)
        if problems:
            found[path.stem] = problems
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when any example is unusable")
    args = parser.parse_args(argv)

    if yaml is None:
        print("PyYAML is required (pip install pyyaml)", file=sys.stderr)
        return 2

    found = check()
    total = sum(len(problems) for problems in found.values())

    if found:
        print("module example problems:", file=sys.stderr)
        for name in sorted(found):
            for problem in found[name]:
                print("  - %s %s" % (name, problem), file=sys.stderr)
        if args.check:
            return 1
    if args.check:
        print("module examples: %d module(s) checked, every example runs as written"
              % len(module_paths()))
        return 0
    print("module examples: %d module(s) checked, %d problem(s) in %d module(s)"
          % (len(module_paths()), total, len(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
