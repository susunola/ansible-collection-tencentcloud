# -*- coding: utf-8 -*-
"""Synchronize the hand-maintained module registries with plugins/modules/.

Three registries duplicate the list of modules in ``plugins/modules/`` and
rot silently when a module is added or removed:

* ``meta/runtime.yml`` -- the ``action_groups.all`` list that powers
  ``module_defaults: group/susunola.tencentcloud.all``;
* ``README.md`` -- the resource-module table and the ``_info`` module table;
* ``galaxy.yml`` -- the module count embedded in the ``description``.

Run without arguments to rewrite the managed regions in place; run with
``--check`` (used in CI) to exit 1 when any registry is stale. Everything
outside the managed regions is preserved verbatim: the ``requires_ansible``
line and the ``plugin_routing`` comment block in ``meta/runtime.yml``, and
all non-table content in ``README.md`` (including the hand-written note
paragraph between the two module tables).

README table row descriptions come from each module's DOCUMENTATION
``short_description``; write modules go into the resource table and
``*_info`` modules into the info table, both sorted by module name. Every
row renders the full FQCN (``susunola.tencentcloud.<module>``) plus a link
to the module source, which carries the module's complete documentation and
its EXAMPLES block. The module counts embedded in the README overview and in
the two ``<details>`` summary titles are derived here as well, so a module
batch cannot leave a stale "769 modules" paragraph behind.
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
GALAXY_YML = REPO_ROOT / "galaxy.yml"

FQCN_PREFIX = "susunola.tencentcloud."
TABLE_HEADER = "| Module (FQCN) | Purpose | Examples |"
TABLE_SEPARATOR = "| --- | --- | --- |"
# Historic header accepted on input so one script run migrates the README.
LEGACY_TABLE_HEADER = "| Module | Purpose |"
_TABLE_HEADERS = {LEGACY_TABLE_HEADER, TABLE_HEADER}

_DOC_RE = re.compile(r"^DOCUMENTATION = r?(?P<quote>'''|\"\"\")\n(?P<body>.*?)\n(?P=quote)", re.M | re.S)

# Count slots in the README that duplicate module numbers and rot silently.
# Each pattern must appear exactly once; group(1) is the stale count.
_COUNT_SLOTS = (
    # Capability-overview paragraph.
    (r"through \*\*(\d+) modules\*\*", "total"),
    (r"including \*\*(\d+) resource modules\*\*", "write"),
    (r"\*\*(\d+) read-only `_info` modules\*\*", "info"),
    # <details> summary titles of the two module tables.
    (r"Browse all (\d+) resource modules", "write"),
    (r"Browse all (\d+) read-only <code>_info</code> modules", "info"),
)


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
    """Render one README module-table row (FQCN + purpose + source link)."""
    return "| `%s%s` | %s | [`%s`](plugins/modules/%s.py) |\n" % (
        FQCN_PREFIX, name, description, name, name)


def _replace_table(lines, header_index, rows):
    """Replace header, separator and rows of the table at *header_index*.

    ``lines[header_index]`` is the (legacy or current) header line; its
    separator and every following ``|`` row are consumed and rewritten with
    the current header, separator and the generated *rows*.
    """
    end = header_index + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    block = [TABLE_HEADER + "\n", TABLE_SEPARATOR + "\n"] + rows
    return lines[:header_index] + block + lines[end:]


def sync_readme_counts(text, total, write_count, info_count):
    """Return *text* with the four README count slots refreshed.

    Every pattern in ``_COUNT_SLOTS`` must appear exactly once; a missing or
    duplicated slot raises instead of silently drifting.
    """
    counts = {"total": str(total), "write": str(write_count), "info": str(info_count)}
    for pattern, slot in _COUNT_SLOTS:
        text, n = re.subn(pattern, lambda m, value=counts[slot]: m.group(0).replace(m.group(1), value), text)
        if n != 1:
            raise ValueError(
                "README.md: count slot %r must appear exactly once, found %d"
                % (pattern, n))
    return text


def render_readme(text, write_rows, info_rows):
    """Return *text* with the two module tables replaced by the given rows.

    The first module table is the resource (write module) table, the second
    the ``_info`` table. Headers, the plugins table and the note paragraphs
    between the module tables are rewritten only where they carry derived
    counts (see ``sync_readme_counts``).
    """
    lines = text.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines)
               if line.rstrip("\n") in _TABLE_HEADERS]
    if len(headers) != 2:
        raise ValueError(
            "README.md: expected exactly two module tables, found %d"
            % len(headers))
    # Replace from the bottom up so the first header index stays valid.
    lines = _replace_table(lines, headers[1], info_rows)
    lines = _replace_table(lines, headers[0], write_rows)
    return sync_readme_counts(
        "".join(lines),
        len(write_rows) + len(info_rows),
        len(write_rows),
        len(info_rows),
    )


def render_galaxy_yml(text, module_names):
    """Return *text* with the module count in ``description`` refreshed.

    The description embeds a count (e.g. "524 modules (resource modules plus
    _info facts modules) cover ..."). The count is the only generated part;
    the surrounding wording stays hand-written. A stale count is an easy
    slip (every description edit after a module batch lands), so this script
    keeps it derived like the README and runtime.yml registries.
    """
    match = re.search(
        r"(?P<prefix>description: \".*?)(?P<count>\d+) modules", text, re.S)
    if not match:
        raise ValueError("galaxy.yml: no '<n> modules' count in description")
    count = str(len(module_names))
    if match.group("count") != count:
        return text[:match.start("count")] + count + text[match.end("count"):]
    return text


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
        (GALAXY_YML, render_galaxy_yml(
            GALAXY_YML.read_text(encoding="utf-8"), module_names)),
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
