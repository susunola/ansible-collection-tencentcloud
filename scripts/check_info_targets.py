# -*- coding: utf-8 -*-
"""Validate ``scripts/info_specs_targets.py`` against what actually shipped.

``scripts/discover_info_specs.py`` scores every ``Describe*``/``List*``
action of an SDK product and keeps only the single best one. That is the
right default for discovery, but it systematically under-covers
multi-resource products: apigateway, ckafka and trabbit each own several
list APIs and only ever got one ``_info`` module between them.

``scripts/info_specs_targets.py`` is the curated answer -- a hand-written
table naming, per write module, the SDK action that reads the resource
back. It is hand-maintained, which makes it exactly the kind of metadata
that rots silently: an entry can name a write module that was renamed, an
action the SDK dropped, or a spec the generator then refuses to emit, and
nothing fails -- the target simply disappears from the skip report.

This guard closes that hole in both directions:

* declared -> disk: every target's write module exists, its
  ``<name>_info`` module was generated, and it has a unit test;
* spec -> declared: the set of specs the generator marked with
  ``TARGET_VERSION_ADDED`` is *exactly* the target set, so a target whose
  action no longer resolves (and therefore yields no spec) fails here
  instead of quietly shrinking the read surface.

Run with ``--check`` to fail CI, mirroring the other ``check_*.py`` gates.

    python scripts/check_info_targets.py           # report
    python scripts/check_info_targets.py --check   # CI gate
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
TARGETS_PATH = SCRIPTS / "info_specs_targets.py"
MODULES_REL = ("plugins", "modules")
TESTS_REL = ("tests", "unit", "plugins", "modules")


def _load_module(path, name):
    """Import *path* under *name*; return the module (never cached)."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _target_action(value):
    """Return the SDK action named by a TARGETS *value*."""
    return value["action"] if isinstance(value, dict) else value


def validate(root=REPO_ROOT):
    """Return a sorted list of problems for the curated targets table.

    *root* is honoured for every input -- the two data files included -- so
    the unit tests can point the guard at a throwaway tree instead of the
    real collection.
    """
    problems = []
    root = Path(root)
    targets_path = root.joinpath("scripts", "info_specs_targets.py")
    specs_path = root.joinpath("scripts", "info_specs_auto.py")
    targets_mod = _load_module(targets_path, "info_specs_targets")
    targets = getattr(targets_mod, "TARGETS", None)
    if not isinstance(targets, dict):
        return ["scripts/info_specs_targets.py must define a TARGETS mapping"]
    if not targets:
        # Anti-vacuity: an empty table would make every check below pass.
        return ["scripts/info_specs_targets.py declares no targets"]

    modules_dir = root.joinpath(*MODULES_REL)
    tests_dir = root.joinpath(*TESTS_REL)

    for write in sorted(targets):
        value = targets[write]
        action = None
        if isinstance(value, dict):
            action = value.get("action")
            if not isinstance(action, str) or not action.strip():
                problems.append(
                    "target '%s' has no non-empty 'action'" % write)
            resource = value.get("resource")
            if resource is not None and (not isinstance(resource, str)
                                         or not resource.strip()):
                problems.append(
                    "target '%s' has an invalid 'resource' override" % write)
        elif isinstance(value, str):
            action = value
        else:
            problems.append(
                "target '%s' must be an action string or a mapping" % write)
        if write.endswith("_info"):
            problems.append(
                "target '%s' already names an _info module; targets key on "
                "the write module" % write)
        write_path = modules_dir / ("%s.py" % write)
        if not write_path.is_file():
            problems.append(
                "target '%s' has no write module plugins/modules/%s.py"
                % (write, write))
        info_path = modules_dir / ("%s_info.py" % write)
        if not info_path.is_file():
            problems.append(
                "target '%s' produced no plugins/modules/%s_info.py -- the "
                "action %r may no longer resolve"
                % (write, write, action))
        test_path = tests_dir / ("test_%s_info.py" % write)
        if not test_path.is_file():
            problems.append(
                "target '%s' produced no tests/unit/plugins/modules/"
                "test_%s_info.py" % (write, write))

    specs_mod = _load_module(specs_path, "info_specs_auto")
    specs = getattr(specs_mod, "SPECS_AUTO", None)
    if not isinstance(specs, list):
        return sorted(problems + [
            "scripts/info_specs_auto.py must define SPECS_AUTO"])
    version_added = getattr(targets_mod, "TARGET_VERSION_ADDED", None)
    if not isinstance(version_added, str) or not version_added.strip():
        return sorted(problems + [
            "scripts/info_specs_targets.py must define TARGET_VERSION_ADDED"])
    generated = {spec["module"] for spec in specs
                 if spec.get("version_added") == version_added}
    expected = {"%s_info" % write for write in targets}
    for name in sorted(generated - expected):
        problems.append(
            "%s is version_added %s but no target declares it -- drop the "
            "spec or add the target" % (name, version_added))
    for name in sorted(expected - generated):
        problems.append(
            "%s is declared as a target but carries no version_added %s "
            "spec -- discovery rejected it" % (name, version_added))
    return sorted(problems)


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when the curated targets do not match what shipped",
    )
    args = parser.parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr

    problems = validate()
    targets_mod = _load_module(TARGETS_PATH, "info_specs_targets")
    targets = getattr(targets_mod, "TARGETS", {})
    print("curated targets: %d" % len(targets), file=out)
    if problems:
        print("problems (%d):" % len(problems), file=out)
        for problem in problems:
            print("  %s" % problem, file=out)
    else:
        print("every curated target shipped an _info module and a unit test",
              file=out)

    if problems and args.check:
        print("fix scripts/info_specs_targets.py (or regenerate) so every "
              "declared target produces an _info module, a unit test and a "
              "spec", file=err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
