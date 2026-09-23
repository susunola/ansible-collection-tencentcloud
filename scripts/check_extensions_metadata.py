# -*- coding: utf-8 -*-
"""Validate ``meta/extensions.yml`` against the plugin directories on disk.

``meta/extensions.yml`` declares the plugin types ansible-core does not
resolve natively (today: the ``ansible.eda`` event sources under
``plugins/event_source``) so that ansible-navigator, execution-environment
builders and Galaxy / Automation Hub can still find, package and surface
them.

The file is hand-maintained, which makes it exactly the kind of metadata
that rots silently: nothing fails when it goes stale. A declaration can
keep pointing at a directory that no longer exists, and a newly added
non-core plugin directory can ship undeclared. Neither is visible locally;
both surface only as missing content inside an execution-environment
image or on a Galaxy listing.

This guard therefore validates in both directions, the same shape as
``integration_impact.validate_target_dirs()``:

* declared -> disk: every ``args.ext_dir`` exists, is a directory and holds
  at least one Python file;
* disk -> declared: every ``plugins/<dir>`` that is neither an
  ansible-core plugin type nor a shared-library directory is declared.

Run with ``--check`` to fail CI, mirroring the other ``check_*.py`` gates.

    python scripts/check_extensions_metadata.py           # report
    python scripts/check_extensions_metadata.py --check   # CI gate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS_PATH = REPO_ROOT / "meta" / "extensions.yml"

# Plugin types ansible-core's own plugin loader resolves without help. They
# must not be declared (the file's comment says the same), and the reverse
# check never requires them.
CORE_PLUGIN_DIRS = {
    "action", "become", "cache", "callback", "cliconf", "connection",
    "doc_fragments", "filter", "httpapi", "inventory", "lookup", "module",
    "modules", "netconf", "shell", "strategy", "terminal", "test", "vars",
}

# Directories under plugins/ that hold importable Python rather than a
# loadable plugin type. They are never declared as extensions.
SHARED_LIB_DIRS = {"module_utils", "plugin_utils"}


def _load(path=EXTENSIONS_PATH):
    """Return ``(data, error)`` for the extensions manifest at *path*."""
    if not path.is_file():
        return None, "meta/extensions.yml is missing"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, "meta/extensions.yml is not valid YAML (%s)" % exc
    if data is None:
        return None, "meta/extensions.yml is empty"
    if not isinstance(data, dict):
        return None, "meta/extensions.yml must be a mapping at the top level"
    if "extensions" not in data:
        return None, "meta/extensions.yml has no 'extensions' key"
    if not isinstance(data["extensions"], list):
        return None, "'extensions' must be a list"
    return data, None


def _iter_declarations(data):
    """Yield ``(ext_dir, problem)`` for every entry in *data*.

    ``problem`` is ``None`` for a well-formed entry. Malformed entries are
    yielded rather than skipped so the report names the offending index.
    """
    for index, entry in enumerate(data["extensions"]):
        label = "extensions[%d]" % index
        if not isinstance(entry, dict):
            yield None, "%s must be a mapping" % label
            continue
        args = entry.get("args")
        if not isinstance(args, dict):
            yield None, "%s must carry an 'args' mapping" % label
            continue
        ext_dir = args.get("ext_dir")
        if not isinstance(ext_dir, str) or not ext_dir.strip():
            yield None, "%s.args.ext_dir must be a non-empty string" % label
            continue
        yield ext_dir.strip(), None


def validate(data, root=REPO_ROOT):
    """Return a sorted list of problems for the parsed manifest *data*."""
    problems = []
    declared = set()
    for ext_dir, problem in _iter_declarations(data):
        if problem:
            problems.append(problem)
            continue
        declared.add(ext_dir)
        # Compare the directory name, not the collection-relative path:
        # "plugins/lookup" is a core plugin type even though "lookup" is
        # the name the plugin loader knows.
        name = Path(ext_dir).name
        if name in CORE_PLUGIN_DIRS:
            problems.append(
                "declares '%s', which ansible-core already resolves "
                "natively -- extensions are only for plugin types it "
                "cannot load" % ext_dir)
            continue
        if name in SHARED_LIB_DIRS:
            problems.append(
                "declares '%s', which is a shared-library directory, not "
                "an extension" % ext_dir)
            continue
        parts = Path(ext_dir).parts
        if Path(ext_dir).is_absolute() or ".." in parts:
            problems.append(
                "declares '%s', which is not a collection-relative "
                "directory" % ext_dir)
            continue
        target = root / ext_dir
        if not target.is_dir():
            problems.append(
                "declares '%s' but that directory does not exist" % ext_dir)
            continue
        if not any(target.glob("*.py")):
            problems.append(
                "declares '%s' but it holds no Python plugin files" % ext_dir)

    for name in _undeclared_dirs(declared, root):
        problems.append(
            "plugins/%s is not an ansible-core plugin type and is not "
            "declared in meta/extensions.yml" % name)
    return sorted(problems)


def _undeclared_dirs(declared, root=REPO_ROOT):
    """Return non-core plugin directories on disk that *declared* omits."""
    plugins_root = root / "plugins"
    if not plugins_root.is_dir():
        return []
    undeclared = []
    for path in sorted(plugins_root.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        if path.name in CORE_PLUGIN_DIRS or path.name in SHARED_LIB_DIRS:
            continue
        # Declarations are collection-relative ("plugins/event_source"),
        # so compare against the same form rather than the bare name.
        if "plugins/%s" % path.name not in declared:
            undeclared.append(path.name)
    return undeclared


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when the extensions metadata does not match plugins/",
    )
    args = parser.parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr

    data, error = _load()
    if error:
        print("meta/extensions.yml: %s" % error, file=out)
        if args.check:
            print("meta/extensions.yml must declare every non-core plugin "
                  "directory", file=err)
            return 1
        return 0

    declared = [d for d, _problem in _iter_declarations(data) if d]
    print("declared extensions (%d): %s"
          % (len(declared), ", ".join(declared) or "-"), file=out)
    problems = validate(data)
    if problems:
        print("problems (%d):" % len(problems), file=out)
        for problem in problems:
            print("  %s" % problem, file=out)
    else:
        print("extensions metadata matches plugins/", file=out)

    if problems and args.check:
        print("fix meta/extensions.yml so every non-core plugin directory is "
              "declared and every declaration points at a populated "
              "directory", file=err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
