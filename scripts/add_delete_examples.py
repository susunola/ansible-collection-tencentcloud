#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add the missing ``state: absent`` example to a write module.

Why
---
270 write modules accept ``state: absent`` and 70 showed it. The delete example
is the one a reader copies when they want something gone, and it is the call
with the least room for guessing: which option identifies the resource, and
which create-only parameters the module still demands.

Where the text comes from
-------------------------
Nothing is invented. The identity options are the ones the module itself reads
to find or delete the resource -- the lookup helper it calls before the state
branch, the options its ``required_one_of`` group names, and whatever it marks
required -- and the values are the ones the module's own create example already
uses, so the pair reads as one resource being created and then removed.

An option the delete path reads that is *not* identity (``alb_load_balancer``
refuses to delete a load balancer whose ``deletion_protection`` is on) is taken
from the unit test's delete call, because copying the create example's ``true``
would document a call the API rejects. A module is skipped rather than guessed
at when any of that is missing.

What it will not touch
----------------------
A module that already shows ``state: absent`` somewhere in ``EXAMPLES``.

Usage
-----
    python scripts/add_delete_examples.py            # insert
    python scripts/add_delete_examples.py --check    # exit 1 while any remain
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enrich_state_docs import DOC_RE, resource_noun  # noqa: E402  (path setup first)

EXAMPLES_RE = re.compile(r"EXAMPLES\s*=\s*r?(?P<q>\'\'\'|\"\"\")(?P<body>.*?)(?P=q)", re.S)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "plugins", "modules")
UNIT_TESTS = os.path.join(REPO_ROOT, "tests", "unit", "plugins", "modules")

#: Options that configure a run rather than identify a resource.
RUNTIME_KNOBS = {
    "client_token", "retries", "retry_delay", "waiter_delay", "waiter_timeout",
    "force", "purge", "region", "state",
}

#: A test that asserts "nothing happened" passes an id that does not exist;
#: its values describe a resource that is not there.
GHOST_MARKERS = ("ghost", "missing", "nope", "no-such", "nosuch", "unknown")


def module_paths():
    return sorted(glob.glob(os.path.join(MODULES_DIR, "*.py")))


def _documentation(source):
    match = DOC_RE.search(source)
    if not match:
        return None
    try:
        parsed = yaml.safe_load(match.group("body"))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def create_example(source):
    """The options the module's first example task passes."""
    match = EXAMPLES_RE.search(source)
    if not match:
        return None
    try:
        parsed = yaml.safe_load(match.group("body"))
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, list):
        return None
    for task in parsed:
        if not isinstance(task, dict):
            continue
        for key, value in task.items():
            if isinstance(value, dict) and key.startswith("susunola.tencentcloud."):
                return value
    return None


def _option_refs(node):
    """Option names read under *node* as ``p["x"]`` / ``params.get("x")``."""
    found = set()
    for child in ast.walk(node):
        if (isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name)
                and child.value.id in ("p", "params")):
            if isinstance(child.slice, ast.Constant) and isinstance(child.slice.value, str):
                found.add(child.slice.value)
        if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                and child.func.attr == "get"):
            value = child.func.value
            if isinstance(value, ast.Name) and value.id in ("p", "params") and child.args:
                first = child.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    found.add(first.value)
    return found


def _reachable_helpers(source):
    """Return (run_module, reach) for a parsed module source.

    ``reach(name)`` is every option read by that function and by everything it
    calls, which is how an option used three helpers deep is still attributed
    to the path that uses it.
    """
    from enrich_state_docs import _called_names

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None, None
    run_module = next((node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == "run_module"), None)
    if run_module is None:
        return None, None
    helpers = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    resolved = {}

    def reach(name, seen=None):
        seen = set() if seen is None else seen
        if name in resolved:
            return resolved[name]
        if name in seen or name not in helpers:
            return set()
        seen = seen | {name}
        found = _option_refs(helpers[name])
        for called in _called_names(helpers[name]):
            found |= reach(called, seen)
        resolved[name] = found
        return found

    return run_module, reach


def lookup_reads(source):
    """Options the module reads to *find* the resource it manages.

    These are the identity: the options a delete call has to carry so the
    module can locate what it is deleting. A lookup helper may take the whole
    parameter mapping -- ``find(module, client, models, p)`` -- or the values
    it needs -- ``find_topic(module, client, models, topic_id, logset_id,
    name)`` -- so the arguments at the call site are mapped back to the
    parameter names before the helper's body is read.
    """
    run_module, reach = _reachable_helpers(source)
    if run_module is None:
        return set()
    reads = set()
    for node in ast.walk(run_module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if not re.match(r"(find|describe|lookup|get|list)_", node.func.id):
            continue
        reads |= reach(node.func.id)
        reads |= _argument_options(source, node)
    return reads


def _argument_options(source, call):
    """Options passed into a helper as individual arguments.

    ``find_topic(..., p["topic_id"], p["logset_id"], p["name"])`` yields the
    three option names, so a helper that reads its own ``topic_id`` parameter
    is still understood to be reading that option.
    """
    options = set()
    for argument in list(call.args):
        if (isinstance(argument, ast.Subscript) and isinstance(argument.value, ast.Name)
                and argument.value.id in ("p", "params")
                and isinstance(argument.slice, ast.Constant)
                and isinstance(argument.slice.value, str)):
            options.add(argument.slice.value)
        elif (isinstance(argument, ast.Call) and isinstance(argument.func, ast.Attribute)
                and argument.func.attr == "get" and isinstance(argument.func.value, ast.Name)
                and argument.func.value.id in ("p", "params") and argument.args):
            first = argument.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                options.add(first.value)
    return options


def delete_reads(source):
    """Options the module reads on the ``state=absent`` path."""
    from enrich_state_docs import _branch_polarity, _called_names

    run_module, reach = _reachable_helpers(source)
    if run_module is None:
        return set()
    reads = set()
    for node in ast.walk(run_module):
        if isinstance(node, ast.If) and _branch_polarity(node) == "body_absent":
            for statement in node.body:
                reads |= _option_refs(statement)
                for called in _called_names(statement):
                    reads |= reach(called)
    return reads


def one_of_members(source):
    match = re.search(r"required_one_of=\[(.*?)\]\s*[,)]", source, re.S)
    if not match:
        return set()
    try:
        return {str(option) for group in ast.literal_eval("[" + match.group(1) + "]")
                for option in group}
    except (SyntaxError, ValueError):
        return set()


def _is_ghost(value):
    return isinstance(value, str) and any(marker in value.lower() for marker in GHOST_MARKERS)


def delete_call_values(name):
    """{option: value} a unit test passes on a delete that really deletes.

    Only the options the test sets explicitly and that are not a resource that
    does not exist. Used for the flags the delete path reads but which are not
    part of the identity -- a load balancer whose ``deletion_protection`` the
    create example turns on cannot be deleted while it stays on.
    """
    values = {}
    for path in sorted(glob.glob(os.path.join(UNIT_TESTS, "test_%s*.py" % name))):
        if os.path.basename(path) == "test_%s_info.py" % name and not name.endswith("_info"):
            continue
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = getattr(func, "id", None) or getattr(func, "attr", "")
            if called not in ("module_args", "_args", "_params", "_base", "_run_args"):
                continue
            kwargs = {k.arg: k.value for k in node.keywords if k.arg}
            raw = kwargs.get("state")
            if not (isinstance(raw, ast.Constant) and raw.value == "absent"):
                continue
            for key, value in kwargs.items():
                if key in RUNTIME_KNOBS or key.startswith("_") or key in values:
                    continue
                try:
                    literal = ast.literal_eval(value)
                except Exception:
                    continue
                if literal is None or _is_ghost(literal):
                    continue
                values[key] = literal
    return values


def delete_options(source, name, create):
    """Return {option: value} for a delete example, or None when not provable.

    ``None`` also stands for "this module needs a person": the rule refuses to
    write a call whose required options it cannot fill from the module's own
    example.
    """
    doc = _documentation(source) or {}
    options = doc.get("options") or {}
    required = {option for option, spec in options.items()
                if isinstance(spec, dict) and spec.get("required")}
    if [option for option in required if option not in create]:
        return None

    identity = lookup_reads(source) | one_of_members(source) | required
    chosen = {option: value for option, value in create.items()
              if option in identity and option not in RUNTIME_KNOBS and value is not None}

    # A flag the delete path reads but which is not the identity is *not*
    # copied from the create example: that value may be the one that makes the
    # delete fail. alb_load_balancer's create example turns deletion protection
    # on, and the module refuses to delete a protected load balancer -- the
    # value comes from the unit test's delete call instead, or the option is
    # left out.
    test_values = delete_call_values(name)
    for option in sorted(delete_reads(source) - identity):
        if option in options and option in test_values:
            chosen[option] = test_values[option]
    return chosen


def render(name, noun, options):
    """Render the delete task."""
    lines = ["- name: Delete the %s" % noun if noun else "- name: Delete the resource",
             "  susunola.tencentcloud.%s:" % name, "    state: absent"]
    for option in sorted(options):
        value = options[option]
        if isinstance(value, (list, dict)):
            rendered = "%s: %s" % (option, yaml.dump(value, default_flow_style=True,
                                                     width=100).strip())
        else:
            rendered = yaml.dump({option: value}, default_flow_style=False,
                                 width=100, sort_keys=False).strip()
        lines.append("    %s" % rendered)
    return "\n".join(lines) + "\n"


def needs_example(source):
    """True when the module supports ``state: absent`` and never shows it."""
    doc = _documentation(source)
    if not doc:
        return False
    state = (doc.get("options") or {}).get("state")
    if not isinstance(state, dict) or "absent" not in (state.get("choices") or []):
        return False
    match = EXAMPLES_RE.search(source)
    if not match:
        return False
    return not re.search(r"state:\s*[\"']?absent", match.group("body"))


def enrich(source, name):
    """Return a new module source with a delete example, or None."""
    if not needs_example(source):
        return None
    create = create_example(source)
    if not isinstance(create, dict):
        return None
    chosen = delete_options(source, name, create)
    if not chosen:
        return None
    match = EXAMPLES_RE.search(source)
    block = render(name, resource_noun(source), chosen)
    body = match.group("body").rstrip("\n") + "\n\n" + block
    return source[:match.start("body")] + body + source[match.end("body"):]


def candidates():
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        name = os.path.basename(path)[:-3]
        new_source = enrich(source, name)
        if new_source is not None and new_source != source:
            found.append((path, source, new_source))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 while any write module is missing a delete example")
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the examples instead of writing them")
    args = parser.parse_args(argv)

    found = candidates()
    if args.show:
        for path, _source, new_source in found[:6]:
            print("── %s" % os.path.relpath(path, REPO_ROOT))
            body = EXAMPLES_RE.search(new_source).group("body")
            print("\n".join(body.rstrip("\n").split("\n")[-9:]))
        return 0

    if args.check:
        if found:
            for path, _source, _new in found:
                print("%s: accepts state=absent and shows only how to create"
                      % os.path.relpath(path, REPO_ROOT))
            print("delete examples: %d module(s) document creation only" % len(found))
            return 1
        print("delete examples: every module that supports deletion shows it")
        return 0

    for path, _source, new_source in found:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(new_source)
    print("delete examples: documented %d module(s)" % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
