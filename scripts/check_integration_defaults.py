#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Check the workflow's default integration dispatch list against the registry.

The weekly credentialed run dispatches exactly one list, and that list is a
string inside ``.github/workflows/integration.yml`` -- written twice, once as
the ``workflow_dispatch`` input default and once as the ``inputs.targets ||
'...'`` fallback. Nothing validated either copy against
``tests/integration/coverage.yml``, and nothing validated the two copies
against each other.

``docs/integration-env.md`` does state the rule -- free/low joins the default
list, medium/high stays opt-in -- but stating a rule is not enforcing it, and
the list quietly carried two medium targets that the rule excludes. That is
the same unvalidated hand-maintained index that already rotted in the module
registries, the doc figures and the curated info targets: the difference here
is that the cost of the drift is a weekly run on a real cloud account.

So the rule is now the code. Every registered target must end up in exactly
one of two places, and the reason has to be recorded rather than implied:
``free``/``low`` belong in the default list, ``high`` never does, and
``medium`` only when it is named here with a reason.
"""

from __future__ import absolute_import, division, print_function

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "integration.yml"
MAP = ROOT / "tests" / "integration" / "coverage.yml"

# The two copies of the list, in the order the workflow declares them.
#
# Both allow an empty list. With ``+`` an emptied list simply failed to match,
# so the guard reported "could not find both copies" -- an unparseable
# workflow -- for what was really a parsed, empty one, and the message sent
# whoever hit it to rewrite the regex instead of to restore the targets.
DEFAULT_RE = re.compile(r"""default:\s*["']([a-z0-9_ ]*)["']""")
FALLBACK_RE = re.compile(r"""inputs\.targets\s*\|\|\s*["']([a-z0-9_ ]*)["']""")

ALWAYS_DISPATCHED = frozenset({"free", "low"})

# medium targets allowed in the default list, each with the reason it is
# allowed. A medium target is not "half billed": it has to say why it is safe
# to run unattended every week, and the reason is printed by --check so a
# reviewer sees it rather than having to trust the name.
VETTED_MEDIUM = {
    "cfs_file_system": (
        "provisions one file system plus its VPC/subnet and tears all three "
        "down in an always: block, leaving no long-lived billable resource"
    ),
    "clb_http": (
        "provisions one load balancer plus its VPC/subnet and tears all three "
        "down in an always: block, leaving no long-lived billable resource"
    ),
}


def default_lists(text):
    """Return the (dispatch default, dispatch fallback) lists from the workflow.

    Both are returned separately rather than merged: they are two hand-typed
    copies of the same intent and are the most likely thing to drift, because
    editing one is a complete, silent, successful edit.
    """
    default = DEFAULT_RE.search(text)
    fallback = FALLBACK_RE.search(text)
    if default is None or fallback is None:
        return None
    return default.group(1).split(), fallback.group(1).split()


def audit(workflow_text, coverage):
    """Return the problems with the default dispatch list."""
    targets = coverage.get("targets", {})
    lists = default_lists(workflow_text)
    problems = []

    if lists is None:
        return ["could not find both copies of the default target list in %s"
                % WORKFLOW.name]
    declared, fallback = lists

    if declared != fallback:
        problems.append(
            "the two copies of the default list disagree: the workflow_dispatch "
            "default has %d targets and the inputs.targets fallback has %d - "
            "they differ in: %s"
            % (len(declared), len(fallback),
               ", ".join(sorted(set(declared) ^ set(fallback))) or "order only"))

    if not declared:
        return problems + ["the default target list is empty"]

    seen = set()
    for name in declared:
        if name in seen:
            problems.append("target %s is listed twice in the default list" % name)
        seen.add(name)
        if name not in targets:
            problems.append(
                "default target %s is not in %s - the run would fail on an "
                "unknown target instead of skipping it" % (name, MAP.name))
            continue
        cost = targets[name].get("cost")
        if cost == "high":
            problems.append(
                "default target %s has cost high - high-cost targets stay "
                "opt-in and are dispatched by hand" % name)
        elif cost == "medium" and name not in VETTED_MEDIUM:
            problems.append(
                "default target %s has cost medium and is not vetted - add it "
                "to VETTED_MEDIUM with the reason it is safe unattended, or "
                "drop it from the default list" % name)

    # The other direction: a registered target that never runs must be able to
    # say why, and the reason has to follow from its cost rather than from
    # somebody's memory of why it was left out.
    for name, config in sorted(targets.items()):
        cost = config.get("cost")
        if cost in ALWAYS_DISPATCHED and name not in seen:
            problems.append(
                "target %s has cost %s but is missing from the default list - "
                "cheap targets are exactly the ones the weekly run should cover"
                % (name, cost))

    for name in sorted(VETTED_MEDIUM):
        if name not in targets:
            problems.append(
                "VETTED_MEDIUM names %s, which is not in the registry" % name)
        elif targets[name].get("cost") != "medium":
            problems.append(
                "VETTED_MEDIUM names %s, whose registry cost is %s - only "
                "medium targets need vetting"
                % (name, targets[name].get("cost")))
        elif name not in seen:
            problems.append(
                "VETTED_MEDIUM names %s but it is not in the default list - "
                "the vetting is a claim about how it runs, so drop the entry"
                % name)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero when the default list is wrong")
    parser.add_argument("--root", default=str(ROOT), help="collection root")
    args = parser.parse_args(argv)

    root = Path(args.root)
    workflow_text = (root / WORKFLOW.relative_to(ROOT)).read_text(encoding="utf-8")
    coverage = yaml.safe_load((root / MAP.relative_to(ROOT)).read_text(encoding="utf-8"))

    problems = audit(workflow_text, coverage)
    lists = default_lists(workflow_text)
    if lists is not None:
        targets = coverage.get("targets", {})
        print("default dispatch list: %d targets" % len(lists[0]))
        for name in sorted(VETTED_MEDIUM):
            if name in lists[0]:
                print("  vetted medium: %s - %s" % (name, VETTED_MEDIUM[name]))
        missing = sorted(set(targets) - set(lists[0]))
        print("opt-in (not dispatched by default): %d" % len(missing))
    if problems:
        print("\nproblems (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
    else:
        print("\ndefault dispatch list agrees with %s" % MAP.name)

    if args.check and problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
