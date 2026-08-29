# -*- coding: utf-8 -*-
"""Synchronize the hand-maintained module registries with plugins/modules/.

Three registries duplicate the list of modules in ``plugins/modules/`` and
rot silently when a module is added or removed:

* ``meta/runtime.yml`` -- the ``action_groups.all`` list that powers
  ``module_defaults: group/susunola.tencentcloud.all``;
* ``README.md`` -- the resource-module table and the ``_info`` module table.

Run without arguments to rewrite the managed regions in place; run with
``--check`` (used in CI) to exit 1 when any registry is stale. Everything
outside the managed regions is preserved verbatim: the ``requires_ansible``
line and the ``plugin_routing`` comment block in ``meta/runtime.yml``, and
all non-table content in ``README.md`` (including the hand-written note
paragraph between the two module tables).

README table row descriptions come from each module's DOCUMENTATION
``short_description``; write modules go into the resource table and
``*_info`` modules into the info table, both sorted by module name.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "plugins" / "modules"
RUNTIME_YML = REPO_ROOT / "meta" / "runtime.yml"
README_MD = REPO_ROOT / "README.md"

TABLE_HEADER = "| Module | Purpose |"
TABLE_SEPARATOR = "| --- | --- |"

_DOC_RE = re.compile(r"^DOCUMENTATION = r?(?P<quote>'''|\"\"\")\n(?P<body>.*?)\n(?P=quote)", re.M | re.S)


def discover_modules(modules_dir):
    """Return the names of every module in *modules_dir*, sorted."""
    return sorted(
        path.stem
        for path in Path(modules_dir).glob("*.py")
        if not path.name.startswith("__")
    )


def split_modules(module_names):
    """Split module names into (write modules, ``_info`` modules)."""
    info = [name for name in module_names if name.endswith("_info")]
    write = [name for name in module_names if not name.endswith("_info")]
    return write, info


def short_description(module_path):
    """Return the DOCUMENTATION ``short_description`` of *module_path*."""
    text = Path(module_path).read_text(encoding="utf-8")
    match = _DOC_RE.search(text)
    if not match:
        raise ValueError("%s: no DOCUMENTATION block found" % module_path)
    doc = yaml.safe_load(match.group("body"))
    return doc["short_description"]


def render_runtime_yml(text, module_names):
    """Return *text* with the ``action_groups.all`` list replaced.

    Only the ``    - <module>`` items directly under ``action_groups.all``
    are rewritten; ``requires_ansible``, ``plugin_routing`` and the comment
    block are preserved verbatim.
    """
    lines = text.splitlines(keepends=True)
    if "action_groups:\n" not in lines:
        raise ValueError("meta/runtime.yml: no 'action_groups:' mapping found")
    header = lines.index("action_groups:\n") + 1
    if lines[header] != "  all:\n":
        raise ValueError("meta/runtime.yml: expected '  all:' under 'action_groups:'")
    end = header + 1
    while end < len(lines) and lines[end].startswith("    - "):
        end += 1
    rows = ["    - %s\n" % name for name in module_names]
    return "".join(lines[:header + 1] + rows + lines[end:])


def module_row(name, description):
    """Render one README module-table row."""
    return "| `%s` | %s |\n" % (name, description)


def _replace_table(lines, header_index, rows):
    if lines[header_index + 1].rstrip("\n") != TABLE_SEPARATOR:
        raise ValueError("README.md: malformed module table header")
    end = header_index + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return lines[:header_index + 2] + rows + lines[end:]


def render_readme(text, write_rows, info_rows):
    """Return *text* with the two module tables replaced by the given rows.

    The first ``| Module | Purpose |`` table is the resource (write module)
    table, the second the ``_info`` table. Headers, separators, the plugins
    table and the note paragraph between the module tables are untouched.
    """
    lines = text.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if line.rstrip("\n") == TABLE_HEADER]
    if len(headers) != 2:
        raise ValueError(
            "README.md: expected exactly two %r tables, found %d"
            % (TABLE_HEADER, len(headers)))
    # Replace from the bottom up so the first header index stays valid.
    lines = _replace_table(lines, headers[1], info_rows)
    lines = _replace_table(lines, headers[0], write_rows)
    return "".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="do not write files; fail if a registry is stale",
    )
    args = parser.parse_args(argv)

    module_names = discover_modules(MODULES_DIR)
    write_names, info_names = split_modules(module_names)
    descriptions = {
        name: short_description(MODULES_DIR / (name + ".py"))
        for name in module_names
    }
    write_rows = [module_row(name, descriptions[name]) for name in write_names]
    info_rows = [module_row(name, descriptions[name]) for name in info_names]

    targets = [
        (RUNTIME_YML, render_runtime_yml(
            RUNTIME_YML.read_text(encoding="utf-8"), module_names)),
        (README_MD, render_readme(
            README_MD.read_text(encoding="utf-8"), write_rows, info_rows)),
    ]

    stale = []
    for path, rendered in targets:
        if path.read_text(encoding="utf-8") == rendered:
            print("up to date: %s" % path)
        elif args.check:
            stale.append(str(path))
        else:
            path.write_text(rendered, encoding="utf-8")
            print("wrote: %s" % path)

    if stale:
        print("stale registries: %s" % ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
