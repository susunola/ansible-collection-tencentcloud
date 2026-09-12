#!/usr/bin/env python
"""Structural audit for the integration targets (P0-01/02 and friends).

Checks, per tasks/main.yml:
1. YAML parses.
2. Every susunola.tencentcloud.<module> FQCN maps to an existing module in
   plugins/modules/ (or plugins/lookup|connection|... as applicable).
3. Every ``register`` variable referenced in a ``when`` guard with
   ``is defined`` was registered earlier in the same file.
4. meta/main.yml declares the collection and vars/main.yml parses.
5. Across *every* target: no bare ``when: <var>`` / ``when: a and b`` guard.
   ansible-core 2.19 rejects a conditional whose result is a non-boolean
   ("Conditional result (False) was derived from value of type 'str'"), and
   gate variables are strings, so they need an explicit test such as
   ``| length > 0``.
6. The Integration workflow's ``workflow_dispatch`` ``targets`` default names
   the same targets as the inline fallback the scheduled run uses.
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

# A conditional made only of identifiers and and/or/not. Those evaluate to the
# *value* of the last identifier (a string) instead of a boolean.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


# `x | length > 0 | length == 0` - what a careless find/replace leaves behind:
# the second `length` is applied to the boolean the comparison produced and
# the task dies with "object of type 'bool' has no len()".
# A comparison immediately followed by another filter: the operand is the
# boolean the comparison produced, not a collection. The right-hand side is
# restricted to a literal so two legitimate filters in one guard
# (`a | length == 0 or b | length == 0`) are not flagged.
_LENGTH_AFTER_COMPARISON = re.compile(
    r"(?:==|!=|>=|<=|>|<)\s*(?:'[^']*'|\"[^\"]*\"|\d+)\s*\|\s*length\b"
)


def is_bare_conditional(cond: str) -> bool:
    """True when a ``when:`` string can only ever yield a non-boolean."""
    text = re.sub(r"\bnot\b", " ", cond.strip()).replace("(", " ").replace(")", " ").strip()
    if not text:
        return False
    return all(_IDENTIFIER.match(part.strip()) for part in re.split(r"\band\b|\bor\b", text))


def is_malformed_conditional(cond: str) -> bool:
    """True when a ``when:`` chains a filter onto a comparison result."""
    return bool(_LENGTH_AFTER_COMPARISON.search(cond))


# The scheduled run has no ``inputs``, so it falls through to the inline
# fallback list; a manual dispatch uses the input default. They must name the
# same targets - they drifted once already, which left the weekly run
# exercising a different set from the one documented in integration-env.md.
_FALLBACK_TARGETS = re.compile(r"inputs\.targets\s*\|\|\s*'([^']*)'")


def _workflow_trigger(data) -> dict | None:
    """Return the ``on:`` mapping. PyYAML resolves that key to boolean True."""
    if not isinstance(data, dict):
        return None
    for key in (True, "on"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return None


def audit_workflow_targets(root: Path | None = None) -> list[str]:
    """Flag a workflow_dispatch default that drifted from the run fallback."""
    root = root or ROOT
    path = root / ".github/workflows/integration.yml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - reported by the parse check
        return [f"{path}: YAML error: {exc}"]
    trigger = _workflow_trigger(data)
    if trigger is None:
        return []
    inputs = ((trigger.get("workflow_dispatch") or {}).get("inputs") or {})
    default = (inputs.get("targets") or {}).get("default")
    run_step = ""
    for job in (data.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if isinstance(step, dict) and "inputs.targets" in (step.get("run") or ""):
                run_step = step["run"]
    fallback = _FALLBACK_TARGETS.search(run_step)
    if not default or not fallback:
        return []
    if default.split() != fallback.group(1).split():
        return [
            f"{path}: the workflow_dispatch 'targets' default and the scheduled "
            "run's fallback list differ - a manual run would exercise a different "
            "set of targets from the weekly one"
        ]
    return []


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
    errors.extend(audit_conditionals())
    errors.extend(audit_workflow_targets())
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
    print(
        "AUDIT OK: 5 targets x 3 files + coverage.yml + integration.yml parse; "
        "all FQCNs resolve; when-guards reference earlier registers; "
        "no bare or malformed conditionals; dispatch default matches the run fallback"
    )
    return 0


def audit_conditionals(root: Path | None = None) -> list[str]:
    """Flag 'when:' guards that are a bare variable / and-or chain."""
    root = root or ROOT
    problems: list[str] = []
    for path in sorted((root / "tests/integration/targets").glob("*/tasks/main.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - reported by the parse check
            problems.append(f"{path}: YAML error: {exc}")
            continue
        for task in walk_tasks(data):
            when = task.get("when") if isinstance(task, dict) else None
            for cond in when if isinstance(when, list) else [when]:
                if not isinstance(cond, str):
                    continue
                if is_bare_conditional(cond):
                    problems.append(
                        f"{path}: 'when: {cond.strip()}' yields a string, not a boolean - "
                        "add an explicit test (e.g. '| length > 0')"
                    )
                elif is_malformed_conditional(cond):
                    problems.append(
                        f"{path}: 'when: {cond.strip()}' chains a filter onto a comparison "
                        "result - the task fails at runtime with 'object of type X has no len()'"
                    )
    return problems


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
