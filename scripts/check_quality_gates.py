#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quality gates for the core subset, and ratchets for everything else.

Two rules, both precise enough to be worth enforcing:

``doc``
    No option's description may merely repeat the option name.  ``target_group_id``
    described as "Target group ID." tells a reader nothing they could not read
    off the option itself.  This is deliberately *not* a length rule: the
    measurements that led here showed a length threshold flags thousands of
    perfectly good one-line descriptions ("Whether the listener should exist.")
    while missing the actual defect, and a gate that cries wolf gets disabled --
    which is how the sanity ignore files grew to 519 entries.

``integration``
    Every module in the core subset must be covered by an integration target
    that the workflow actually dispatches.  The collection already maps modules
    to targets in ``tests/integration/coverage.yml``; what went wrong is that
    the modules users need most -- cvm_instance, tke_cluster, cdb_instance --
    were exactly the ones left out of the default dispatch because their cost
    tier is ``high``.

Everything outside the core subset is held by a ratchet: the count may only go
down.  Raising a ceiling means deleting a finding, not editing this file.

Usage
-----
    python scripts/check_quality_gates.py            # verify (CI)
    python scripts/check_quality_gates.py --print    # show the census
"""

from __future__ import absolute_import, division, print_function

import argparse
import collections
import glob
import os
import re
import sys

import yaml

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "plugins", "modules")
CORE_SUBSET = os.path.join(REPO_ROOT, "tests", "quality", "core-subset.yml")
COVERAGE_YML = os.path.join(REPO_ROOT, "tests", "integration", "coverage.yml")
INTEGRATION_WF = os.path.join(REPO_ROOT, ".github", "workflows", "integration.yml")

# Ratchets: the census measured when this gate was introduced (2026-09-25).
# They may only go down.  The integration number is the honest one: the
# collection dispatches 21 targets covering 24 of the 166 write modules in
# the core subset, and 20 core products have no covered write module at all.
# That gap, not the documentation, is the largest remaining distance between
# this collection and the standard it claims.
DOC_RATCHET = 91
INTEGRATION_RATCHET = 142

_DOC_RE = re.compile(r"DOCUMENTATION = r?(['\"]{3})(.*?)\1", re.S)


def _normalise(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def core_products():
    with open(CORE_SUBSET, encoding="utf-8") as handle:
        return yaml.safe_load(handle)["products"]


def module_paths():
    return sorted(glob.glob(os.path.join(MODULES_DIR, "*.py")))


def module_product(name):
    """The core product a module belongs to, longest matching prefix first.

    A product is a prefix family, and some names span several words
    (``cvm_disaster_recover_group``), so the match runs against the core list
    -- not against the module catalogue, where every module would match
    itself.  Returns ``None`` when the module is outside the core subset.
    """
    matches = [p for p in core_products()
               if name == p or name.startswith(p + "_")]
    return max(matches, key=len) if matches else None


def in_core(name, products=None):
    return module_product(name) is not None


def doc_findings():
    """Options whose description merely restates the option name."""
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        match = _DOC_RE.search(text)
        if not match:
            continue
        try:
            doc = yaml.safe_load(match.group(2))
        except yaml.YAMLError:
            continue
        for name, option in (doc.get("options") or {}).items():
            if not isinstance(option, dict):
                continue
            description = option.get("description")
            if isinstance(description, list):
                description = " ".join(description)
            if not description:
                continue
            if _normalise(description) == _normalise(name.replace("_", " ")):
                found.append((os.path.basename(path)[:-3], name))
    return found


def integration_findings():
    """Core-subset modules with no integration target in the default dispatch."""
    with open(INTEGRATION_WF, encoding="utf-8") as handle:
        workflow = handle.read()
    match = re.search(r"inputs\.targets \|\| '([^']+)'", workflow)
    dispatched = set(match.group(1).split()) if match else set()

    with open(COVERAGE_YML, encoding="utf-8") as handle:
        registry = yaml.safe_load(handle).get("targets") or {}
    covered = set()
    for target, entry in registry.items():
        if target in dispatched:
            covered.update((entry or {}).get("modules") or [])

    products = core_products()
    found = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if not in_core(name, products):
            continue
        if name.endswith("_info"):
            continue
        if name not in covered:
            found.append(name)
    return sorted(found)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the census without judging it")
    args = parser.parse_args()

    docs = doc_findings()
    integrations = integration_findings()

    if args.show:
        print("description restates the option name: %d option(s)" % len(docs))
        by_module = collections.Counter(module for module, _option in docs)
        for module, count in by_module.most_common():
            print("   %-44s %d" % (module, count))
        print()
        print("core-subset write modules with no dispatched integration target: %d"
              % len(integrations))
        for name in integrations:
            print("   %s" % name)
        return 0

    problems = []
    if len(docs) > DOC_RATCHET:
        problems.append(
            "description restates the option name: %d, ratchet is %d "
            "(the ratchet only goes down)" % (len(docs), DOC_RATCHET))
    if len(integrations) > INTEGRATION_RATCHET:
        problems.append(
            "core-subset modules with no dispatched integration target: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(integrations), INTEGRATION_RATCHET))

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem, file=sys.stderr)
        print("  (run with --print for the list)", file=sys.stderr)
        return 1

    print("ok: %d option description(s) merely restate the option name "
          "(ratchet %d)" % (len(docs), DOC_RATCHET))
    print("ok: %d core-subset module(s) lack a dispatched integration target "
          "(ratchet %d)" % (len(integrations), INTEGRATION_RATCHET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
