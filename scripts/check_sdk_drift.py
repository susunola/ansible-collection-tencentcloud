#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI sentinel: the committed auto specs must match the installed SDK.

The auto specs in ``scripts/info_specs_auto.py`` are derived by
introspecting the installed tencentcloud SDK packages (request/response
field names, filter shapes, pagination types). The file carries a
``GENERATED_SDK_VERSION`` stamp recording the SDK release the specs were
discovered against.

``requirements.txt`` allows the SDK as a compatibility range for users,
so CI re-pins it to the stamp (``--print-stamp``) before running this
check; the check then compares the stamp to the SDK installed in the
current environment and exits non-zero on drift, so CI fails loudly
instead of silently shipping ``_info`` modules generated against an
unknown SDK. The fix is a deliberate regeneration - re-run discovery,
review the diff and commit the regeneration together with the SDK bump
(see the failure message for the exact steps).
"""

from __future__ import absolute_import, division, print_function

import argparse
import re
import sys
from importlib.metadata import PackageNotFoundError, version as dist_version
from pathlib import Path

AUTO_SPECS_PATH = Path(__file__).resolve().parent / "info_specs_auto.py"

STAMP_RE = re.compile(r'^GENERATED_SDK_VERSION\s*=\s*["\']([^"\']+)["\']', re.M)

FIX_MESSAGE = """
The _info module set (auto specs + generated modules + tests) was produced
against a different SDK release than the one installed here. Resolve the
drift deliberately:

  1) python scripts/discover_info_specs.py    # refresh SPECS_AUTO + stamp
  2) python scripts/generate_info_modules.py  # regenerate modules/tests
  3) review the diff (new/changed/renamed modules) and the skip report
  4) commit the regeneration together with the SDK bump

If re-discovery produced no changes to SPECS_AUTO, bump the
GENERATED_SDK_VERSION stamp to the installed version and commit that.
"""


def stamped_version(path):
    """Return the SDK version recorded next to the committed auto specs."""
    text = path.read_text(encoding="utf-8")
    match = STAMP_RE.search(text)
    if not match:
        raise ValueError(
            "no GENERATED_SDK_VERSION stamp found in %s (re-run "
            "scripts/discover_info_specs.py to regenerate)" % path)
    return match.group(1)


def installed_version():
    """Return the tencentcloud-sdk-python version in this environment."""
    try:
        return dist_version("tencentcloud-sdk-python")
    except PackageNotFoundError:
        pass
    try:
        import tencentcloud
        return tencentcloud.__version__
    except ImportError:
        raise RuntimeError(
            "tencentcloud-sdk-python is not installed; install "
            "requirements.txt first (python -m pip install -r requirements.txt)")


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit non-zero (default behaviour)")
    parser.add_argument("--print-stamp", action="store_true",
                        help="print the stamped SDK version and exit; CI uses "
                             "this to re-pin the SDK to the stamp before "
                             "running the strict drift check")
    parser.add_argument("--specs", metavar="PATH", default=str(AUTO_SPECS_PATH),
                        help="path to info_specs_auto.py (mainly for tests)")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    if args.print_stamp:
        try:
            out.write(stamped_version(Path(args.specs)) + "\n")
            return 0
        except (ValueError, OSError) as exc:
            err.write("SDK drift check failed: %s\n" % exc)
            return 1

    try:
        stamp = stamped_version(Path(args.specs))
        installed = installed_version()
    except (ValueError, RuntimeError, OSError) as exc:
        err.write("SDK drift check failed: %s\n" % exc)
        return 1

    if stamp == installed:
        out.write("SDK drift check OK: auto specs generated with %s\n" % stamp)
        return 0

    err.write("SDK drift detected:\n")
    err.write("  auto specs stamped with: %s\n" % stamp)
    err.write("  installed SDK version:   %s\n" % installed)
    err.write(FIX_MESSAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
