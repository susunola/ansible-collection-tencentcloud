# -*- coding: utf-8 -*-
"""Check the roadmap's "done" markers against their own acceptance criteria.

``docs/panorama.html`` closes with a 30-item priority table (P0-01 .. P2-08).
Each row carries a ``chip done`` badge once the item is considered achieved.
That badge is hand-maintained and nothing validates it, which makes it the
same kind of index ``meta/extensions.yml`` was before G1-f: it rots quietly
in *both* directions.

* It can claim an item is done when the acceptance criterion has never been
  met -- the badge is then marketing rather than status.
* It can leave an item unbadged long after the work landed, so the roadmap
  keeps advertising a gap that no longer exists. On 2026-09-14 nine items
  (P0-03, P0-09, P0-10, P0-11, P1-07, P1-09, P1-10, P2-03, P2-08) were in
  exactly that state: measured against their own written acceptance every
  one of them already passed, but the table still listed them as open.

This guard therefore measures what can be measured mechanically and compares
it with the badge in both directions. Items whose acceptance cannot be
reduced to a mechanical test (P0-05 and P0-06's read-surface waves, P2-01
and P2-02's external review) are deliberately absent from ``CRITERIA`` and
are reported as unmeasured rather than faked.

Run with ``--check`` to fail CI, mirroring the other ``check_*.py`` gates.

    python scripts/check_roadmap_status.py           # report
    python scripts/check_roadmap_status.py --check   # CI gate
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

PANORAMA = "docs/panorama.html"
README = "README.md"
CONTRIBUTING = "CONTRIBUTING.md"
TRIAGE = "docs/triage.md"
INTEGRATION_ENV = "docs/integration-env.md"
MODULE_UTILS_README = "plugins/module_utils/README.md"
PORTING = "docs/porting.md"
CHANGELOG = "changelogs/changelog.yaml"
CONTRACT_TEST = "tests/contract/test_sdk_contracts.py"
ROLE_TEST_DIR = "tests/unit/roles"
MODULE_TEST_DIR = "tests/unit/plugins/modules"
MODULES_DIR = "plugins/modules"
ROLES_DIR = "roles"
EXAMPLES_DIR = "docs/examples"
EXAMPLES_CHECKER = "scripts/check_examples.py"
WORKFLOWS_DIR = ".github/workflows"

# The three companion documents that quote the panorama's headline figures.
# P0-12's acceptance is that none of them is left on a stale number.
COMPANION_DOCS = ("docs/capability-map.html", "docs/roadmap.md", "docs/gap-closure.md")

ROW_RE = re.compile(
    r'<tr class="grp-p\d">\s*<td class="no">(P\d-\d\d)</td>(.*?)</tr>',
    re.DOTALL,
)
DONE_MARKER = "chip done"
FQCN_ROW_RE = re.compile(r"^\|\s*`susunola\.tencentcloud\.([a-z0-9_]+)`\s*\|", re.M)


# ---------------------------------------------------------------------------
# Repo facts
# ---------------------------------------------------------------------------


def _module_names(root=REPO_ROOT):
    """Every module name, split into write and ``_info`` halves."""
    names = sorted(
        p.stem for p in (root / MODULES_DIR).glob("*.py") if not p.name.startswith("__")
    )
    return names, [n for n in names if not n.endswith("_info")]


def _role_dirs(root=REPO_ROOT):
    return sorted(
        p for p in (root / ROLES_DIR).iterdir() if p.is_dir() and p.name.startswith("tc_")
    )


def _load(root, relative, name):
    """Import *relative* from *root* under the module name *name*."""
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Panorama table
# ---------------------------------------------------------------------------


def parse_panorama(root=REPO_ROOT):
    """Return ``{item_id: is_marked_done}`` for the priority table.

    Every ``<td class="no">P0-01</td>`` row is read with its body so the
    ``chip done`` badge can be found without depending on where in the row
    the author put it.
    """
    path = root / PANORAMA
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    return {item: DONE_MARKER in body for item, body in ROW_RE.findall(text)}


# ---------------------------------------------------------------------------
# Criteria.  Each returns ``(satisfied, detail)``.
# ---------------------------------------------------------------------------


def _p0_03(root):
    """The trusted integration environment is documented end to end."""
    path = root / INTEGRATION_ENV
    if not path.is_file():
        return False, "%s is missing" % INTEGRATION_ENV
    text = path.read_text(encoding="utf-8")
    needed = {
        "credential injection": "TENCENTCLOUD_SECRET_ID",
        "cleanup backstop": "always()",
        "failure alerting": "failure()",
    }
    missing = [label for label, marker in needed.items() if marker not in text]
    if missing:
        return False, "%s does not document %s" % (INTEGRATION_ENV, ", ".join(missing))
    return True, "credentials, cleanup sweeper and failure alerting all documented"


def _p0_09(root):
    """No module test file is a shallow smoke test under 80 lines."""
    files = sorted((root / MODULE_TEST_DIR).rglob("test_*.py"))
    if not files:
        return False, "no module test files found under %s" % MODULE_TEST_DIR
    shallow = [(len(f.read_text(encoding="utf-8").splitlines()), f.name) for f in files]
    shallow = [item for item in shallow if item[0] < 80]
    if shallow:
        return False, "%d module test file(s) under 80 lines: %s" % (
            len(shallow),
            ", ".join("%s (%d)" % (name, lines) for lines, name in sorted(shallow)[:5]),
        )
    return True, "%d module test files, none under 80 lines" % len(files)


def _p0_10(root):
    """Every ``tc_*`` role has task-level assertions in at least 3 families."""
    files = sorted((root / ROLE_TEST_DIR).glob("test_*.py"))
    if not files:
        return False, "no role tests found under %s" % ROLE_TEST_DIR
    covered = set()
    families = set()
    for index, path in enumerate(files):
        module = _load(root, "%s/%s" % (ROLE_TEST_DIR, path.name), "_roadmap_%d" % index)
        for role in module._iter_roles():
            covered.add(role.name)
        families.update(
            name for name in vars(module) if name.startswith("_check_")
        )
    roles = {p.name for p in _role_dirs(root)}
    problems = []
    if len(families) < 3:
        problems.append("only %d assertion families (need 3): %s" % (
            len(families), ", ".join(sorted(families)) or "none"))
    gap = sorted(roles - covered)
    if gap:
        problems.append("%d role(s) not covered: %s" % (len(gap), ", ".join(gap[:5])))
    if problems:
        return False, "; ".join(problems)
    return True, "%d roles x %d assertion families" % (len(roles), len(families))


def _p0_11(root):
    """Every write module is contract-tested or carries a written exception."""
    _all, write = _module_names(root)
    path = root / CONTRACT_TEST
    if not path.is_file():
        return False, "%s is missing" % CONTRACT_TEST
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    exercised = {
        node.name[len("test_"):]
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    excepted = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "NO_API3_CONTRACT"
            for target in node.targets
        ):
            excepted.update(
                key.value for key in node.value.keys if isinstance(key, ast.Constant)
            )
    missing = sorted(set(write) - exercised - excepted)
    if missing:
        return False, "%d write module(s) with neither a contract case nor an exception: %s" % (
            len(missing), ", ".join(missing[:5]))
    counter = sum(1 for name in write if name in exercised)
    return True, "%d/%d exercised, %d excepted (no API 3.0 request model)" % (
        counter, len(write), sum(1 for name in write if name in excepted))


def _p0_12(root):
    """The companion docs quote the current module count, not a stale one."""
    names, _write = _module_names(root)
    total = len(names)
    problems = []
    for relative in COMPANION_DOCS:
        path = root / relative
        if not path.is_file():
            problems.append("%s is missing" % relative)
            continue
        numbers = _numbers(path.read_text(encoding="utf-8"))
        if total not in numbers:
            problems.append("%s never states the module count %d" % (relative, total))
    if problems:
        return False, "; ".join(problems)
    return True, "all %d companion docs state %d modules" % (len(COMPANION_DOCS), total)


def _p1_07(root):
    """The module_utils README documents every helper and the dependency direction."""
    path = root / MODULE_UTILS_README
    if not path.is_file():
        return False, "%s is missing" % MODULE_UTILS_README
    text = path.read_text(encoding="utf-8")
    if "## Dependency direction" not in text:
        return False, "%s has no dependency-direction section" % MODULE_UTILS_README
    helpers = sorted(
        p.name for p in (root / "plugins/module_utils").glob("*.py")
        if not p.name.startswith("__")
    )
    undocumented = [name for name in helpers if "`%s`" % name not in text]
    if undocumented:
        return False, "%s omits %d helper(s): %s" % (
            MODULE_UTILS_README, len(undocumented), ", ".join(undocumented[:5]))
    return True, "%d helpers documented with a dependency direction" % len(helpers)


def _p1_09(root):
    """Every module has an FQCN row in the README index."""
    path = root / README
    if not path.is_file():
        return False, "%s is missing" % README
    names, _write = _module_names(root)
    indexed = set(FQCN_ROW_RE.findall(path.read_text(encoding="utf-8")))
    missing = sorted(set(names) - indexed)
    if missing:
        return False, "%d module(s) missing from the README index: %s" % (
            len(missing), ", ".join(missing[:5]))
    return True, "%d FQCN rows, one per module" % len(indexed & set(names))


def _p1_10(root):
    """Five or more example playbooks, all passing the example checker."""
    checker = _load(root, EXAMPLES_CHECKER, "_roadmap_examples")
    problems, inventories = checker.check()
    if len(inventories) < 5:
        return False, "only %d example playbook(s) discovered (need 5)" % len(inventories)
    if problems:
        return False, "%d example problem(s): %s" % (len(problems), str(problems[0])[:120])
    return True, "%d example playbooks, checker clean" % len(inventories)


def _p2_03(root):
    """CONTRIBUTING spells out the co-maintainer path."""
    path = root / CONTRIBUTING
    if not path.is_file():
        return False, "%s is missing" % CONTRIBUTING
    text = path.read_text(encoding="utf-8")
    needed = {
        "permission boundaries": "co-maintainer",
        "expected commitment": "Expected commitment",
        "how to join": "How to join",
    }
    missing = [label for label, marker in needed.items() if marker not in text]
    if missing:
        return False, "%s does not document %s" % (CONTRIBUTING, ", ".join(missing))
    return True, "role matrix, expected commitment and joining steps documented"


def _p2_05(root):
    """Triage is automated (a workflow reacts to new items) and the SLA is written."""
    path = root / TRIAGE
    if not path.is_file():
        return False, "%s is missing" % TRIAGE
    workflows = sorted((root / WORKFLOWS_DIR).glob("*.yml"))
    automated = False
    for workflow in workflows:
        try:
            data = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        triggers = data.get(True) or data.get("on") or {}
        if isinstance(triggers, dict) and "issues" in triggers:
            automated = True
            break
    if not automated:
        return False, "no workflow triggers on issues; new items are labelled by hand only"
    text = path.read_text(encoding="utf-8")
    if "48" not in text:
        return False, "%s states no first-response SLA" % TRIAGE
    return True, "issue workflow present and %s states the SLA" % TRIAGE


def _p2_06(root):
    """A demo/adoption page exists and the README links to it."""
    candidates = sorted((root / "docs").glob("demo*.html"))
    if not candidates:
        return False, "no docs/demo*.html page"
    readme = root / README
    linked = readme.is_file() and any(
        candidate.name in readme.read_text(encoding="utf-8") for candidate in candidates
    )
    if not linked:
        return False, "%s exists but %s does not link it" % (candidates[0].name, README)
    return True, "%s linked from README" % candidates[0].name


def _p2_07(root):
    """The porting guide maps every released version."""
    changelog = root / CHANGELOG
    if not changelog.is_file():
        return False, "%s is missing" % CHANGELOG
    releases = (yaml.safe_load(changelog.read_text(encoding="utf-8")) or {}).get("releases") or {}
    if not releases:
        return False, "%s lists no releases" % CHANGELOG
    path = root / PORTING
    if not path.is_file():
        return False, "%s is missing" % PORTING
    text = path.read_text(encoding="utf-8")
    missing = [version for version in releases if "`%s`" % version not in text]
    if missing:
        return False, "%s maps %d of %d releases; missing %s" % (
            PORTING, len(releases) - len(missing), len(releases), ", ".join(sorted(missing)[:5]))
    return True, "all %d releases mapped in %s" % (len(releases), PORTING)


NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text):
    """Whole numbers appearing in *text*, so ``55`` does not match ``1557``."""
    found = set()
    for token in NUMBER_RE.findall(text):
        value = token.replace(",", "").rstrip(".")
        if value.isdigit():
            found.add(int(value))
    return found


CRITERIA = {
    "P0-03": _p0_03,
    "P0-09": _p0_09,
    "P0-10": _p0_10,
    "P0-11": _p0_11,
    "P0-12": _p0_12,
    "P1-07": _p1_07,
    "P1-09": _p1_09,
    "P1-10": _p1_10,
    "P2-03": _p2_03,
    "P2-05": _p2_05,
    "P2-06": _p2_06,
    "P2-07": _p2_07,
}

TITLES = {
    "P0-03": "trusted integration environment documented",
    "P0-09": "no shallow (<80 line) module tests",
    "P0-10": "task-level tests for every role",
    "P0-11": "contract coverage for every write module",
    "P0-12": "companion docs on current figures",
    "P1-07": "module_utils README + dependency direction",
    "P1-09": "README module index with FQCN",
    "P1-10": "end-to-end example playbooks",
    "P2-03": "co-maintainer joining path",
    "P2-05": "triage SLA + label automation",
    "P2-06": "adoption / demo page",
    "P2-07": "changelog version mapping + porting guide",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def measure(root=REPO_ROOT):
    """Return ``{item_id: (satisfied, detail)}`` for every mechanical criterion."""
    return {item: probe(root) for item, probe in CRITERIA.items()}


def validate(root=REPO_ROOT):
    """Compare measured criteria with the panorama's badges, both directions."""
    problems = []
    marked = parse_panorama(root)
    if not marked:
        return ["no priority rows found in %s -- the panorama table changed shape" % PANORAMA]

    unknown = sorted(set(CRITERIA) - set(marked))
    if unknown:
        problems.append("criteria with no row in %s: %s" % (PANORAMA, ", ".join(unknown)))

    measured = measure(root)
    for item in sorted(CRITERIA):
        satisfied, detail = measured[item]
        if marked.get(item) and not satisfied:
            problems.append("%s is marked done but fails its acceptance: %s" % (item, detail))
        elif satisfied and not marked.get(item):
            problems.append("%s meets its acceptance but is not marked done (%s)" % (item, detail))
    return problems


def report(root=REPO_ROOT):
    """Render the measured state of every criterion."""
    marked = parse_panorama(root)
    measured = measure(root)
    lines = ["roadmap status -- %d measurable of %d rows" % (len(CRITERIA), len(marked))]
    for item in sorted(CRITERIA):
        satisfied, detail = measured[item]
        state = "PASS" if satisfied else "FAIL"
        badge = "done" if marked.get(item) else "open"
        agree = "ok" if satisfied == bool(marked.get(item)) else "MISMATCH"
        lines.append("  %-6s %-4s badge=%-4s %-8s %-44s %s" % (
            item, state, badge, agree, TITLES.get(item, ""), detail))
    unmeasured = sorted(set(marked) - set(CRITERIA))
    if unmeasured:
        lines.append("  not mechanically measurable: %s" % ", ".join(unmeasured))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero when a badge disagrees with its acceptance")
    args = parser.parse_args(argv)
    print(report())
    if not args.check:
        return 0
    problems = validate()
    if not problems:
        print("\nroadmap status: ok")
        return 0
    print("\nroadmap status: %d problem(s)" % len(problems))
    for problem in problems:
        print("  - %s" % problem)
    return 1


if __name__ == "__main__":
    sys.exit(main())
