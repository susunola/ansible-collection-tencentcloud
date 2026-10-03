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
* every scalar passed matches the type the option declares -- an unquoted
  ``2.1`` is a float, not the documented string, and an unquoted
  ``1400000000_218695_1590065777`` is YAML digit grouping that collapses the
  underscores the API expects (``types``),
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


def _option_specs(name, cache=None):
    """Return the option spec mapping of *name*, doc fragments included.

    The module's own ``DOCUMENTATION`` is applied *last* so it wins any name
    the shared fragments also declare -- the same precedence as the runtime,
    where ``TencentCloudModule`` starts from ``base_argument_spec()`` and then
    lets the module's own argument spec ``update()`` over it (a module-local
    ``role_arn: int`` shadows the credentials fragment's assume-role
    ``role_arn: str``).
    """
    cache = {} if cache is None else cache
    if name in cache:
        return cache[name]
    specs = {}
    doc = _load_documentation(MODULES_DIR / (name + ".py"))
    sources = []
    if doc is not None:
        fragments = doc.get("extends_documentation_fragment") or []
        if isinstance(fragments, str):
            fragments = [fragments]
        for fragment in fragments:
            sources.append(_load_documentation(
                DOC_FRAGMENTS_DIR / (fragment.rsplit(".", 1)[-1] + ".py")))
    sources.append(doc)
    for source in sources:
        if isinstance(source, dict):
            for option, spec in (source.get("options") or {}).items():
                if isinstance(spec, dict):
                    specs[str(option)] = spec
    cache[name] = specs
    return specs


_DECLARED_TYPE = {
    "dict": dict,
    "list": list,
    "str": str,
    "path": str,
    "json": str,
    "jsonarg": str,
    "int": int,
    "bool": bool,
    "float": (int, float),
}


def _type_problem(declared, value):
    """Why *value* cannot be what the option declares, or None.

    Quoted scalars are accepted for ``int``/``float``/``bool`` because the
    argument spec casts them; everything else is a copy-paste that passes the
    wrong type -- or, worse, the right digits with YAML digit grouping eaten
    (``1400000000_218695_1590065777`` is one huge int, not the documented
    ``SdkAppId_RoomId_CreateTime`` string).
    """
    expected = _DECLARED_TYPE.get(declared)
    if expected is None:
        return None
    if isinstance(value, str):
        if "{{" in value:
            return None  # templated: the runtime decides the type
        if declared in ("int", "float", "bool"):
            return None  # a quoted scalar is cast by the argument spec
    if declared in ("int", "float") and isinstance(value, bool):
        return "is a boolean, which %s does not accept" % declared
    if declared == "bool" and value in (0, 1) and not isinstance(value, bool):
        return None  # 0/1 are accepted booleans in every argspec
    if not isinstance(value, expected):
        return "is %s, but the option is declared %s" % (
            type(value).__name__, declared)
    return None


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
    cache = {"options": {}, "required": {}, "specs": {}} if cache is None else cache
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
        specs = _option_specs(target, cache["specs"])
        for key in sorted(params):
            if key in ANSIBLE_KEYWORDS:
                continue
            if declared and key not in declared:
                problems.append("task %r passes %s to %s, which does not declare that option"
                                % (label, key, target))
                continue
            spec = specs.get(key)
            if spec is not None:
                why = _type_problem(spec.get("type"), params[key])
                if why is not None:
                    problems.append("task %r passes %s to %s: value %s"
                                    % (label, key, target, why))
        required = _required_options(target, cache["required"])
        for key in sorted(required - set(params)):
            problems.append("task %r calls %s without %s, which it marks required"
                            % (label, target, key))

    if not calls_self:
        problems.append("no example task calls %s itself" % name)
    return problems


def check():
    """Return {module name: [problem, ...]} for every module with a problem."""
    cache = {"options": {}, "required": {}, "specs": {}}
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
