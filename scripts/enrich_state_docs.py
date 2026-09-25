#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Say what each ``state`` choice does, using the calls the module makes.

Why
---
``state`` is the option every resource module has and the one a reader looks
at first. Eighty modules in the core subset described it as "Desired state.",
which is true of every ``state`` option in every collection and tells the
reader nothing they could not read off the two choices underneath. The
flagship modules say it properly -- ``cvm_instance`` names the API call behind
each choice and says what it waits for -- and the difference is not product
knowledge, it is that someone wrote it down.

The sentence is derivable. A module in this collection has one shape: it looks
the resource up, creates it with one API call when it is missing, updates it
with another when it differs, and deletes it with a third when asked. Which
calls those are is in the source, and the module's ``RETURN`` block names the
resource. So the description is generated from the module's own code:

    state:
      description:
        - C(present) creates the target group with V(CreateTargetGroup) when it
          does not exist and updates it with V(ModifyTargetGroupAttributes) when
          it differs. C(absent) deletes it with V(DeleteTargetGroups).
        - The module waits for the change to be observable before returning,
          bounded by O(waiter_timeout).

Nothing here is invented. The operation names are the ones the module passes
to ``sdk_call``, the noun is the key its ``RETURN`` block publishes, and the
waiting sentence appears only for modules that use a waiter.

What it will not touch
----------------------
Only a ``state`` option whose choices are exactly ``present`` and ``absent``
and whose description is still under ``MIN_DESCRIPTION`` characters. A module
with a longer description already says something a generator would overwrite,
and a module with other choices (``running``, ``rebooted``) has semantics this
shape does not cover.

Usage
-----
    python scripts/enrich_state_docs.py            # insert
    python scripts/enrich_state_docs.py --check    # exit 1 if any remain thin
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
CORE_SUBSET = os.path.join(REPO_ROOT, "tests", "quality", "core-subset.yml")

#: A description shorter than this says nothing beyond the option's name.
MIN_DESCRIPTION = 25

DOC_RE = re.compile(r"(?P<open>DOCUMENTATION\s*=\s*r?)(?P<q>'''|\"\"\")(?P<body>.*?)(?P=q)", re.S)
RETURN_RE = re.compile(r"RETURN\s*=\s*r?(?:'''|\"\"\")(?P<body>.*?)(?:'''|\"\"\")", re.S)

#: Operation prefixes, by what they do to the resource.
CREATE_VERBS = ("Create", "Run", "Add", "Register", "Allocate", "Import", "Apply", "Bind", "Attach", "Open")
UPDATE_VERBS = ("Modify", "Update", "Set", "Reset", "Replace", "Change", "Adjust", "Alter", "Rename", "Rebind")
DELETE_VERBS = ("Delete", "Remove", "Terminate", "Destroy", "Isolate", "Unbind", "Detach",
                "Release", "Purge", "Schedule", "Revoke", "Withdraw", "Expire", "Cancel")
#: Operations that read, so they are never mentioned as a change.
READ_VERBS = ("Describe", "List", "Get", "Query", "Check", "Search", "Inquire", "Fetch", "Preview")


def core_products():
    with open(CORE_SUBSET, encoding="utf-8") as handle:
        return set(yaml.safe_load(handle)["products"])


def module_paths():
    """Every core-subset module path, sorted."""
    products = core_products()
    found = []
    for path in sorted(glob.glob(os.path.join(MODULES_DIR, "*.py"))):
        name = os.path.basename(path)[:-3]
        if name.split("_")[0] in products:
            found.append(path)
    return found


def documentation(body):
    """Return the parsed DOCUMENTATION mapping of a module body, or None."""
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _classify(operation):
    for verbs, kind in ((READ_VERBS, "read"), (CREATE_VERBS, "create"),
                        (UPDATE_VERBS, "update"), (DELETE_VERBS, "delete")):
        if operation.startswith(verbs):
            return kind
    return "other"


def _operation_names(node, skip=None):
    """Every ``client.<Operation>`` referenced under *node*, in source order."""
    skip = set() if skip is None else skip
    found = []
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "client" and node.attr not in found):
        found.append(node.attr)
    for child in ast.iter_child_nodes(node):
        if id(child) in skip:
            continue
        for name in _operation_names(child, skip):
            if name not in found:
                found.append(name)
    return found


def _called_names(node):
    """Bare function names called under *node*."""
    found = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id not in found:
                found.append(child.func.id)
    return found


def _helper_operations(tree):
    """Map each module-level function to the client calls it can reach.

    Most modules here do not call the SDK from ``run_module``: they call
    ``_create``, ``_update``, ``_bind`` and friends, which hold the calls. A
    phase is therefore the set of calls reachable from its statements, not the
    calls written in them.
    """
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    resolved = {}

    def resolve(name, seen):
        if name in resolved:
            return resolved[name]
        if name in seen or name not in functions:
            return []
        seen = seen | {name}
        found = _operation_names(functions[name])
        for called in _called_names(functions[name]):
            for operation in resolve(called, seen):
                if operation not in found:
                    found.append(operation)
        resolved[name] = found
        return found

    return {name: resolve(name, set()) for name in functions}


def reachable_operations(statements, helpers):
    """Client calls reachable from a list of statements, in source order."""
    found = []
    for statement in statements:
        for operation in _operation_names(statement) + [
                operation for called in _called_names(statement)
                for operation in helpers.get(called, [])]:
            if operation not in found:
                found.append(operation)
    return found


def _branch_polarity(node):
    """Which side of an ``if`` is the absent path, or None if it is neither.

    Three spellings cover every module here: ``state == "absent"`` and
    ``not desired_present`` put the absent path in the body, while
    ``state == "present"`` and a bare ``desired_present`` put it in the
    ``else``. Reading the bare flag as an absent guard inverted the two phases
    and credited the create call to deletion.
    """
    test = ast.dump(node.test)
    if "desired_present" in test:
        negated = isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
        return "body_absent" if negated else "body_present"
    if "state" in test and "absent" in test:
        return "body_absent"
    if "state" in test and "present" in test:
        return "body_present"
    return None


def _phase_statements(run_module):
    """Split ``run_module`` into (present, absent) statement lists."""
    present, absent, inside_absent = [], [], set()

    def add_absent(statements):
        for statement in statements:
            absent.append(statement)
            for node in ast.walk(statement):
                inside_absent.add(id(node))

    branches = []
    for node in ast.walk(run_module):
        if not isinstance(node, ast.If):
            continue
        polarity = _branch_polarity(node)
        if polarity is None:
            continue
        branches.append(polarity)
        if polarity == "body_absent":
            add_absent(node.body)
            present.extend(node.orelse)
        else:
            present.extend(node.body)
            add_absent(node.orelse)

    # ``if state == "present": ... <absent code follows>`` -- only read this way
    # when the module has no absent guard at all, because a module that has one
    # and also mentions the present state is branching for another reason.
    if "body_absent" not in branches:
        for index, node in enumerate(run_module.body):
            if not isinstance(node, ast.If) or _branch_polarity(node) != "body_present":
                continue
            present.extend(node.body)
            add_absent(run_module.body[index + 1:])

    for node in ast.walk(run_module):
        if isinstance(node, ast.IfExp) and "present" in ast.dump(node.test):
            present.append(node.body)
            add_absent([node.orelse])
        elif isinstance(node, ast.IfExp) and "present" in ast.dump(node.orelse):
            present.append(node.orelse)
            add_absent([node.body])

    remaining = [node for node in run_module.body if id(node) not in inside_absent]
    return present + remaining, absent


def phase_operations(source):
    """Return {'create': [...], 'update': [...], 'delete': [...]} for a module.

    The split is made on the syntax tree rather than on line order, because
    modules here write the two branches in either order, choose the call with a
    ternary in some places, and delegate the call to a helper in others. A call
    is named under the choice that reaches it.

    A delete-shaped call reached on the present path is left out rather than
    reported under ``absent``: those are rollbacks that happen while
    reconciling, and naming them as the deletion would be wrong.
    """
    empty = {"create": [], "update": [], "delete": []}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return empty
    run_module = next((node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == "run_module"), None)
    if run_module is None:
        return empty
    helpers = _helper_operations(tree)

    present_statements, absent_statements = _phase_statements(run_module)
    present_operations = reachable_operations(present_statements, helpers)
    absent_operations = reachable_operations(absent_statements, helpers)

    found = {"create": [], "update": [], "delete": []}
    for operation in present_operations:
        kind = _classify(operation)
        if kind in ("read", "other", "delete"):
            continue
        if operation not in found[kind]:
            found[kind].append(operation)
    for operation in absent_operations:
        if _classify(operation) == "delete" and operation not in found["delete"]:
            found["delete"].append(operation)
    return found


def waits_for_change(source):
    """True when the module waits for the change to become observable."""
    return bool(re.search(r"wait_for_\w+\(", source) or "waiter_timeout" in source)


def resource_noun(body):
    """The noun the module uses for what it manages.

    Taken from the module's own ``RETURN`` key -- the name it publishes the
    resource under -- falling back to the module id with its product prefix
    dropped. ``alb_target_group`` publishes ``target_group``, so the sentence
    says "the target group" rather than "the resource".
    """
    match = RETURN_RE.search(body)
    if match:
        try:
            parsed = yaml.safe_load(match.group("body"))
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, dict):
            for key in parsed:
                if key not in ("changed", "diff", "request_id") and not key.endswith("_ids"):
                    return str(key).replace("_", " ")
    return None


def _join(operations):
    """An English list of calls: ``V(A)``, ``V(A)`` and ``V(B)``.

    More than one call in the same phase means the module chooses between
    them -- ``mariadb_instance`` creates with V(CreateHourDBInstance) or
    V(CreateDBInstance) depending on the billing mode -- so they are joined
    with "or" rather than listed as steps it performs.
    """
    calls = ["V(%s)" % operation for operation in operations]
    if len(calls) == 1:
        return calls[0]
    if len(calls) == 2:
        return "%s or %s" % (calls[0], calls[1])
    return "%s or %s" % (", ".join(calls[:-1]), calls[-1])


#: Deletion-family operations whose name says the resource is gone. Anything
#: else in that family (Isolate, Unbind, Detach, Schedule) is still what
#: ``state=absent`` calls, but "deletes it" would claim more than the call does.
GONE_VERBS = ("Delete", "Terminate", "Destroy", "Remove", "Purge")


def _absent_verb(operations):
    return "deletes it" if all(o.startswith(GONE_VERBS) for o in operations) else "removes it"


def build_description(noun, operations, waits):
    """Return the description lines for a ``state`` option."""
    the = "the %s" % noun if noun else "the resource"
    present = []
    if operations["create"]:
        present.append("creates %s with %s when it does not exist"
                       % (the, _join(operations["create"])))
    if operations["update"]:
        present.append("updates it with %s when it differs" % _join(operations["update"]))
    absent = []
    if operations["delete"]:
        absent.append("%s with %s" % (_absent_verb(operations["delete"]),
                                      _join(operations["delete"])))

    if not present and not absent:
        return []

    lines = []
    sentence = "C(present) %s." % " and ".join(present) if present else ""
    if absent:
        sentence = ("%s C(absent) %s." % (sentence, " and ".join(absent))).strip()
    lines.append(sentence)
    if waits:
        lines.append("The module waits for the change to be observable before returning, "
                     "bounded by O(waiter_timeout).")
    return lines


def _wrapped(lines, indent="    "):
    """Render the description as a block sequence in the house style."""
    from normalize_module_docs import _BlockSeq, _Dumper

    body = yaml.dump(_BlockSeq(lines), Dumper=_Dumper, default_flow_style=False,
                     sort_keys=False, width=100, allow_unicode=True, indent=2)
    return [indent + "  " + line for line in body.rstrip("\n").split("\n")]


def state_span(body):
    """Return (start, end) of the ``description`` value under ``options.state``.

    The span covers the lines that hold the value, so it can be replaced
    without touching the rest of the option (its type, choices and default).
    """
    lines = body.split("\n")
    in_options = False
    for index, line in enumerate(lines):
        if re.match(r"^options:\s*$", line):
            in_options = True
            continue
        if in_options and re.match(r"^[a-z_]+:", line):
            break
        if not in_options or not re.match(r"^  state:\s*$", line):
            continue
        for offset in range(index + 1, len(lines)):
            if re.match(r"^  \S", lines[offset]):
                break
            if re.match(r"^    description:\s*", lines[offset]):
                end = offset + 1
                while end < len(lines) and re.match(r"^ {6,}\S", lines[end]):
                    end += 1
                return offset, end
    return None


def thin_state(body):
    """True when ``options.state`` exists, is present/absent, and says too little.

    Ownership is deliberately not claimed here. Forty-six hand-written
    descriptions in this collection -- ``cvm_instance``, ``cdb_instance``,
    ``key_pair`` and the rest of the flagship set -- open with the same
    "C(present) " that this script writes, so a description cannot be claimed
    on its opening words, and claiming it on length alone would overwrite the
    text that made the module readable in the first place.
    """
    parsed = documentation(body)
    if not parsed:
        return False
    spec = (parsed.get("options") or {}).get("state")
    if not isinstance(spec, dict):
        return False
    if set(spec.get("choices") or []) != {"present", "absent"}:
        return False
    description = spec.get("description")
    items = description if isinstance(description, list) else [description]
    text = " ".join(str(item) for item in items if item is not None).strip()
    return len(text) < MIN_DESCRIPTION


def enrich(source):
    """Return a new module source with a derived state description, or None.

    Takes the whole module: the documentation block says whether the option
    needs the treatment, and the code says what to write.
    """
    match = DOC_RE.search(source)
    if not match:
        return None
    body = match.group("body")
    if not thin_state(body):
        return None
    span = state_span(body)
    if span is None:
        return None
    noun = resource_noun(source)
    operations = phase_operations(source)
    if not operations["create"] and not operations["update"]:
        return None
    if not operations["delete"]:
        # A present/absent option whose absent path could not be read would get
        # a description that never mentions deletion, which is worse than the
        # "Desired state." it has now.
        return None
    lines = build_description(noun, operations, waits_for_change(source))
    if not lines:
        return None
    start, end = span
    body_lines = body.split("\n")
    replacement = ["    description:"] + _wrapped(lines)
    new_body = "\n".join(body_lines[:start] + replacement + body_lines[end:])
    return source[:match.start("body")] + new_body + source[match.end("body"):]


def candidates():
    """Return [(path, source, new_source)] for every module still thin."""
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source = enrich(source)
        if new_source is None or new_source == source:
            # Nothing to change. The generator owns the sentences it wrote, so
            # a module it has already described comes back through here on
            # every run; only a difference is a finding.
            continue
        found.append((path, source, new_source))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 while any core module still has a thin state description")
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the generated description instead of writing")
    args = parser.parse_args(argv)

    found = candidates()
    if args.show:
        for path, _source, new_source in found[:5]:
            print("── %s" % os.path.relpath(path, REPO_ROOT))
            match = DOC_RE.search(new_source)
            span = state_span(match.group("body"))
            print("\n".join(match.group("body").split("\n")[span[0]:span[1]]))
        return 0

    if args.check:
        if found:
            for path, _source, _new in found:
                print("%s: state description says nothing about what it does"
                      % os.path.relpath(path, REPO_ROOT))
            print("state docs: %d core module(s) still describe state as just a desired value"
                  % len(found))
            return 1
        print("state docs: every core module with a present/absent state names its calls")
        return 0

    for path, _source, new_source in found:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(new_source)
    print("state docs: described %d module(s)" % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
