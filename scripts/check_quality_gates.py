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
UNIT_TESTS = os.path.join(REPO_ROOT, "tests", "unit", "plugins", "modules")
INTEGRATION_WF = os.path.join(REPO_ROOT, ".github", "workflows", "integration.yml")

# Ratchets: the census measured when this gate was introduced (2026-09-25).
# They may only go down.  The integration number is the honest one: the
# collection dispatches 21 targets covering 24 of the 166 write modules in
# the core subset, and 20 core products have no covered write module at all.
# That gap, not the documentation, is the largest remaining distance between
# this collection and the standard it claims.
DOC_RATCHET = 0
INTEGRATION_GATED_RATCHET = 8
INTEGRATION_MISSING_RATCHET = 134

# Write modules whose unit tests never run ``run_module`` twice, so nothing
# checks the idempotency the attributes claim.  Small, but the claim is
# user-facing and the three core-subset entries are worth naming.
IDEMPOTENCY_RATCHET = 0

# RETURN entries with no ``sample``.  A sample has to show the real shape of
# the payload -- the curated ones carry ID formats like ``ins-xxxxxxxx``,
# which is most of their value.  Generating them from the SDK model was tried
# and rejected: it produced 110 lines of ``"string"`` and ``0`` for
# cvm_instance, which is longer than the curated sample and says less.  So
# this is authoring work with a ratchet rather than a generator.
RETURN_SAMPLE_RATCHET = 976

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


def _registry_and_dispatch():
    """(coverage registry, dispatched target names, gated target names)."""
    with open(INTEGRATION_WF, encoding="utf-8") as handle:
        workflow = handle.read()
    match = re.search(r"inputs\.targets \|\| '([^']+)'", workflow)
    dispatched = set(match.group(1).split()) if match else set()
    with open(COVERAGE_YML, encoding="utf-8") as handle:
        registry = yaml.safe_load(handle).get("targets") or {}
    return registry, dispatched


def integration_findings():
    """Core-subset modules with no integration target in the default dispatch.

    Two different problems, and they need different answers:

    ``gated``
        The target exists and is written; it simply never runs because its
        cloud-account gate variables are unset.  This is a configuration and
        budget decision, not engineering, and it is where the flagship
        modules are -- cvm_instance, tke_cluster, cdb_instance among them.
    ``missing``
        No target at all.  This one is authoring work.

    Reporting them as one number would hide which of the two is being asked
    for.
    """
    registry, dispatched = _registry_and_dispatch()
    module_targets = {}
    for target, entry in registry.items():
        for module in (entry or {}).get("modules") or []:
            module_targets.setdefault(module, []).append(target)

    covered = set()
    for target, entry in registry.items():
        if target in dispatched:
            covered.update((entry or {}).get("modules") or [])

    gated, missing = [], []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if name.endswith("_info") or not in_core(name):
            continue
        if name in covered:
            continue
        (gated if module_targets.get(name) else missing).append(name)
    return sorted(gated), sorted(missing)


def integration_gates():
    """Map each gated target to the environment variables it waits on."""
    gates = {}
    for target in sorted({t for modules in _gated_targets().values() for t in modules}):
        directory = os.path.join(REPO_ROOT, "tests", "integration", "targets", target)
        found = set()
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if not name.endswith((".yml", ".yaml")):
                    continue
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    found.update(re.findall(r"TENCENTCLOUD_[A-Z0-9_]+", handle.read()))
        gates[target] = sorted(found)
    return gates


def _gated_targets():
    registry, dispatched = _registry_and_dispatch()
    module_targets = {}
    for target, entry in registry.items():
        for module in (entry or {}).get("modules") or []:
            module_targets.setdefault(module, []).append(target)
    return module_targets


def _unit_test_sources():
    """Map module name -> concatenated unit test source for that module."""
    sources = {}
    for path in glob.glob(os.path.join(UNIT_TESTS, "*.py")):
        name = os.path.basename(path)[len("test_"):-3]
        for suffix in ("_main", "_info"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        with open(path, encoding="utf-8") as handle:
            sources.setdefault(name, "")
            sources[name] += handle.read()
    return sources


def idempotency_findings():
    """Write modules whose tests never exercise the module twice."""
    sources = _unit_test_sources()
    found = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if name.endswith("_info"):
            continue
        source = sources.get(name, "")
        named = re.search(
            r"def test_\w*(?:idempot|second_run|twice|no_change|unchanged)", source)
        twice = re.search(
            r"run\(\s*\w*\.?run_module[^\n]*\)(?:.|\n){0,4000}?run\(\s*\w*\.?run_module",
            source)
        if not (named or twice):
            found.append(name)
    return sorted(found)


def return_sample_findings():
    """Modules whose RETURN entries carry no sample."""
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r"RETURN = r?(['\"]{3})(.*?)\1", text, re.S)
        if not match or "sample:" in match.group(2):
            continue
        found.append(os.path.basename(path)[:-3])
    return sorted(found)


def _gated_modules():
    """Map each gated module to the target(s) that would cover it."""
    registry, dispatched = _registry_and_dispatch()
    module_targets = {}
    for target, entry in registry.items():
        for module in (entry or {}).get("modules") or []:
            module_targets.setdefault(module, []).append(target)
    return {name: sorted(module_targets[name]) for name in integration_findings()[0]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the census without judging it")
    args = parser.parse_args()

    docs = doc_findings()
    gated, missing = integration_findings()
    idempotency = idempotency_findings()
    samples = return_sample_findings()

    if args.show:
        print("description restates the option name: %d option(s)" % len(docs))
        by_module = collections.Counter(module for module, _option in docs)
        for module, count in by_module.most_common():
            print("   %-44s %d" % (module, count))
        print()
        print("core-subset write modules whose target exists but never runs: %d"
              % len(gated))
        for name, targets in sorted(_gated_modules().items()):
            print("   %-30s -> %s" % (name, ", ".join(targets)))
        print()
        print("core-subset write modules with no integration target at all: %d"
              % len(missing))
        for name in missing[:40]:
            print("   %s" % name)
        if len(missing) > 40:
            print("   ... and %d more" % (len(missing) - 40))
        print()
        print("write modules whose tests never run the module twice: %d" % len(idempotency))
        for name in idempotency:
            print("   %s" % name)
        print()
        print("modules whose RETURN carries no sample: %d" % len(samples))
        return 0

    problems = []
    if len(docs) > DOC_RATCHET:
        problems.append(
            "description restates the option name: %d, ratchet is %d "
            "(the ratchet only goes down)" % (len(docs), DOC_RATCHET))
    if len(gated) > INTEGRATION_GATED_RATCHET:
        problems.append(
            "core-subset modules whose target exists but never runs: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(gated), INTEGRATION_GATED_RATCHET))
    if len(missing) > INTEGRATION_MISSING_RATCHET:
        problems.append(
            "core-subset modules with no integration target at all: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(missing), INTEGRATION_MISSING_RATCHET))
    if len(samples) > RETURN_SAMPLE_RATCHET:
        problems.append(
            "modules whose RETURN carries no sample: %d, ratchet is %d "
            "(the ratchet only goes down)" % (len(samples), RETURN_SAMPLE_RATCHET))
    if len(idempotency) > IDEMPOTENCY_RATCHET:
        problems.append(
            "write modules whose tests never run the module twice: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(idempotency), IDEMPOTENCY_RATCHET))

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem, file=sys.stderr)
        print("  (run with --print for the list)", file=sys.stderr)
        return 1

    print("ok: %d option description(s) merely restate the option name "
          "(ratchet %d)" % (len(docs), DOC_RATCHET))
    print("ok: %d core-subset module(s) have a target that never runs "
          "(ratchet %d)" % (len(gated), INTEGRATION_GATED_RATCHET))
    print("ok: %d core-subset module(s) have no integration target "
          "(ratchet %d)" % (len(missing), INTEGRATION_MISSING_RATCHET))
    print("ok: %d write module(s) lack a two-run test (ratchet %d)"
          % (len(idempotency), IDEMPOTENCY_RATCHET))
    print("ok: %d module(s) have a RETURN with no sample (ratchet %d)"
          % (len(samples), RETURN_SAMPLE_RATCHET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
