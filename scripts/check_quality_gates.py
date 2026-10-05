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
import ast
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
RUNTIME_YML = os.path.join(REPO_ROOT, "meta", "runtime.yml")
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
# Corrected from 134: three modules were credited to a target that never
# called them. ``security_group_rule`` is exercised by the ``network`` target
# and was credited to ``security_group``, and ``network_acl`` and ``clb_rule``
# are exercised by nothing at all. The first was a mis-attribution, so moving
# it changes no count; ``clb_rule`` is a core-subset write module, so the gap
# is one larger than the registry claimed. This is a correction, not a
# regression, and the count now cannot go up again by itself:
# ``audit_integration_targets.py`` fails when a target claims a module its
# tasks never call.
INTEGRATION_MISSING_RATCHET = 135

# Write modules whose unit tests never run ``run_module`` twice, so nothing
# checks the idempotency the attributes claim.  Small, but the claim is
# user-facing and the three core-subset entries are worth naming.
IDEMPOTENCY_RATCHET = 0

# RETURN entries with no ``sample``.  A sample has to show the real shape of
# the payload -- the curated ones carry ID formats like ``ins-xxxxxxxx``,
# which is most of their value.  Generating them from the SDK model was tried
# and rejected: it produced 110 lines of ``"string"`` and ``0`` for
# cvm_instance, which is longer than the curated sample and says less.
#
# Two sources closed it. ``scripts/add_return_samples.py`` records the payload
# a module's own unit test produced and documents that -- 413 modules, the
# hand-written ones whose tests use the shared harness.  The generated modules
# are owned by ``generate_info_modules.py``, which now emits the *structure* of
# the SDK response model it already introspects: the field names are the API's
# own and the values are deliberately empty, because inventing values for an
# API nobody here can call is how a sample becomes misinformation.  That is
# another 501 modules, so this moved from 976 to 62.
#
# What is left is hand-written modules whose tests build a private harness (so
# no payload is captured) and two whose payload is a blob that cannot be
# wrapped under the line pep8 allows.
RETURN_SAMPLE_RATCHET = 2

# RETURN entries whose ``sample`` contradicts the declared ``type`` -- a dict
# documented as a list, an integer documented as a string. The sample is what
# the module actually produced under test, so a mismatch is always the
# documentation lying about the module. The first census found exactly one
# (``ssl_certificate.deploy_record_id``, an SDK integer documented as
# ``str``); none may come back.
RETURN_SAMPLE_TYPE_RATCHET = 0

# Write modules that claim ``check_mode: full`` with no dry-run test. The
# claim is user-facing and load-bearing: a user runs --check expecting no
# write. All 457 have one today.
CHECK_MODE_TEST_RATCHET = 0

# Unit-test files that are still unmodified generator skeletons, so their
# behavioural tests are xfail stubs. Eight files were, covering 22 xfails;
# each one is hand-finishing work, and this may only go down.
SKELETON_TEST_RATCHET = 0

# Write modules that accept ``state: absent`` and never show it. Deletion is
# the operation with the most consequence and the one a reader cannot guess:
# which option identifies the resource, and which create-only parameters the
# module still demands. All 270 now document it: 38 written by hand and the
# rest by ``scripts/add_delete_examples.py``, which takes the identity from the
# options the module's own lookup reads, the values from its create example,
# and a delete-path flag such as ``deletion_protection`` from the unit test's
# delete call rather than from the create example that turns it on.
DELETE_EXAMPLE_RATCHET = 0

# Module options that re-declare a doc-fragment option with a *different*
# type. Same-type re-declaration is how a module overrides a fragment default
# or description (108 sites today, harmless). A different type means the
# module silently shadows the fragment feature: ``dlc_spark_job`` declares
# ``role_arn: int`` (the DLC data-access role) over the credentials fragment's
# ``role_arn: str`` (the STS assume-role ARN), and because
# ``TencentCloudModule`` lets the module's own spec ``update()`` over
# ``base_argument_spec()``, the assume-role option cannot be used with that
# module at all. Un-shadowing it needs a deprecation cycle, so the one site
# is frozen as a baseline; no new shadow may appear.
FRAGMENT_SHADOW_RATCHET = 1

# Top-level helpers a module defines but nothing calls -- not the module
# itself, not its tests, not the contract suite. Four identical dead
# ``_first`` one-liners (cfs_file_system, ckafka_topic, gaap_proxy,
# ssm_parameter) were the first census; helpers referenced only by the
# contract suite (sqlserver_instance's modify-path builders, tke_cluster_
# endpoint's build_status) are alive by definition and are recorded in
# docs/inclusion-remediation.md instead.
DEAD_HELPER_RATCHET = 0

# Two of the families above are stock counts of *existing* debt -- samples to
# author (976) and integration targets that need a cloud account (135). A
# stock ceiling cannot tell "fixed three, broke three" apart from "fixed
# nothing", and it charges every new module for the sins of the old ones. So
# those two families are also frozen as an explicit baseline list: a module
# that is not on the list must not have the finding (new modules are held to
# the standard), and a module that no longer has the finding must be removed
# from the list (the baseline only shrinks, and `--write-baseline` reports
# exactly what moved). The stock ceiling above stays as the debt budget, so
# editing the baseline cannot raise the total.
BASELINES_DIR = os.path.join(REPO_ROOT, "scripts", "quality_baselines")
BASELINE_RETURN_SAMPLES = "return_samples"
BASELINE_INTEGRATION_MISSING = "integration_missing"
BASELINE_UNTESTED_MODULES = "untested_modules"
BASELINE_PRIVATE_HARNESS = "private_harness"
BASELINE_UNTESTED_MAIN_PATH = "untested_main_path"
BASELINE_FRAGMENT_SHADOWING = "fragment_shadowing"

# Three of the families above carry a baseline but had no stock ceiling: their
# debt had been paid down to zero, so the file was the only thing that could
# hold any of it. That left one place where a hard failure could still be
# frozen without limit -- ``--write-baseline`` records whatever the census
# finds, and nothing capped the total, so a single command could have turned
# any number of failures into "debt". Each has a ceiling of zero now, which
# makes them hard rules: a new finding has to be fixed rather than recorded,
# and re-opening one is a reviewed edit to this file, not a command.
UNTESTED_MODULES_CEILING = 0
PRIVATE_HARNESS_CEILING = 0
UNTESTED_MAIN_PATH_CEILING = 0

# Hand-written ``_info`` modules calling the module-level ``sdk_call``, which
# does not retry. The 502 generated ones moved when the generator did and the
# 15 hand-written ones were migrated afterwards, so this is a hard rule rather
# than a ratchet: no module may reach for the non-retrying call. Modules that
# read through ``TencentCloudModule.sdk_call`` are not counted -- that path
# retries already, and a census that cannot tell the two names apart reports
# debt that is not there.
LEGACY_READ_CALL_CEILING = 0

_BASELINE_GUIDANCE = {
    BASELINE_RETURN_SAMPLES:
        "a module added from now on documents its return values with a "
        "`sample:` (see cam_user_info for the shape), and a baselined module "
        "that gains one is removed from "
        "scripts/quality_baselines/return_samples.txt",
    BASELINE_INTEGRATION_MISSING:
        "a new core-subset write module needs an integration target under "
        "tests/integration/targets/, or it does not belong in the core "
        "subset",
    BASELINE_UNTESTED_MODULES:
        "a hand-written module needs a test that references it -- run_module "
        "end to end, not only a helper -- before it ships",
    BASELINE_UNTESTED_MAIN_PATH:
        "a module test drives run_module, not only the module's helpers, so "
        "the body that talks to the API is executed at least once",
    BASELINE_PRIVATE_HARNESS:
        "a module test drives its module through "
        "tests/unit/plugins/modules/harness.py, not a private double, so the "
        "payload is observable and the conventions live in one place",
    BASELINE_FRAGMENT_SHADOWING:
        "a module that re-declares a fragment option keeps the fragment's "
        "type, so the shared feature (assume-role, waiter, endpoint) stays "
        "usable; dlc_spark_job is the one grandfathered shadow",
}

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


_SAMPLE_TYPE_MAP = {
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


def _sample_type_mismatches(entries, trail, name, found):
    for key, spec in (entries or {}).items():
        if not isinstance(spec, dict):
            continue
        here = "%s.%s" % (trail, key) if trail else key
        declared = spec.get("type")
        if "sample" in spec and declared in _SAMPLE_TYPE_MAP:
            sample = spec["sample"]
            expected = _SAMPLE_TYPE_MAP[declared]
            matches = isinstance(sample, expected)
            if matches and declared in ("int", "float") and isinstance(sample, bool):
                matches = False  # bool is an int subclass, but never a valid id
            if not matches:
                found.append("%s :: %s (declared %s, sample is %s)"
                             % (name, here, declared,
                                type(sample).__name__))
        _sample_type_mismatches(spec.get("contains"), here, name, found)


def return_sample_type_findings():
    """RETURN entries whose sample contradicts the declared type."""
    found = []
    for path in module_paths():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r"RETURN = r?(['\"]{3})(.*?)\1", text, re.S)
        if not match or "sample:" not in match.group(2):
            continue
        try:
            doc = yaml.safe_load(match.group(2))
        except yaml.YAMLError:
            continue  # validate-modules owns YAML validity
        if not isinstance(doc, dict):
            continue
        _sample_type_mismatches(doc, "", os.path.basename(path)[:-3], found)
    return sorted(found)


_DOC_FRAGMENTS_DIR = os.path.join(REPO_ROOT, "plugins", "doc_fragments")


def _documentation_of(path):
    """The parsed DOCUMENTATION mapping of one module or fragment file."""
    with open(path, encoding="utf-8") as handle:
        match = _DOC_RE.search(handle.read())
    if not match:
        return None
    try:
        doc = yaml.safe_load(match.group(2))
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def fragment_shadow_findings():
    """Module options re-declaring a fragment option with a different type.

    Same-type re-declaration only overrides a default or a description; a
    different type means the module's own option silently shadows the shared
    feature the fragment provides (the runtime lets the module's argument
    spec ``update()`` over ``base_argument_spec()``).
    """
    fragment_types = {}
    for path in sorted(glob.glob(os.path.join(_DOC_FRAGMENTS_DIR, "*.py"))):
        stem = os.path.basename(path)[:-3]
        doc = _documentation_of(path)
        if isinstance(doc, dict):
            fragment_types[stem] = {
                key: spec.get("type")
                for key, spec in (doc.get("options") or {}).items()
                if isinstance(spec, dict)
            }
    found = []
    for path in module_paths():
        doc = _documentation_of(path)
        if not isinstance(doc, dict):
            continue
        own = doc.get("options") or {}
        fragments = doc.get("extends_documentation_fragment") or []
        if isinstance(fragments, str):
            fragments = [fragments]
        for fragment in fragments:
            stem = fragment.rsplit(".", 1)[-1]
            for option, frag_type in fragment_types.get(stem, {}).items():
                spec = own.get(option)
                if not isinstance(spec, dict):
                    continue
                own_type = spec.get("type")
                if own_type != frag_type:
                    found.append("%s :: %s (%s declares %s, module declares %s)"
                                 % (os.path.basename(path)[:-3], option,
                                    stem, frag_type, own_type))
    return sorted(found)


def _word_re(name):
    return re.compile(r"\b%s\b" % re.escape(name))


def dead_helper_findings():
    """Top-level module helpers that nothing in the repository calls.

    A helper whose name appears only at its own ``def`` is dead code. The
    reference search is deliberately scoped: a file can only reach another
    module's helper when it names that module (an import, the contract
    suite's plugin lists, a test's ``import_plugin``), so references count
    only in files that mention the module's own stem -- otherwise a same-
    named local helper in an unrelated module would rescue every dead one
    (``_first`` exists as a local in a dozen modules). Helpers referenced
    only by tests or the contract suite stay alive by definition.
    """
    word_sets = {}
    self_path = os.path.abspath(__file__)
    for base in ("tests", "scripts", "plugins"):
        pattern = os.path.join(REPO_ROOT, base, "**", "*.py")
        for path in sorted(glob.glob(pattern, recursive=True)):
            if os.path.abspath(path) == self_path:
                continue  # this census must not rescue its own examples
            with open(path, encoding="utf-8") as handle:
                word_sets[path] = set(re.findall(r"\w+", handle.read()))
    found = []
    for path in module_paths():
        stem = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        referencing = [words for other, words in word_sets.items()
                       if other != path and stem in words]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if name in ("main", "run_module"):
                continue
            own = source.replace("def %s" % name, "", 1)
            if _word_re(name).search(own):
                continue
            if any(name in words for words in referencing):
                continue
            found.append("%s :: %s" % (stem, name))
    return sorted(found)


def baseline_path(family):
    """Return the baseline file for *family*."""
    return os.path.join(BASELINES_DIR, "%s.txt" % family)


def read_baseline(family):
    """Return the frozen findings for *family* (comments and blanks ignored)."""
    try:
        with open(baseline_path(family), encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return None
    return sorted(line.strip() for line in lines
                  if line.strip() and not line.startswith("#"))


def _wrap_comment(text, width=76):
    """Wrap *text* into comment lines of at most *width* characters."""
    lines = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = "%s %s" % (current, word) if current else word
    if current:
        lines.append(current)
    return lines


def write_baseline(family, findings, out=sys.stdout):
    """Freeze *findings* as the baseline for *family*; report what moved."""
    previous = read_baseline(family) or []
    added = sorted(set(findings) - set(previous))
    removed = sorted(set(previous) - set(findings))
    os.makedirs(BASELINES_DIR, exist_ok=True)
    with open(baseline_path(family), "w", encoding="utf-8") as handle:
        handle.write("# Frozen findings for the %r family of "
                     "scripts/check_quality_gates.py.\n" % family)
        handle.write("# One module name per line.\n")
        handle.write("# This list may only shrink: a baselined module that no "
                     "longer has the\n# finding must be delisted (the gate "
                     "names it), and a module that is not on\n# the list must "
                     "not have the finding at all.\n")
        for line in _wrap_comment(_BASELINE_GUIDANCE[family]):
            handle.write("# %s\n" % line)
        for name in findings:
            handle.write("%s\n" % name)
    print("%s: %d entry/entries (+%d, -%d)"
          % (baseline_path(family), len(findings), len(added), len(removed)),
          file=out)
    for name in added:
        print("   added:   %s" % name, file=out)
    for name in removed:
        print("   removed: %s" % name, file=out)
    return 0


def baseline_problems(family, findings):
    """Return the problems that keep *findings* frozen as *family*'s baseline."""
    problems = []
    frozen = read_baseline(family)
    if frozen is None:
        if not findings:
            # A family with no debt needs no file: the rule is satisfied, and
            # the missing file is the visible sign that the debt was paid off.
            return []
        return ["%s is missing: freeze the current %d finding(s) with "
                "`python scripts/check_quality_gates.py --write-baseline %s`"
                % (baseline_path(family), len(findings), family)]
    new = sorted(set(findings) - set(frozen))
    stale = sorted(set(frozen) - set(findings))
    if new:
        problems.append(
            "%d finding(s) are not in the %s baseline: %s -- %s"
            % (len(new), family, ", ".join(new[:6])
               + (" ..." if len(new) > 6 else ""), _BASELINE_GUIDANCE[family]))
    if stale:
        problems.append(
            "%d %s baseline entry/entries no longer have the finding: %s -- "
            "delete them (the baseline only shrinks); "
            "`--write-baseline %s` does it for you"
            % (len(stale), family, ", ".join(stale[:6])
               + (" ..." if len(stale) > 6 else ""), family))
    return problems


def delete_example_findings():
    """Write modules that accept ``state: absent`` but never show it.

    Deletion is the operation with the most consequence and the one a reader
    is least able to guess: which option identifies the resource, and which
    create-only parameters the module still demands. 38 modules documented
    only how to create their resource. Every one of them now has a delete
    example, and this is the gate that keeps it that way -- the identity
    options in each example are the ones the module's own delete path
    resolves the resource from, and ``scripts/check_module_examples.py``
    re-validates them against the argument spec on every run.
    """
    found = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if name.endswith("_info"):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        doc = re.search(r"DOCUMENTATION = r?(['\"]{3})(.*?)\1", text, re.S)
        if not doc:
            continue
        try:
            parsed = yaml.safe_load(doc.group(2))
        except yaml.YAMLError:
            continue
        state = ((parsed or {}).get("options") or {}).get("state")
        if not isinstance(state, dict) or "absent" not in (state.get("choices") or []):
            continue
        examples = re.search(r"EXAMPLES = r?(['\"]{3})(.*?)\1", text, re.S)
        if examples and re.search(r"state:\s*[\"']?absent", examples.group(2)):
            continue
        found.append(name)
    return sorted(found)


def check_mode_test_findings():
    """Write modules that claim ``check_mode: full`` with no dry-run test.

    The claim is that no write reaches the API in check mode, and only a test
    that runs the module in check mode can settle it. The check is on the test
    *name* -- ``check_mode`` or ``dry_run`` -- because that is deterministic:
    detecting the assertion itself by reading test prose was tried, and it
    reported 376 modules of which every one inspected was a false positive,
    since the idiom varies (``assert_not_called()``,
    ``assert not any(name == "CreateGroup" for name, request in fake.calls)``,
    ``assert "DeleteHost" not in [c for c, unused in fake.calls]``). Names are
    structured; prose is not, and a gate that cries wolf gets disabled.
    """
    sources = _unit_test_sources()
    found = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if name.endswith("_info"):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        match = _DOC_RE.search(text)
        if not match:
            continue
        try:
            doc = yaml.safe_load(match.group(2))
        except yaml.YAMLError:
            continue
        support = (((doc or {}).get("attributes") or {}).get("check_mode") or {}).get("support")
        if support != "full":
            continue
        if not re.search(r"def test_\w*(?:check_mode|dry_run)", sources.get(name, "")):
            found.append(name)
    return sorted(found)


def skeleton_test_findings():
    """Test files that are still unmodified generator skeletons.

    ``scripts/generate_module_test_skeleton.py`` writes a starting point and
    marks it with a first-line comment; the documented contract is that
    finishing the file means deleting that line. A file that still carries it
    has never been finished, so its behavioural tests are ``xfail`` stubs and
    the module they describe has no real test of its behaviour -- eight files
    did, which was 22 of the suite's xfails.

    The marker is read from the first line only, which is where the generator
    puts it, so a test that happens to quote the marker string is not
    mistaken for a skeleton.
    """
    marker = "# Skeleton generated by scripts/generate_module_test_skeleton.py"
    found = []
    for path in sorted(glob.glob(os.path.join(UNIT_TESTS, "test_*.py"))):
        with open(path, encoding="utf-8") as handle:
            first = handle.readline()
        if first.startswith(marker):
            found.append(os.path.basename(path)[:-3])
    return sorted(found)


def role_meta_findings():
    """Roles whose galaxy_info disagrees with the collection's own metadata.

    ``meta/runtime.yml`` is the collection's ansible-core floor and the README
    restates it; a role's ``min_ansible_version`` is a third copy, and all
    sixty-four roles said 2.16 while the collection required 2.19.  A role
    page that advertises a floor the rest of the collection does not support
    is how a user ends up installing something that will not run, so this is a
    hard check rather than a ratchet.
    """
    with open(RUNTIME_YML, encoding="utf-8") as handle:
        runtime = yaml.safe_load(handle)
    floor = re.search(r"(\d+\.\d+)", runtime["requires_ansible"]).group(1)

    problems = []
    roles = sorted(glob.glob(os.path.join(REPO_ROOT, "roles", "*")))
    for role in roles:
        meta = os.path.join(role, "meta", "main.yml")
        name = os.path.basename(role)
        if not os.path.exists(meta):
            problems.append("roles/%s: no meta/main.yml" % name)
            continue
        with open(meta, encoding="utf-8") as handle:
            info = (yaml.safe_load(handle) or {}).get("galaxy_info") or {}
        declared = str(info.get("min_ansible_version"))
        if declared != floor:
            problems.append("roles/%s: min_ansible_version %s, collection requires %s"
                            % (name, declared, floor))
        if info.get("license") != "GPL-3.0-or-later":
            problems.append("roles/%s: license is %r, expected GPL-3.0-or-later"
                            % (name, info.get("license")))
    return problems


#: A role README names its own variables as ``tc_<role>_<name>``; that
#: namespace is the role's public interface.
ROLE_VAR_RE = re.compile(r"\b(tc_[a-z0-9_]+)\b")


def _role_published_names(role_dir):
    """Return every name the role assigns through set_fact or register."""
    names = set()
    tasks_dir = os.path.join(role_dir, "tasks")
    files = []
    for root, _dirs, filenames in os.walk(tasks_dir):
        files.extend(os.path.join(root, name) for name in filenames
                     if name.endswith(".yml"))
    for path in sorted(files):
        try:
            with open(path, encoding="utf-8") as handle:
                parsed = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            continue
        stack = [parsed]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                for key, value in node.items():
                    if key in ("ansible.builtin.set_fact", "set_fact") \
                            and isinstance(value, dict):
                        names.update(str(name) for name in value)
                    elif key == "register" and isinstance(value, str):
                        names.add(value)
                    stack.append(value)
    return names


def role_doc_findings():
    """Role READMEs that name a variable the role does not offer.

    A role's interface is its ``defaults/main.yml`` (the inputs) plus what it
    publishes with ``set_fact``/``register`` (the outputs, documented as
    ``tc_<role>_result``). A README that names anything else in the role's own
    namespace documents a variable a user cannot set and will not receive --
    the failure mode the example checker already caught once, when five roles
    read a ``region`` variable they never declared and hidden it behind
    ``default(omit)``.
    """
    problems = []
    for role_dir in sorted(glob.glob(os.path.join(REPO_ROOT, "roles", "*"))):
        role = os.path.basename(role_dir)
        readme = os.path.join(role_dir, "README.md")
        if not os.path.isfile(readme):
            problems.append("roles/%s: no README.md" % role)
            continue
        with open(readme, encoding="utf-8") as handle:
            text = handle.read()
        declared = set()
        defaults = os.path.join(role_dir, "defaults", "main.yml")
        if os.path.isfile(defaults):
            with open(defaults, encoding="utf-8") as handle:
                parsed = yaml.safe_load(handle) or {}
            if isinstance(parsed, dict):
                declared = {str(key) for key in parsed}
        offered = declared | _role_published_names(role_dir)
        mentioned = {name for name in ROLE_VAR_RE.findall(text)
                     if name.startswith(role + "_")}
        for name in sorted(mentioned - offered):
            problems.append(
                "roles/%s: README names %s, which defaults/main.yml does not "
                "declare and nothing in the role publishes" % (role, name))
    return problems


GENERATED_MARKER = "# Generated by scripts/generate_info_modules.py"

#: The shared harness every module test should drive its module through.
HARNESS_IMPORT = "tests.unit.plugins.modules.harness"


def untested_main_path_findings():
    """Hand-written modules whose tests never execute ``run_module``.

    A module can be named by a test file and still never be executed: a test
    that only imports the module and calls its helpers leaves the body that
    talks to the API -- argument handling, request building, pagination,
    exit_json -- unrun. Those modules are invisible to every other census
    here: they are referenced (so ``untested_module_findings`` is satisfied)
    and they need no private harness (so that census is satisfied too).

    A module with tests must have at least one of them drive ``run_module``;
    the frozen list may only shrink as the missing tests are written.
    """
    problems = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            if GENERATED_MARKER in handle.read():
                continue
        files = sorted(glob.glob(os.path.join(
            REPO_ROOT, "tests", "unit", "plugins", "modules",
            "test_%s*.py" % name)))
        if not files:
            continue
        blob = "\n".join(open(item, encoding="utf-8").read() for item in files)
        if "run_module" in blob:
            continue
        problems.append(
            "plugins/modules/%s.py: no test under tests/unit/ calls "
            "run_module, so the module body is never executed" % name)
    return problems


def private_harness_findings():
    """Modules whose tests drive ``run_module`` without the shared harness.

    ``tests/unit/plugins/modules/harness.py`` is the collection's single
    module-test harness: argument injection, the ``AnsibleModule`` patch, the
    fake SDK objects and the ansible-core 2.21 serialisation profile all live
    there. 57 hand-written modules instead build a private double in their own
    test file -- a ``FakeModule`` with its own ``exit_json`` -- and replace the
    module's ``AnsibleModule`` with it. Those tests do exercise the main path,
    but the payload never passes through a real ``AnsibleModule``, so nothing
    outside the test file can observe it: they cannot gain a captured RETURN
    sample, they duplicate the scaffolding, and a fix to the shared harness
    does not reach them.

    A new module test must use the shared harness; the frozen list may only
    shrink as the private ones are migrated.
    """
    problems = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            if GENERATED_MARKER in handle.read():
                continue
        files = sorted(glob.glob(os.path.join(
            REPO_ROOT, "tests", "unit", "plugins", "modules",
            "test_%s*.py" % name)))
        if not files:
            continue
        blob = "\n".join(open(item, encoding="utf-8").read() for item in files)
        if "run_module" not in blob or HARNESS_IMPORT in blob:
            continue
        problems.append(
            "plugins/modules/%s.py: its tests drive run_module through a "
            "private double instead of %s" % (name, HARNESS_IMPORT))
    return problems


MODULES_PACKAGE = "ansible_collections.susunola.tencentcloud.plugins.modules"


def _modules_named_by_tests():
    """Module names the unit tests name in an import, not in passing.

    The census used to ask ``name in blob`` over the concatenated text of every
    test file. That is satisfied by accident: any test that mentions ``vpc`` --
    as a fixture key, a sample value, part of ``vpc_id`` -- kept ``vpc_info``'s
    entry alive, so for a short module name the rule could not fail. Reading
    the import statements is what "referenced by a test" actually means.

    Three spellings are recognised, because tests use all three:
    ``from ...plugins.modules import <name>``,
    ``import ...plugins.modules.<name>``, and
    ``importlib.import_module("...plugins.modules.<name>")``.
    """
    referenced = set()
    paths = sorted(glob.glob(os.path.join(REPO_ROOT, "tests", "unit", "**", "*.py"),
                             recursive=True))
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            # A file pytest cannot import either; leaving it out can only make
            # this census stricter, never laxer.
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == MODULES_PACKAGE:
                    referenced.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(MODULES_PACKAGE + "."):
                        referenced.add(alias.name[len(MODULES_PACKAGE) + 1:])
            elif isinstance(node, ast.Call):
                func = node.func
                if not (isinstance(func, ast.Attribute) and func.attr == "import_module"):
                    continue
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.startswith(MODULES_PACKAGE + "."):
                            referenced.add(arg.value[len(MODULES_PACKAGE) + 1:])
    return referenced


def untested_module_findings():
    """Hand-written modules that no test file imports.

    The collection ships a unit test per module and says so; two modules were
    referenced by no test file and no integration target at all --
    ``cos_bucket_domain_certificate_info`` and
    ``cos_bucket_intelligent_tiering_info`` -- so nothing anywhere executed
    them. A module nothing runs is a module nobody can tell works, so this is
    a hard rule rather than a ratchet. Generated modules are exempt: their
    tests are generated beside them and ``generate_info_modules.py --check``
    keeps the pair in step.
    """
    referenced = _modules_named_by_tests()

    problems = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if GENERATED_MARKER in text:
            continue
        if name in referenced:
            continue
        problems.append(
            "plugins/modules/%s.py: no file under tests/unit/ imports it, so "
            "nothing executes or checks this module" % name)
    return problems


def _calls_bare_sdk_call(text):
    """True when the module calls the module-level ``sdk_call`` function.

    The two call wrappers share a suffix and the difference is the whole point
    of this census:

    - ``sdk_call(module, operation, request)`` is the module-level function in
      ``module_utils/tencentcloud.py``, which does **not** retry.
    - ``module.sdk_call(operation, request)`` is ``TencentCloudModule``'s
      method, which retries through ``retry_on`` and records the call audit
      trail.

    A text search for ``sdk_call`` cannot tell them apart. The first version of
    this census used one, and listed 38 modules that already retry among the 53
    it called non-retrying. The AST separates them: a bare call parses as
    ``ast.Call(func=ast.Name(id="sdk_call"))``, a method call as
    ``ast.Call(func=ast.Attribute(attr="sdk_call"))``.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "sdk_call":
            return True
    return False


def legacy_read_call_findings():
    """Hand-written ``_info`` modules still calling the non-retrying wrapper.

    The module-level ``sdk_call`` does not retry, which is right for a write
    module and wrong for a read. Tencent Cloud throttles as a matter of course,
    so a module on this list fails the first time it meets
    ``RequestLimitExceeded`` while every module that reads through
    ``read_sdk_call`` recovers from it. The generated ``_info`` modules moved
    when the generator did; these are hand-written, each with its own request
    builders and pagination, so each needs a look rather than a regeneration.

    Modules that read through ``TencentCloudModule.sdk_call`` are deliberately
    not listed: that path retries already, and it additionally records the call
    in the ``tencentcloud_resource_actions`` audit trail, which
    ``read_sdk_call`` does not. Moving them would be a regression dressed up as
    a migration.
    """
    problems = []
    for path in module_paths():
        name = os.path.basename(path)[:-3]
        if not name.endswith("_info"):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if GENERATED_MARKER in text:
            continue
        if not _calls_bare_sdk_call(text):
            continue
        problems.append(name)
    return problems


def _gated_modules():
    """Map each gated module to the target(s) that would cover it."""
    registry, dispatched = _registry_and_dispatch()
    module_targets = {}
    for target, entry in registry.items():
        for module in (entry or {}).get("modules") or []:
            module_targets.setdefault(module, []).append(target)
    return {name: sorted(module_targets[name]) for name in integration_findings()[0]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the census without judging it")
    parser.add_argument("--write-baseline", metavar="FAMILY",
                        choices=sorted(_BASELINE_GUIDANCE),
                        help="freeze the current findings of FAMILY as its "
                             "baseline (a deliberate, reviewable act)")
    args = parser.parse_args(argv)

    docs = doc_findings()
    gated, missing = integration_findings()
    idempotency = idempotency_findings()
    samples = return_sample_findings()
    sample_types = return_sample_type_findings()
    shadows = fragment_shadow_findings()
    dead_helpers = dead_helper_findings()
    deletes = delete_example_findings()
    skeletons = skeleton_test_findings()
    check_mode_tests = check_mode_test_findings()
    role_meta = role_meta_findings()
    role_docs = role_doc_findings()
    untested = untested_module_findings()
    private_harness = private_harness_findings()
    untested_main_path = untested_main_path_findings()
    legacy_read_call = legacy_read_call_findings()

    if args.write_baseline:
        findings = {"return_samples": samples,
                    "integration_missing": missing,
                    "untested_modules": untested,
                    "private_harness": private_harness,
                    "untested_main_path": untested_main_path,
                    "fragment_shadowing": shadows}[args.write_baseline]
        return write_baseline(args.write_baseline, findings)

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
        frozen = read_baseline(BASELINE_INTEGRATION_MISSING)
        print("   baseline %s: %s"
              % (BASELINE_INTEGRATION_MISSING,
                 "missing" if frozen is None else len(frozen)))
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
        frozen = read_baseline(BASELINE_RETURN_SAMPLES)
        print("   baseline %s: %s"
              % (BASELINE_RETURN_SAMPLES,
                 "missing" if frozen is None else len(frozen)))
        print()
        print("RETURN samples contradicting the declared type: %d"
              % len(sample_types))
        for name in sample_types:
            print("   %s" % name)
        print()
        print("module options shadowing a fragment option with another type: %d"
              % len(shadows))
        frozen = read_baseline(BASELINE_FRAGMENT_SHADOWING)
        print("   baseline %s: %s"
              % (BASELINE_FRAGMENT_SHADOWING,
                 "missing" if frozen is None else len(frozen)))
        for name in shadows:
            print("   %s" % name)
        print()
        print("top-level module helpers nothing calls: %d" % len(dead_helpers))
        for name in dead_helpers:
            print("   %s" % name)
        print()
        print("write modules that accept state=absent with no delete example: %d"
              % len(deletes))
        for name in deletes:
            print("   %s" % name)
        print()
        print("unit-test files that are still generator skeletons: %d" % len(skeletons))
        for name in skeletons:
            print("   %s" % name)
        print()
        print("write modules claiming check_mode: full with no dry-run test: %d"
              % len(check_mode_tests))
        for name in check_mode_tests:
            print("   %s" % name)
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
    problems.extend(role_meta)
    problems.extend(role_docs)
    if len(untested) > UNTESTED_MODULES_CEILING:
        problems.append(
            "hand-written modules no unit test references: %d, ceiling is %d "
            "(a module nothing executes is a module nobody can tell works; "
            "write the test rather than freezing the finding)"
            % (len(untested), UNTESTED_MODULES_CEILING))
    if len(private_harness) > PRIVATE_HARNESS_CEILING:
        problems.append(
            "module tests building a private double: %d, ceiling is %d (use "
            "tests/unit/plugins/modules/harness.py so the payload stays "
            "observable outside the test file)"
            % (len(private_harness), PRIVATE_HARNESS_CEILING))
    if len(untested_main_path) > UNTESTED_MAIN_PATH_CEILING:
        problems.append(
            "module tests that never execute run_module: %d, ceiling is %d "
            "(a test that only imports the module proves it parses and "
            "nothing else)" % (len(untested_main_path), UNTESTED_MAIN_PATH_CEILING))
    if len(legacy_read_call) > LEGACY_READ_CALL_CEILING:
        problems.append(
            "hand-written _info modules reading through the non-retrying "
            "sdk_call: %d, ceiling is %d (read through read_sdk_call, or "
            "paginate_read when the module pages)"
            % (len(legacy_read_call), LEGACY_READ_CALL_CEILING))
    problems.extend(baseline_problems(BASELINE_UNTESTED_MODULES, untested))
    problems.extend(baseline_problems(BASELINE_PRIVATE_HARNESS, private_harness))
    problems.extend(baseline_problems(BASELINE_UNTESTED_MAIN_PATH, untested_main_path))
    problems.extend(baseline_problems(BASELINE_RETURN_SAMPLES, samples))
    problems.extend(baseline_problems(BASELINE_INTEGRATION_MISSING, missing))
    if len(samples) > RETURN_SAMPLE_RATCHET:
        problems.append(
            "modules whose RETURN carries no sample: %d, ratchet is %d "
            "(the ratchet only goes down)" % (len(samples), RETURN_SAMPLE_RATCHET))
    if sample_types:
        problems.append(
            "RETURN samples contradicting the declared type: %d, ratchet is %d "
            "(the ratchet only goes down)"
            % (len(sample_types), RETURN_SAMPLE_TYPE_RATCHET))
    problems.extend(baseline_problems(BASELINE_FRAGMENT_SHADOWING, shadows))
    if len(shadows) > FRAGMENT_SHADOW_RATCHET:
        problems.append(
            "module options shadowing a fragment option with another type: "
            "%d, ratchet is %d (the ratchet only goes down)"
            % (len(shadows), FRAGMENT_SHADOW_RATCHET))
    if dead_helpers:
        problems.append(
            "top-level module helpers nothing calls: %d, ratchet is %d "
            "(the ratchet only goes down)"
            % (len(dead_helpers), DEAD_HELPER_RATCHET))
    if len(check_mode_tests) > CHECK_MODE_TEST_RATCHET:
        problems.append(
            "write modules claiming check_mode: full with no dry-run test: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(check_mode_tests), CHECK_MODE_TEST_RATCHET))
    if len(skeletons) > SKELETON_TEST_RATCHET:
        problems.append(
            "unit-test files that are still generator skeletons: %d, ratchet is %d "
            "(the ratchet only goes down)" % (len(skeletons), SKELETON_TEST_RATCHET))
    if len(deletes) > DELETE_EXAMPLE_RATCHET:
        problems.append(
            "write modules that accept state=absent with no delete example: %d, "
            "ratchet is %d (the ratchet only goes down)"
            % (len(deletes), DELETE_EXAMPLE_RATCHET))
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
          "(ratchet %d, baseline %d)"
          % (len(missing), INTEGRATION_MISSING_RATCHET,
             len(read_baseline(BASELINE_INTEGRATION_MISSING) or [])))
    print("ok: %d write module(s) lack a two-run test (ratchet %d)"
          % (len(idempotency), IDEMPOTENCY_RATCHET))
    print("ok: %d module(s) have a RETURN with no sample (ratchet %d, "
          "baseline %d)"
          % (len(samples), RETURN_SAMPLE_RATCHET,
             len(read_baseline(BASELINE_RETURN_SAMPLES) or [])))
    print("ok: %d RETURN sample(s) contradict the declared type (ratchet %d)"
          % (len(sample_types), RETURN_SAMPLE_TYPE_RATCHET))
    print("ok: %d module option(s) shadow a fragment option with another type "
          "(ratchet %d, baseline %d)"
          % (len(shadows), FRAGMENT_SHADOW_RATCHET,
             len(read_baseline(BASELINE_FRAGMENT_SHADOWING) or [])))
    print("ok: %d top-level module helper(s) are dead code (ratchet %d)"
          % (len(dead_helpers), DEAD_HELPER_RATCHET))
    print("ok: %d write module(s) accept state=absent with no delete example "
          "(ratchet %d)" % (len(deletes), DELETE_EXAMPLE_RATCHET))
    print("ok: %d unit-test file(s) are still generator skeletons (ratchet %d)"
          % (len(skeletons), SKELETON_TEST_RATCHET))
    print("ok: %d write module(s) claim check_mode: full with no dry-run test "
          "(ratchet %d)" % (len(check_mode_tests), CHECK_MODE_TEST_RATCHET))
    print("ok: all %d role(s) declare the collection's ansible-core floor"
          % len(glob.glob(os.path.join(REPO_ROOT, "roles", "*"))))
    print("ok: all %d role README(s) name only variables the role offers"
          % len(glob.glob(os.path.join(REPO_ROOT, "roles", "*"))))
    print("ok: %d hand-written module(s) have no test that runs them "
          "(ceiling %d, baseline %d)"
          % (len(untested_main_path), UNTESTED_MAIN_PATH_CEILING,
             len(read_baseline(BASELINE_UNTESTED_MAIN_PATH) or [])))
    print("ok: %d module test(s) build a private double (ceiling %d, "
          "baseline %d)"
          % (len(private_harness), PRIVATE_HARNESS_CEILING,
             len(read_baseline(BASELINE_PRIVATE_HARNESS) or [])))
    print("ok: %d hand-written module(s) are referenced by no unit test "
          "(ceiling %d, baseline %d)"
          % (len(untested), UNTESTED_MODULES_CEILING,
             len(read_baseline(BASELINE_UNTESTED_MODULES) or [])))
    print("ok: %d hand-written _info module(s) read through the non-retrying "
          "sdk_call (ceiling %d)"
          % (len(legacy_read_call), LEGACY_READ_CALL_CEILING))
    return 0


if __name__ == "__main__":
    sys.exit(main())
