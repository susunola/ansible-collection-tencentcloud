#!/usr/bin/env python
"""Structural audit for the 5 new flagship integration targets (P0-01/02).

Checks, per tasks/main.yml:
1. YAML parses.
2. Every susunola.tencentcloud.<module> FQCN maps to an existing module in
   plugins/modules/ (or plugins/lookup|connection|... as applicable).
3. Every ``register`` variable referenced in a ``when`` guard with
   ``is defined`` was registered earlier in the same file.
4. meta/main.yml declares the collection and vars/main.yml parses.
Also parses coverage.yml and the integration workflow YAML.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULES = {p.stem for p in (ROOT / "plugins/modules").glob("*.py")}
TARGETS = ["cvm_instance", "vpc", "subnet", "cdb_instance", "tke_cluster"]
errors: list[str] = []


def main() -> int:
    errors.clear()  # main() may run multiple times under pytest.
    for t in TARGETS:
        base = ROOT / "tests/integration/targets" / t
        for rel in ("meta/main.yml", "vars/main.yml", "tasks/main.yml"):
            p = base / rel
            try:
                yaml.safe_load(p.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{p}: YAML error: {exc}")
        audit_tasks(base / "tasks/main.yml")
    # coverage registry + workflow parse
    for p in (ROOT / "tests/integration/coverage.yml", ROOT / ".github/workflows/integration.yml"):
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{p}: YAML error: {exc}")
    if errors:
        print("AUDIT FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("AUDIT OK: 5 targets x 3 files + coverage.yml + integration.yml parse; all FQCNs resolve; when-guards reference earlier registers")
    return 0


def audit_tasks(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    # 2. FQCN existence.
    fqcn = re.findall(r"(?<!group/)susunola\.tencentcloud\.([a-z0-9_]+)", text)
    for name in sorted(set(fqcn)):
        if name not in MODULES:
            errors.append(f"{path}: unknown module susunola.tencentcloud.{name}")
    # 3. register / when-guard ordering (flatten in document order).
    registered: set[str] = set()
    for task in walk_tasks(data):
        if isinstance(task, dict):
            reg = task.get("register")
            if isinstance(reg, str):
                registered.add(reg)
            when = task.get("when")
            for var in guarded_vars(when):
                if var not in registered:
                    errors.append(f"{path}: 'when' references {var} before it is registered")
    # 4. meta declares collection.
    meta = yaml.safe_load((path.parent.parent / "meta/main.yml").read_text(encoding="utf-8"))
    if "susunola.tencentcloud" not in (meta.get("collections") or []):
        errors.append(f"{path.parent.parent}/meta/main.yml: collection not declared")


def walk_tasks(node):
    """Yield tasks from a block/always/tasks list recursively."""
    if isinstance(node, list):
        for item in node:
            yield from walk_tasks(item)
    elif isinstance(node, dict):
        # A real task has a 'name' or a module key at top level.
        if "name" in node and any(k for k in node if "susunola" in k or "ansible." in k):
            yield node
        for key in ("block", "always", "tasks", "rescue"):
            if key in node:
                yield from walk_tasks(node[key])


def guarded_vars(when):
    if when is None:
        return []
    if isinstance(when, list):
        out = []
        for w in when:
            out.extend(guarded_vars(w))
        return out
    if isinstance(when, str):
        # when: X is defined / X.field is defined / not (x is undefined).
        # The base identifier is the registered variable; fields are ignored.
        return [m.group(1) for m in re.finditer(r"\b([a-z_][a-z0-9_]*)(?:\.[A-Za-z0-9_]+)* is (?:not )?defined", when)]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
