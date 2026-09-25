#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hold every shared helper to its own coverage floor.

Why
---
The coverage gate measures ``plugins/module_utils`` and ``plugins/modules``
together and fails below 80%. That is a good gate for the whole surface and a
blind one for a single file: a new shared helper can land with no tests at all
and move the total by a fraction of a point. It is how
``cos_bucket_read.py`` came to sit at 89% -- twelve uncovered lines, every one
of them a defensive branch (an empty payload, a single rule returned as a
mapping rather than a list) that the module tests never reach because they all
pass well-formed payloads. Those branches are the ones the API itself hits.

This reads the ``coverage.xml`` the CI coverage step already writes and
compares each file under ``plugins/module_utils`` and ``plugins/plugin_utils``
with its own floor. The floor is deliberately a few points below the lowest
measured file: it is there to catch a helper that arrives untested, not to
ratchet the last few branches of a file that is already exercised through its
callers.

Usage
-----
    python scripts/check_shared_coverage.py --coverage-xml coverage.xml
    python scripts/check_shared_coverage.py --coverage-xml coverage.xml --min 90
"""

from __future__ import absolute_import, division, print_function

import argparse
import os
import sys
from xml.etree import ElementTree

__metaclass__ = type

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directories whose files are shared by many plugins, so a gap in one is a
#: gap in everything that calls it.
SHARED = ("plugins/module_utils/", "plugins/plugin_utils/")

#: The measured files when this gate was introduced: client.py at 91.0,
#: resolver.py 92.3, tdmysql.py 94.1, cos.py 94.9, monitor.py 97.4 and the rest
#: at or above 99. The floor sits six points under the lowest of them on
#: purpose -- it is here to catch a shared helper that arrives untested, not to
#: ratchet the last few branches of a file that is already exercised through
#: its callers, and a floor set at the measured minimum would flip on a
#: comment-only change.
DEFAULT_MIN = 85.0


def shared_files(coverage_xml):
    """Return [(path, percent)] for every shared helper in the report."""
    tree = ElementTree.parse(coverage_xml)
    found = []
    for element in tree.iter("class"):
        filename = element.get("filename") or ""
        rate = element.get("line-rate")
        if rate is None:
            continue
        normalised = filename.replace("\\", "/")
        for part in SHARED:
            index = normalised.find(part)
            if index >= 0:
                found.append((normalised[index:], round(float(rate) * 100, 1)))
                break
    return sorted(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--coverage-xml", default=os.path.join(REPO_ROOT, "coverage.xml"),
                        help="the report the coverage step writes")
    parser.add_argument("--min", type=float, default=DEFAULT_MIN,
                        help="per-file floor in percent (default %s)" % DEFAULT_MIN)
    args = parser.parse_args(argv)

    if not os.path.isfile(args.coverage_xml):
        print("no coverage report at %s" % args.coverage_xml, file=sys.stderr)
        return 2

    files = shared_files(args.coverage_xml)
    if not files:
        print("no shared helper found in %s" % args.coverage_xml, file=sys.stderr)
        return 2

    below = [(path, percent) for path, percent in files if percent < args.min]
    for path, percent in files:
        print("%-58s %5.1f%% %s" % (path, percent, "ok" if percent >= args.min else "BELOW"))
    if below:
        print("\n%d shared helper(s) below %.0f%%:" % (len(below), args.min))
        for path, percent in below:
            print("  - %s: %.1f%%" % (path, percent))
        return 1
    print("\nall %d shared helper(s) are at or above %.0f%%" % (len(files), args.min))
    return 0


if __name__ == "__main__":
    sys.exit(main())
