#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Check that the headline figures quoted in docs/panorama.html are true.

Every number on the benchmark page is measured, not remembered. Two of them
had already drifted: the unit-test file count was quoted as 1,014 after two
new guard files had landed, and plugin_utils was called 6 files when it has
5 -- the convention that gives module_utils 16 excludes ``__init__.py``.
Nothing in the gate noticed either, because nothing re-measured them.

A number is matched as a whole number, never as a substring: ``55`` occurs
inside ``1557`` and ``553``, both of which the page quotes elsewhere, and
that made a claim pass while the page never stated the figure at all.

The check is deliberately one-directional: for each figure it looks for a
line of the doc that carries both the figure and a keyword that pins what
the figure means. A figure that is edited away, or edited to a wrong value,
stops finding such a line and fails.
"""

from __future__ import absolute_import, division, print_function

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANORAMA = "docs/panorama.html"
CAPABILITIES = "scripts/generate_product_capabilities.py"
BACKLOG = "scripts/gap_backlog.py"
WORKFLOW = ".github/workflows/integration.yml"
IGNORE_CHECK = "scripts/check_sanity_ignore.py"

# (label, keywords that must share the line with the value)
CLAIMS = (
    ("modules", ("模块",)),
    ("write modules", ("write", "_info")),
    ("info modules", ("write", "_info")),
    ("products", ("产品",)),
    ("products with write", ("含写", "write")),
    ("roles", ("roles",)),
    ("unit test files", ("test_*.py", "单测")),
    ("module-level unit files", ("模块级",)),
    ("module-level test functions", ("测试函数",)),
    ("read-side gap", ("_info 读面", "读面缺口")),
    ("read-side gap products", ("读面", "产品")),
    ("read-side mapped", ("映射", "mapped")),
    ("read-side backlog", ("backlog", "待补")),
    ("read-side no-list-api", ("no-list-api", "无列表")),
    ("read-side backlog products", ("backlog", "产品")),
    ("integration target dirs", ("targets", "目录数")),
    ("integration default list", ("默认清单",)),
    ("sanity ignores", ("ignore", "豁免")),
    ("sanity ignore budget", ("预算", "封顶")),
    ("event_source plugins", ("event_source",)),
    ("inventory plugins", ("inventory",)),
    ("lookup plugins", ("lookup",)),
    ("doc_fragments", ("doc_fragments",)),
    ("module_utils", ("module_utils",)),
    ("plugin_utils", ("plugin_utils",)),
)


def _py_files(directory):
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.py") if not p.name.startswith("__"))


def _test_functions(paths):
    """Count test functions declared at module scope (``def test_`` at column 0).

    The rule is part of the figure. The page once quoted this number twice,
    as 10,826 in one place and 10,869 in another, and neither reproduced
    under any stated rule -- because the number was remembered instead of
    measured. Counting here means the page cannot disagree with the repo.
    """
    total = 0
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("def test_"):
                total += 1
    return total


def _product_count(root):
    """Use the repo's own product definition rather than a guess."""
    path = root / CAPABILITIES
    spec = importlib.util.spec_from_file_location("_gpc", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    products = module.inventory(
        modules_dir=str(root / "plugins" / "modules"),
        roles_dir=str(root / "roles"),
    )
    return len(products), sum(1 for value in products.values() if value["write"])


def _backlog(root):
    """Return the read-side split scripts/gap_backlog.py computes.

    ``read-side gap`` alone is not a backlog: a write module without a
    sibling ``_info`` may already be read through a curated mapping, or the
    resource may have no list API at all. Only the ``backlog`` bucket is
    actionable, so the docs have to state all three.
    """
    path = root / BACKLOG
    spec = importlib.util.spec_from_file_location("_gap_backlog", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.collect(root)
    counts = data["counts"]
    products = data["by_product"]
    return {
        "read-side mapped": counts["mapped"],
        "read-side no-list-api": counts["no-list-api"],
        "read-side backlog": counts["backlog"],
        "read-side backlog products": len(products["backlog"]),
        "read-side gap products": len(
            set(products["mapped"])
            | set(products["no-list-api"])
            | set(products["backlog"])),
    }


def _default_targets(root):
    text = (root / WORKFLOW).read_text(encoding="utf-8")
    match = re.search(r"inputs\.targets\s*\|\|\s*'([^']*)'", text)
    return len(match.group(1).split()) if match else 0


def _ignore_budget(root):
    text = (root / IGNORE_CHECK).read_text(encoding="utf-8")
    match = re.search(r"^BASELINE_TOTAL\s*=\s*(\d+)", text, re.M)
    return int(match.group(1)) if match else 0


def _ignore_total(root):
    total = 0
    for path in sorted((root / "tests" / "sanity").glob("ignore-*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                total += 1
    return total


def measure(root):
    """Return the {label: value} map the docs must agree with."""
    modules = _py_files(root / "plugins" / "modules")
    write = [p for p in modules if not p.stem.endswith("_info")]
    info = [p for p in modules if p.stem.endswith("_info")]
    info_stems = {p.stem for p in info}
    gap = [p for p in write if "%s_info" % p.stem not in info_stems]

    unit_dir = root / "tests" / "unit"
    unit_files = sorted(unit_dir.rglob("test_*.py"))
    module_level = sorted((unit_dir / "plugins" / "modules").glob("test_*.py"))

    products, products_with_write = _product_count(root)

    figures = {
        "modules": len(modules),
        "write modules": len(write),
        "info modules": len(info),
        "products": products,
        "products with write": products_with_write,
        "roles": len([p for p in (root / "roles").iterdir() if p.is_dir()]),
        "unit test files": len(unit_files),
        "module-level unit files": len(module_level),
        "module-level test functions": _test_functions(module_level),
        "read-side gap": len(gap),
        "integration target dirs": len(
            [p for p in (root / "tests" / "integration" / "targets").iterdir()
             if p.is_dir()]),
        "integration default list": _default_targets(root),
        "sanity ignores": _ignore_total(root),
        "sanity ignore budget": _ignore_budget(root),
    }
    for name in ("event_source", "inventory", "lookup", "doc_fragments",
                 "module_utils", "plugin_utils"):
        figures["%s plugins" % name if name not in
                ("doc_fragments", "module_utils", "plugin_utils") else name] = \
            len(_py_files(root / "plugins" / name))
    figures.update(_backlog(root))
    return figures


NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(line):
    """Whole numbers on a line, as numbers.

    Substring matching is not good enough: ``55`` occurs inside ``1557``
    and ``553``, and the page is full of both, so the ``read-side gap
    products`` claim passed while the doc never stated it. Commas and a
    trailing decimal point are stripped; ``1,017`` and ``1017`` are the
    same number.
    """
    found = set()
    for token in NUMBER_RE.findall(line):
        text = token.replace(",", "").rstrip(".")
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        found.add(int(value) if value.is_integer() else value)
    return found


def validate(figures, doc_text):
    """Return the list of figures the doc no longer states correctly."""
    lines = doc_text.splitlines()
    problems = []
    for label, keywords in CLAIMS:
        value = figures.get(label)
        if value is None:
            problems.append("%s: not measured" % label)
            continue
        hit = any(
            any(keyword in line for keyword in keywords)
            and value in _numbers(line)
            for line in lines
        )
        if not hit:
            problems.append(
                "%s: %s is not stated in %s next to any of %s"
                % (label, value, PANORAMA, "/".join(keywords)))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero when a figure is not stated")
    parser.add_argument("--root", default=str(ROOT), help="collection root")
    args = parser.parse_args(argv)

    root = Path(args.root)
    figures = measure(root)
    doc_text = (root / PANORAMA).read_text(encoding="utf-8")
    problems = validate(figures, doc_text)

    for label, keywords in CLAIMS:
        assert keywords  # the claim is meaningless without a keyword to pin it
        value = figures.get(label)
        state = "MISSING" if any(p.startswith(label + ":") for p in problems) else "ok"
        print("%-28s %-8s %s" % (label, value, state))
    if problems:
        print("\nproblems (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
    else:
        print("\nall %d figures are stated in %s" % (len(CLAIMS), PANORAMA))

    if args.check and problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
