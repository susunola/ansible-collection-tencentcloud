"""Map changed collection files to real-cloud integration targets."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "tests" / "integration" / "coverage.yml"


def changed_files(base, head):
    result = subprocess.run(["git", "diff", "--name-only", base, head], cwd=ROOT, check=True, text=True, capture_output=True)
    return set(result.stdout.splitlines())


def select(files, coverage):
    selected = set()
    modules = {Path(name).stem for name in files if name.startswith("plugins/modules/") and name.endswith(".py")}
    for target, config in coverage["targets"].items():
        if modules.intersection(config.get("modules", [])):
            selected.add(target)
    if any(name.startswith(("plugins/module_utils/", "tests/integration/", ".github/workflows/integration")) for name in files):
        selected.update(name for name, cfg in coverage["targets"].items() if cfg.get("cost") in ("free", "low"))
    return sorted(selected)


def validate_registry(coverage):
    """Return actionable registry problems instead of silently skipping E2E."""
    problems = []
    seen = {}
    valid_costs = {"free", "low", "medium", "high"}
    for target, config in coverage.get("targets", {}).items():
        target_dir = ROOT / "tests" / "integration" / "targets" / target
        if not (target_dir / "tasks" / "main.yml").exists():
            problems.append("target %s has no tasks/main.yml" % target)
        if config.get("cost") not in valid_costs:
            problems.append("target %s has invalid cost" % target)
        for module in config.get("modules", []):
            if not (ROOT / "plugins" / "modules" / (module + ".py")).exists():
                problems.append("target %s references missing module %s" % (target, module))
            if module in seen:
                problems.append("module %s is mapped by both %s and %s" % (module, seen[module], target))
            seen[module] = target
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="HEAD^", help="Git base revision")
    parser.add_argument("--head", default="HEAD", help="Git head revision")
    parser.add_argument("--files", nargs="*", help="Use an explicit changed-file list")
    parser.add_argument("--check", action="store_true", help="Validate target, cost and module mappings")
    args = parser.parse_args(argv)
    coverage = yaml.safe_load(MAP.read_text(encoding="utf-8"))
    if args.check:
        problems = validate_registry(coverage)
        if problems:
            for problem in problems:
                print(problem)
            return 1
    targets = select(set(args.files) if args.files is not None else changed_files(args.base, args.head), coverage)
    print(" ".join(targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
