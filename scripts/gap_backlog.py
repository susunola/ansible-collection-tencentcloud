#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Read-surface backlog reporter (offline).

Splits the write modules that have no sibling ``<name>_info`` into the three
verdicts ``scripts/audit_info_coverage.py`` already computes:

* **mapped** -- a curated KNOWN_COVERAGE entry points the write module at an
  existing ``_info`` that really returns the resource. Not a gap at all.
* **no-list-api** -- the service exposes no list/describe API for the
  resource, so an ``_info`` cannot honestly be generated. Not actionable.
* **backlog** -- a scoped list API exists and nobody wired it up yet. This
  is the only actionable part of the backlog.

The previous version of this tool scraped ``KNOWN_GAPS`` out of
``audit_info_coverage.py`` with a regex that only matched double-quoted
names, while the set is written with single quotes -- so it reported
``0 in KNOWN_GAPS`` and every single entry as UNTRACKED. It also counted a
write module as a gap purely because ``<name>_info`` was absent, which
inflated the headline to 226 and hid the fact that only part of that is
actionable. This version **imports** the audit module and reuses its
verdicts, so the two can no longer drift, and it groups modules by product
using the repo's own product definition instead of ``name.split('_')[0]``
(which conflated ``api_gateway_*`` with ``apigateway_*``).

Usage::

    python scripts/gap_backlog.py            # per-product report
    python scripts/gap_backlog.py --all      # do not truncate long products
"""

from __future__ import absolute_import, division, print_function

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = "scripts/audit_info_coverage.py"
CAPABILITIES_PATH = "scripts/generate_product_capabilities.py"

MAPPED = "mapped"
NO_LIST_API = "no-list-api"
BACKLOG = "backlog"
UNCOVERED = "uncovered"
# Ordered the way a reader should read them: mapped is already fine,
# no-list-api is unfixable, backlog is the work.
BUCKETS = (MAPPED, NO_LIST_API, BACKLOG, UNCOVERED)


def _load(root, relative, name):
    """Import a script by file path (it has no importable package)."""
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def product_map(root):
    """Return {module name: product} using the repo's own product split."""
    capabilities = _load(root, CAPABILITIES_PATH, "_gap_backlog_capabilities")
    inventory = capabilities.inventory(
        modules_dir=str(root / "plugins" / "modules"),
        roles_dir=str(root / "roles"),
    )
    mapping = {}
    for product, buckets in inventory.items():
        for key in ("write", "info"):
            for module in buckets[key]:
                mapping[module] = product
    return mapping


def collect(root):
    """Return the backlog structure; see ``report`` for the rendering.

    Keys: ``counts`` ({bucket: n}), ``by_product`` ({bucket: {product:
    [names]}}), ``covered`` (n), ``write_modules`` (n), ``uncovered``
    ([names]).
    """
    audit = _load(root, AUDIT_PATH, "_gap_backlog_audit")
    rows, uncovered = audit.audit()
    products = product_map(root)

    by_product = {bucket: {} for bucket in BUCKETS}
    covered = 0
    for name, verdict, detail in rows:
        if verdict == "covered":
            covered += 1
            continue
        if verdict == "gap":
            bucket = detail.split(":")[0].strip()
        else:
            bucket = verdict
        product = products.get(name, name.split("_")[0])
        by_product.setdefault(bucket, {}).setdefault(product, []).append(name)

    for bucket in by_product:
        for product in by_product[bucket]:
            by_product[bucket][product].sort()

    return {
        "write_modules": len(rows),
        "covered": covered,
        "counts": {bucket: sum(len(v) for v in by_product[bucket].values())
                   for bucket in BUCKETS},
        "by_product": by_product,
        "uncovered": sorted(uncovered),
    }


def report(data, show_all=False, limit=8):
    """Render the collected structure as text lines."""
    lines = []
    counts = data["counts"]
    missing_sibling = sum(counts[bucket] for bucket in BUCKETS)
    lines.append("write modules          %d" % data["write_modules"])
    lines.append("  sibling _info        %d" % data["covered"])
    lines.append("  no sibling _info     %d" % missing_sibling)
    for bucket in BUCKETS:
        if counts[bucket]:
            lines.append("    %-16s %d" % (bucket, counts[bucket]))
    lines.append("products with backlog  %d" % len(data["by_product"][BACKLOG]))
    lines.append("")

    for bucket in BUCKETS:
        products = data["by_product"][bucket]
        if not products:
            continue
        lines.append("== %s (%d)" % (bucket, counts[bucket]))
        for product in sorted(products, key=lambda p: (-len(products[p]), p)):
            names = products[product]
            lines.append("## %s: %d" % (product, len(names)))
            shown = names if show_all or len(names) <= limit else names[:limit]
            for name in shown:
                lines.append("   %s" % name)
            if len(shown) < len(names):
                lines.append("   ... %d more" % (len(names) - len(shown)))
        lines.append("")
    return "\n".join(lines)


def main(argv=None, out=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true",
                        help="list every module instead of truncating")
    parser.add_argument("--root", default=str(ROOT), help="collection root")
    args = parser.parse_args(argv)

    data = collect(Path(args.root))
    text = report(data, show_all=args.all)
    print(text, file=out or sys.stdout)
    return 1 if data["uncovered"] else 0


if __name__ == "__main__":
    sys.exit(main())
