# -*- coding: utf-8 -*-
"""Synchronize the hand-maintained module registry with plugins/modules/.

``meta/runtime.yml``'s ``action_groups.all`` list powers
``module_defaults: group/susunola.tencentcloud.all`` and duplicates the
list of modules in ``plugins/modules/``; left to rot, a module is added or
removed and the group silently drifts from what ships.

Run without arguments to rewrite the managed region in place; run with
``--check`` (used in CI) to exit 1 when the registry is stale. Everything
outside the managed region is preserved verbatim: the ``requires_ansible``
line and the ``plugin_routing`` comment block.

The README module tables and the ``galaxy.yml`` module count used to be
managed here too. Both are gone by design: docs/REMEDIATION.md forbids
regenerating README catalog tables to advertise the module count.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "plugins" / "modules"
RUNTIME_YML = REPO_ROOT / "meta" / "runtime.yml"


def discover_modules(modules_dir):
    """Return the names of every module in *modules_dir*, sorted."""
    return sorted(
        path.stem
        for path in Path(modules_dir).glob("*.py")
        if not path.name.startswith("__")
    )


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="do not write files; fail if a registry is stale",
    )
    args = parser.parse_args(argv)

    module_names = discover_modules(MODULES_DIR)
    rendered = render_runtime_yml(
        RUNTIME_YML.read_text(encoding="utf-8"), module_names)

    if RUNTIME_YML.read_text(encoding="utf-8") == rendered:
        print("up to date: %s" % RUNTIME_YML)
    elif args.check:
        print("stale registries: %s" % RUNTIME_YML, file=sys.stderr)
        return 1
    else:
        RUNTIME_YML.write_text(rendered, encoding="utf-8")
        print("wrote: %s" % RUNTIME_YML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
