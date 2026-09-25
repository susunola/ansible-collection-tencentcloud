#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add an ``attributes`` block documenting check mode and idempotency.

Reviewer request (ansible-inclusion#89):

    MUST FIX: Please add the ``attribute`` fields to the DOCUMENTATION
    sections of your modules with info about check mode support and
    idempotency (full / partial, etc.).

No module in the collection had one, so a reader could not tell from the
documentation whether C(check_mode) is honoured or whether a second run is a
no-op.  The support level is derived from the code rather than blanket-filled:

* ``check_mode`` -- from ``supports_check_mode`` in the module's own
  ``AnsibleModule``/``TencentCloudModule`` call.
* ``idempotency`` -- ``full`` when the module reconciles drift (it imports
  ``maybe_diff``) or is read-only; ``partial`` when it does not compare
  against live state, which is the case for one-shot actions and for the few
  modules that only issue a write.  A partial module that always acts
  (``state=rebooted``, ``restarted``, an ``invoke``/``run`` style action) says
  so explicitly, because that is the part a user cannot infer from the option
  list.

Usage
-----
    python scripts/add_module_attributes.py           # insert
    python scripts/add_module_attributes.py --check   # exit 1 if any missing
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
MODULE_GLOB = os.path.join(REPO_ROOT, "plugins", "modules", "*.py")

_DOC_RE = re.compile(
    r"(?P<open>DOCUMENTATION\s*=\s*r?)(?P<q>'''|\"\"\")(?P<body>.*?)(?P=q)", re.S)

# A state value that always performs the action instead of converging to it.
_ONE_SHOT_STATES = ("rebooted", "restarted", "invoked", "run", "executed",
                    "rotated", "retried", "resumed")

#: States whose meaning is the module's, not the word's. ``started`` converges
#: for a resource with a running/stopped lifecycle -- ``lighthouse_instance``
#: starts an instance that is stopped and reports C(changed=false) when it is
#: already running -- and creates a new record for an action module.
#: ``tat_invocation`` says so itself, in its own description: "This is an
#: action module; C(state=started) creates a new invocation on every
#: execution." It claimed ``idempotent: full`` anyway, because the derived rule
#: only knew the one-shot words above.
_MODULE_ONE_SHOT_STATES = {
    "tat_invocation": ("cancelled", "started"),
}


def _state_choices(text):
    """Return the values the ``state`` option accepts, sorted."""
    for choices in re.findall(r'"state":\s*\{[^}]*"choices":\s*\[([^\]]*)\]', text):
        return sorted(set(re.findall(r'"([a-z_]+)"', choices)))
    return []


def _one_shot_states(text, name=None):
    found = set(_MODULE_ONE_SHOT_STATES.get(name, ()))
    for choices in re.findall(r'"state":\s*\{[^}]*"choices":\s*\[([^\]]*)\]', text):
        for value in re.findall(r'"([a-z_]+)"', choices):
            if value in _ONE_SHOT_STATES:
                found.add(value)
    return sorted(found)


def _check_mode_support(text):
    if "supports_check_mode=True" in text:
        return "full"
    if "supports_check_mode=False" in text:
        return "none"
    return "none"


def _wrapped(text, indent="  ", width=64):
    """Render ``description:`` as a quoted, wrapped block list.

    The text is emitted through PyYAML rather than by hand: a description such
    as ``Can run in C(check_mode): ...`` contains ``": "``, which turns a
    plain scalar into a mapping and produces YAML no parser will load.  The
    emitter quotes only when it has to, so the readable cases stay unquoted.
    """
    from normalize_module_docs import _BlockSeq, _Dumper  # same house style

    body = yaml.dump(_BlockSeq([text]), Dumper=_Dumper, default_flow_style=False,
                     sort_keys=False, width=width, allow_unicode=True, indent=2)
    lines = body.rstrip("\n").split("\n")
    return [indent + "description:"] + [indent + "  " + line for line in lines]


def build_block(text, relpath):
    """Return the attributes block lines for one module.

    ``idempotency`` is derived from whether the module can know the current
    state at all.  The collection reconciles resources against the cloud, so
    a module that reads the resource back (any Describe/List/Get/Query call)
    is idempotent by construction, whatever helper it uses to compare --
    ``tag``, for instance, reconciles by comparing resource-ID sets and does
    not go through ``maybe_diff``.  Only a module that never reads state, or
    one with a one-shot action, has to declare ``partial``.
    """
    check_mode = _check_mode_support(text)
    read_only = relpath.endswith("_info.py")
    # A module reconciles when it can know the current state.  There is no
    # single naming convention for that in this collection, so look for all of
    # them: the API 3.0 style (client.DescribeX), the COS modules (they read
    # through module_utils helpers such as cos.iter_objects), the collection's
    # drift helpers, and the read-back helpers modules define for themselves
    # (is_attached, find_policy, current/desired pairs).
    reads_state = bool(
        "maybe_diff" in text
        or "require_immutable_unchanged" in text
        or re.search(r"client\.(?:Describe|List|Get|Query)\w+", text)
        or re.search(r"\b(?:describe|list|get|find|iter|wait_for|is)_[a-z0-9_]+\s*\(", text))
    one_shot = _one_shot_states(text, os.path.basename(relpath)[:-3])
    all_states = _state_choices(text)

    if read_only:
        idem_support = "full"
        idem_desc = ("Read-only, so every run returns the current state and never "
                     "changes the target, and a repeated run reports "
                     "C(changed=false).")
        idem_details = None
    elif one_shot and all_states and set(one_shot) >= set(all_states):
        # An action module with no converging state at all. Saying "most
        # C(state) values converge" about a module where none does is the same
        # kind of untrue sentence as the claim this replaced.
        idem_support = "partial"
        idem_desc = ("Every C(state) value (%s) performs the action on every run "
                     "and always reports C(changed=true)."
                     % ", ".join("C(state=%s)" % state for state in one_shot))
        idem_details = ("There is no state to compare against, so a repeat run "
                        "cannot report C(changed=false).")
    elif one_shot:
        idem_support = "partial"
        states = "), C(state=".join(one_shot)
        idem_desc = ("Most C(state) values converge and are idempotent, but "
                     "C(state=%s) performs the action on every run and always "
                     "reports C(changed=true)." % states)
        idem_details = ("C(state=%s) has no settled state to converge to, so it "
                        "cannot report C(changed=false) on a repeat run." % states)
    elif reads_state:
        idem_support = "full"
        idem_desc = ("Reconciles the resource against its live state, so running "
                     "again with the same arguments leaves it unchanged and "
                     "reports C(changed=false).")
        idem_details = None
    else:
        idem_support = "partial"
        idem_desc = ("The module does not read the resource back to compare it "
                     "with the requested state, so a repeated run may issue the "
                     "write again instead of reporting C(changed=false).")
        idem_details = ("The module cannot tell whether the resource already "
                        "matches the request, so a repeated run may repeat the "
                        "write.")

    if check_mode == "full":
        cm_desc = ("Can run in C(check_mode), reading the current state and "
                   "predicting the result without issuing a write API call.")
    else:
        cm_desc = "Does not support C(check_mode)."

    lines = ["attributes:", "  check_mode:"]
    lines += _wrapped(cm_desc, "    ")
    lines.append("    support: %s" % check_mode)

    # ``diff_mode`` is one of the three attributes ansible-core actually
    # defines (ansible.builtin.action_common_attributes, alongside check_mode
    # and platform), and the collection can state it precisely: a module that
    # calls maybe_diff() builds a before/after payload.
    if "maybe_diff" in text:
        lines.append("  diff_mode:")
        lines += _wrapped(
            "Returns the difference between the observed and the requested state "
            "when the task runs with C(--diff).", "    ")
        lines.append("    support: full")

    # The key is ``idempotent``, not ``idempotency``: ansible-core defines no
    # such attribute, and community.postgresql -- the collection the reviewer
    # pointed at as the example -- spells it ``idempotent``.
    lines.append("  idempotent:")
    lines += _wrapped(idem_desc, "    ")
    lines.append("    support: %s" % idem_support)
    if idem_details:
        # The documentation standard requires details whenever support is
        # partial, so a reader learns how it falls short rather than only that
        # it does.
        lines.append("    details: %s" % idem_details)
    return lines


def add_attributes(source, relpath):
    """Return (new_source, changed)."""
    match = _DOC_RE.search(source)
    if not match:
        return source, False
    body = match.group("body")
    if re.search(r"^attributes:", body, re.M):
        return source, False

    block = build_block(source, relpath)
    # Insert before ``author:`` when present so the block sits with the other
    # top-level documentation keys; otherwise append at the end.
    author = re.search(r"^author:.*$", body, re.M)
    if author:
        new_body = body[:author.start()] + "\n".join(block) + "\n" + body[author.start():]
    else:
        new_body = body.rstrip("\n") + "\n" + "\n".join(block) + "\n"
    start = match.start("body")
    return source[:start] + new_body + source[match.end("body"):], True


#: How strong a claim is. ``full`` is the strongest, and any attribute block
#: may claim less than the rules allow -- ``alb_listener`` says ``partial`` for
#: both ``diff_mode`` and ``idempotent`` and explains why, which is more useful
#: than the boilerplate. It may not claim more.
_SUPPORT_RANK = {"none": 0, "partial": 1, "full": 2}
_ATTRIBUTES = ("check_mode", "diff_mode", "idempotent")


def _committed_supports(body):
    """Return {attribute: support} for the attributes block in *body*."""
    block = re.search(r"(?m)^attributes:\n((?:[ \t]+.*\n|\n)*)", body)
    if not block:
        return {}
    found = {}
    current = None
    for line in block.group(1).splitlines():
        match = re.match(r"^  ([a-z_]+):\s*$", line)
        if match:
            current = match.group(1)
            continue
        match = re.match(r"^    support:\s*(\w+)", line)
        if match and current:
            found[current] = match.group(1)
            current = None
    return found


def overclaimed(text, relpath):
    """Return the attributes whose committed claim is stronger than allowed.

    The generator used to insert a block once and never look at it again, so a
    module could claim ``idempotent: full`` for the rest of its life and every
    check stayed green -- ``tat_invocation`` claimed exactly that while its own
    description says "this is an action module; C(state=started) creates a new
    invocation on every execution", and every one of its exit paths passes
    ``changed=True``. Comparing the committed support levels against the
    derived ones is what makes the claim checkable.
    """
    match = _DOC_RE.search(text)
    if not match:
        return []
    committed = _committed_supports(match.group("body"))
    if not committed:
        return []
    derived = {}
    for line in build_block(text, relpath):
        found = re.match(r"^  ([a-z_]+):\s*$", line)
        if found:
            current = found.group(1)
            continue
        found = re.match(r"^    support:\s*(\w+)", line)
        if found and current:
            derived[current] = found.group(1)
    problems = []
    for name in _ATTRIBUTES:
        claimed = committed.get(name)
        allowed = derived.get(name)
        if claimed is None or allowed is None:
            continue
        if _SUPPORT_RANK.get(claimed, 0) > _SUPPORT_RANK.get(allowed, 0):
            problems.append("%s: claims support=%s, the module's code supports %s"
                            % (name, claimed, allowed))
    return problems


def module_paths():
    return sorted(glob.glob(MODULE_GLOB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report modules without an attributes block")
    args = parser.parse_args()

    missing = []
    overclaimed_found = []
    for path in module_paths():
        relpath = os.path.relpath(path, REPO_ROOT)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source, changed = add_attributes(source, relpath)
        if changed:
            missing.append(path)
            if not args.check:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(new_source)
            continue
        for problem in overclaimed(source, relpath):
            overclaimed_found.append("%s: %s" % (relpath, problem))

    if args.check:
        for path in missing:
            print("%s: DOCUMENTATION has no attributes block"
                  % os.path.relpath(path, REPO_ROOT))
        for problem in overclaimed_found:
            print(problem)
        if missing or overclaimed_found:
            if missing:
                print("attributes: %d module(s) do not document check_mode/idempotency"
                      % len(missing))
            if overclaimed_found:
                print("attributes: %d claim(s) are stronger than the module supports"
                      % len(overclaimed_found))
            return 1
        print("attributes: all %d module(s) document check_mode and idempotent, "
              "and none overclaims" % len(module_paths()))
        return 0

    print("added an attributes block to %d module(s)" % len(missing))
    for problem in overclaimed_found:
        print("left alone (fix by hand): %s" % problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
