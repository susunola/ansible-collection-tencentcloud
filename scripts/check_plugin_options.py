#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that a plugin's documented options are options the plugin reads.

Why
---
``validate-modules`` holds every module's documentation to its argument spec.
The plugins are documented by hand and nothing compared the two:
``plugins/inventory/tencentcloud_sg.py`` documented ``include_sgless`` from
the day it was written and never read it, so a user could set it in an
inventory file and silently get the default behaviour -- an inventory plugin
accepts any option it documents, and no test executed the plugin either.

What it checks
--------------
For every lookup and inventory plugin, each name in its ``DOCUMENTATION``
options must appear in a ``get_option("...")`` call. The options of the doc
fragments the plugin extends are resolved too, from this collection first and
then from the installed ansible-core, so ``constructed`` and
``inventory_cache`` count without being copied here.

* ``plugin`` is exempt: the inventory loader consumes it to pick the plugin,
  before the plugin runs.
* An option that is deliberately inert is listed in :data:`UNUSED_BY_DESIGN`
  with its reason, which is a reviewed decision rather than a silent one.

Action and event-source plugins are out of scope: an action plugin reads
``self._task.args`` and an event source reads its own configuration, so there
is no call site to compare the documentation against.

Usage
-----
    python scripts/check_plugin_options.py            # the census
    python scripts/check_plugin_options.py --check    # exit 1 on any finding
"""

from __future__ import absolute_import, division, print_function

import argparse
import importlib
import re
import sys
from pathlib import Path

import yaml

__metaclass__ = type

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRS = ("inventory", "lookup")
DOC_FRAGMENTS_DIR = REPO_ROOT / "plugins" / "doc_fragments"
COLLECTION_PREFIX = "susunola.tencentcloud."

DOC_RE = re.compile(r"DOCUMENTATION\s*=\s*r?(['\"]{3})(.*?)\1", re.S)

#: ``self.get_option("name")`` and ``self.get_option('name')``.
GET_OPTION_RE = re.compile(r"""get_option\(\s*["']([a-z0-9_]+)["']""")

#: Options the loader consumes before the plugin does, and options that are
#: documented as having no effect on purpose.
UNUSED_BY_DESIGN = {
    "plugin": "consumed by the inventory loader to select the plugin",
    "_terms": (
        "the lookup framework passes the terms to run(); they are an argument, "
        "not an option the plugin reads"),
    "with_decryption": (
        "documented for parity with the amazon.aws.aws_ssm lookup: "
        "GetSecretValue always returns the decrypted value"),
}


def plugin_sources():
    """Return ``(relative_path, path)`` for every lookup and inventory plugin."""
    sources = []
    for directory in PLUGIN_DIRS:
        root = REPO_ROOT / "plugins" / directory
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            sources.append((str(path.relative_to(REPO_ROOT)), path))
    return sources


def _documentation(text):
    """Return the parsed DOCUMENTATION mapping of *text*, or ``None``."""
    match = DOC_RE.search(text)
    if not match:
        return None
    try:
        parsed = yaml.safe_load(match.group(2))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _fragment_names(documentation):
    """Return the doc fragment names *documentation* extends."""
    fragments = documentation.get("extends_documentation_fragment") or []
    names = []
    for entry in fragments:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("fragment")
            if isinstance(name, str):
                names.append(name)
    return names


def fragment_options(name):
    """Return ``(options, builtin)`` for a doc fragment, or ``(None, False)``.

    The fragment is looked up in this collection first and then in the
    installed ansible-core, which is where ``constructed`` and
    ``inventory_cache`` live. A builtin fragment's options are read by
    ansible-core's own mixins (``Constructable``, ``Cacheable``) inside the
    plugin instance, so they are the framework's contract rather than the
    plugin's: they are reported separately and not held to a ``get_option``
    call in this repository.
    """
    short = name[len(COLLECTION_PREFIX):] if name.startswith(COLLECTION_PREFIX) else name
    local = DOC_FRAGMENTS_DIR / ("%s.py" % short)
    if local.is_file():
        documentation = _documentation(local.read_text(encoding="utf-8"))
        if documentation is not None:
            return set(documentation.get("options") or {}), False
    try:
        module = importlib.import_module("ansible.plugins.doc_fragments.%s" % short)
        documentation = yaml.safe_load(module.ModuleDocFragment.DOCUMENTATION)
    except Exception:  # noqa: BLE001 - an unknown fragment is reported below
        return None, False
    if not isinstance(documentation, dict):
        return None, False
    return set(documentation.get("options") or {}), True


def documented_options(text):
    """Return ``(options, unknown_fragments)`` for a plugin source.

    *options* holds what the plugin is responsible for reading: its own
    options and the options of this collection's fragments.
    """
    documentation = _documentation(text)
    if documentation is None:
        return None, set()
    options = set(documentation.get("options") or {})
    unknown = set()
    for name in _fragment_names(documentation):
        resolved, builtin = fragment_options(name)
        if resolved is None:
            unknown.add(name)
        elif not builtin:
            options |= resolved
    return options, unknown


def read_options(text):
    """Return the option names a plugin reads through ``get_option``."""
    return set(GET_OPTION_RE.findall(text))


def findings():
    """Return the documented options no ``get_option`` call reads."""
    problems = []
    for relative, path in plugin_sources():
        text = path.read_text(encoding="utf-8")
        options, unknown = documented_options(text)
        if options is None:
            problems.append("%s: no readable DOCUMENTATION block" % relative)
            continue
        for name in sorted(unknown):
            problems.append(
                "%s: extends doc fragment %r, which is neither in "
                "plugins/doc_fragments/ nor in the installed ansible-core"
                % (relative, name))
        unread = options - read_options(text) - set(UNUSED_BY_DESIGN)
        for name in sorted(unread):
            problems.append(
                "%s: documents option %r, which no get_option call reads -- "
                "either read it, drop it, or list it in UNUSED_BY_DESIGN with "
                "the reason" % (relative, name))
    return sorted(problems)


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any finding")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    problems = findings()
    print("%d plugin(s) checked, %d documented option(s) that no call reads"
          % (len(plugin_sources()),
             len([line for line in problems if "no get_option call reads" in line])),
          file=out)
    if problems:
        print("findings (%d):" % len(problems), file=out)
        for problem in problems:
            print("  %s" % problem, file=out)
    if problems and args.check:
        print("a documented plugin option must be one the plugin reads",
              file=err)
        return 1
    if not problems:
        print("plugin option check OK: every documented option is read", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
