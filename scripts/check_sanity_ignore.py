#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sanity-ignore guard: forbidden codes, justifications, and a ratchet.

What this replaces
------------------
The previous version of this guard enforced ``BASELINE_TOTAL = 2600`` -- a
*budget* for 2,076 committed ignore entries, with headroom above them, plus a
comment in ``.github/workflows/devel.yml`` describing how to copy
``ignore-2.21.txt`` to ``ignore-2.22.txt`` when a new ansible-core minor
arrives.  That is the opposite of what the community requires:

    You MUST NOT ignore the following validations.  They MUST be fixed and
    removed from the files before approval.
    All entries in ignore-*.txt files MUST have a justification in a comment
    in the files for each entry.

    -- Ansible community package collections requirements, "CI Testing"

An ignore file that is allowed to grow is a place where violations go to be
forgotten: this is how the collection reached 519 entries per file, how a
merge that dropped 509 modules' doc fragments went unnoticed, and how 20
modules ended up failing with no ignore entry at all -- invisible behind an
earlier failing CI step.

This guard therefore asserts three things:

1. no entry names a code that must not be ignored (hard failure);
2. every entry carries a ``#`` justification;
3. the per-code count never exceeds the ceiling recorded here, and the
   ceiling is only ever lowered.

Usage
-----
    python scripts/check_sanity_ignore.py            # verify (CI)
    python scripts/check_sanity_ignore.py --print    # show the current census
"""

from __future__ import absolute_import, division, print_function

import argparse
import collections
import glob
import os
import sys

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE_GLOB = os.path.join(REPO_ROOT, "tests", "sanity", "ignore-*.txt")

# MUST NOT be ignored: fix the finding, delete the entry.
# Source: collection_requirements.html#ci-testing
MUST_NOT_IGNORE = frozenset((
    "validate-modules:doc-choices-do-not-match-spec",
    "validate-modules:doc-default-does-not-match-spec",
    "validate-modules:doc-missing-type",
    "validate-modules:doc-required-mismatch",
    "validate-modules:mutually_exclusive-unknown",
    "validate-modules:no-log-needed",
    "validate-modules:nonexistent-parameter-documented",
    "validate-modules:parameter-list-no-elements",
    "validate-modules:parameter-type-not-in-doc",
))

# Ignorable only in two narrow cases (a deprecated dangerous parameter kept
# solely to warn, or parameters injected by an accompanying action plugin).
# An entry here is a claim to one of those exemptions and is counted, not
# banned -- but the ceiling keeps the claim from spreading.
CONDITIONAL = frozenset((
    "validate-modules:undocumented-parameter",
))

# Ceiling for the TOTAL number of entries across all four files.  Like the
# per-code ceilings this only goes down: the whole point of replacing the old
# BASELINE_TOTAL budget is that the debt shrinks rather than being managed.
TOTAL_CEILING = 204

# Ratchet: the census measured when this guard was introduced (2026-09-24).
# These numbers may only go DOWN.  Raising one requires deleting the finding,
# not the assertion -- see docs/sanity-ignore-remediation.md.
CEILING = {
    "validate-modules:missing-gplv3-license": 0,
    "validate-modules:doc-default-does-not-match-spec": 0,
    "validate-modules:parameter-type-not-in-doc": 0,
    "validate-modules:nonexistent-parameter-documented": 0,
    "validate-modules:no-log-needed": 0,
    "validate-modules:doc-choices-do-not-match-spec": 0,
    "validate-modules:undocumented-parameter": 0,
}


def parse_entries():
    """Yield (path, lineno, relative_path, code, has_justification)."""
    for path in sorted(glob.glob(IGNORE_GLOB)):
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                if len(parts) < 2:
                    yield path, lineno, stripped, "", False
                    continue
                # A justification is an inline comment after the code.
                justification = "#" in line.split(parts[1], 1)[1]
                yield path, lineno, parts[0], parts[1], justification


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the per-code census")
    args = parser.parse_args()

    counts = collections.Counter()
    uncommented = []
    dangling = []
    total = 0

    for path, lineno, rel, code, justified in parse_entries():
        relpath = os.path.relpath(path, REPO_ROOT)
        total += 1
        counts[code] += 1
        if not justified:
            uncommented.append("%s:%d: %s" % (relpath, lineno, rel))
        if not os.path.exists(os.path.join(REPO_ROOT, rel)):
            dangling.append("%s:%d: %s" % (relpath, lineno, rel))

    if args.show:
        for code, number in counts.most_common():
            print("%5d %s" % (number, code))
        print("TOTAL %d across %d file(s)" % (total, len(glob.glob(IGNORE_GLOB))))
        return 0

    problems = []

    for code in sorted(MUST_NOT_IGNORE):
        if counts[code]:
            problems.append(
                "%s: %d entr(y/ies) name a code that MUST NOT be ignored "
                "(fix the finding and delete the entry)" % (code, counts[code]))

    for code, ceiling in sorted(CEILING.items()):
        if counts[code] > ceiling:
            problems.append(
                "%s: %d entr(y/ies) exceed the ratchet ceiling %d "
                "(the ceiling only goes down)" % (code, counts[code], ceiling))

    if total > TOTAL_CEILING:
        problems.append(
            "%d entr(y/ies) in total exceed the ratchet ceiling %d "
            "(the ceiling only goes down)" % (total, TOTAL_CEILING))

    if uncommented:
        problems.append(
            "%d entr(y/ies) carry no justification comment, e.g. %s"
            % (len(uncommented), uncommented[0]))

    if dangling:
        problems.append(
            "%d entr(y/ies) name a file that does not exist, e.g. %s"
            % (len(dangling), dangling[0]))

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem, file=sys.stderr)
        if len(uncommented) > 1:
            print("  (all unjustified entries: %s)" % ", ".join(uncommented[:10]),
                  file=sys.stderr)
        return 1

    print("ok: 0 entries on the must-not-ignore list")
    print("ok: every entry carries a justification comment")
    print("ok: total %d entr(y/ies) within the ratchet ceiling" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
