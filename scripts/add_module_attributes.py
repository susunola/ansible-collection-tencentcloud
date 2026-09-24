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


def _one_shot_states(text):
    found = []
    for choices in re.findall(r'"state":\s*\{[^}]*"choices":\s*\[([^\]]*)\]', text):
        for value in re.findall(r'"([a-z_]+)"', choices):
            if value in _ONE_SHOT_STATES:
                found.append(value)
    return sorted(set(found))


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
    one_shot = _one_shot_states(text)

    if read_only:
        idem_support = "full"
        idem_desc = ("Read-only: every run returns the current state and never "
                     "changes the target, so a repeated run reports "
                     "C(changed=false).")
    elif one_shot:
        idem_support = "partial"
        idem_desc = ("Most C(state) values converge and are idempotent, but "
                     "C(state=%s) performs the action on every run and always "
                     "reports C(changed=true)."
                     % "), C(state=".join(one_shot))
    elif reads_state:
        idem_support = "full"
        idem_desc = ("Reconciles the resource against its live state: running "
                     "again with the same arguments leaves it unchanged and "
                     "reports C(changed=false).")
    else:
        idem_support = "partial"
        idem_desc = ("The module does not read the resource back to compare it "
                     "with the requested state, so a repeated run may issue the "
                     "write again instead of reporting C(changed=false).")

    if check_mode == "full":
        cm_desc = ("Can run in C(check_mode): the module reads the current state "
                   "and predicts the result without issuing a write API call.")
    else:
        cm_desc = "Does not support C(check_mode)."

    lines = ["attributes:", "  check_mode:"]
    lines += _wrapped(cm_desc, "    ")
    lines.append("    support: %s" % check_mode)
    lines.append("  idempotency:")
    lines += _wrapped(idem_desc, "    ")
    lines.append("    support: %s" % idem_support)
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


def module_paths():
    return sorted(glob.glob(MODULE_GLOB))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report modules without an attributes block")
    args = parser.parse_args()

    missing = []
    for path in module_paths():
        relpath = os.path.relpath(path, REPO_ROOT)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        new_source, changed = add_attributes(source, relpath)
        if not changed:
            continue
        missing.append(path)
        if not args.check:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(new_source)

    if args.check:
        if missing:
            for path in missing:
                print("%s: DOCUMENTATION has no attributes block"
                      % os.path.relpath(path, REPO_ROOT))
            print("attributes: %d module(s) do not document check_mode/idempotency"
                  % len(missing))
            return 1
        print("attributes: all %d module(s) document check_mode and idempotency"
              % len(module_paths()))
        return 0

    print("added an attributes block to %d module(s)" % len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
