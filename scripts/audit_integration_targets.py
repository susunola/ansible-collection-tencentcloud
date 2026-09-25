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


# ansible-test rebuilds the environment before it spawns ansible-playbook, so
# a gate only reaches a target if it was exported on the "Materialise
# integration inputs" step. The run step's own env is too late - and it is
# where every gate used to live, which made every gated target self-skip.
_INPUTS_STEP = "Materialise integration inputs for ansible-test"
_RUN_STEP = "Run integration tests"
# The key pair travels in the TCCLI profile instead (and is masked anyway).
_INPUT_PARITY_EXEMPT = frozenset({"TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"})


def audit_workflow_input_parity(root: Path | None = None) -> list[str]:
    """Flag a per-target gate exported on the run step but not on the inputs step."""
    root = root or ROOT
    path = root / ".github/workflows/integration.yml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - reported by the parse check
        return [f"{path}: YAML error: {exc}"]
    found: dict[str, set] = {}
    for job in (data.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if isinstance(step, dict) and step.get("name") in (_INPUTS_STEP, _RUN_STEP):
                found[step["name"]] = set(step.get("env") or {})
    inputs_env = found.get(_INPUTS_STEP)
    run_env = found.get(_RUN_STEP)
    if inputs_env is None or run_env is None:
        return []
    missing = sorted((run_env - _INPUT_PARITY_EXEMPT) - inputs_env)
    if not missing:
        return []
    return [
        f"{path}: {' '.join(missing)} is exported on the '{_RUN_STEP}' step but not on "
        f"the '{_INPUTS_STEP}' step - ansible-test strips it before the playbook runs, "
        "so the gated target silently self-skips"
    ]


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
    errors.extend(audit_teardowns())
    errors.extend(audit_check_mode())
    errors.extend(audit_lazy_random_names())
    errors.extend(audit_registry_claims())
    errors.extend(audit_workflow_targets())
    errors.extend(audit_workflow_input_parity())
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
        "no bare or malformed conditionals; dispatch default matches the run fallback; "
        "per-target gates are exported where ansible-test can still see them; "
        "every target that creates a resource tears it down in an 'always' block "
        "and predicts the change in check mode"
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


def audit_teardowns(root: Path | None = None) -> list[str]:
    """Targets that create a resource and never delete it in an ``always`` block.

    Every target here provisions something in a real Tencent Cloud account.
    Thirty-two of the thirty-three ended with a delete in an ``always`` block,
    so a failure half way through left the account as it found it; the
    thirty-third deleted on the success path only, which is exactly the run
    that failed. The check is deliberately about the *block structure* and not
    about a deletion somewhere in the file: a delete that the failing task
    never reaches is not a teardown.
    """
    root = root or ROOT
    problems: list[str] = []
    for path in sorted((root / "tests/integration/targets").glob("*/tasks/main.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - reported by the parse check
            continue
        if not _creates_a_resource(data):
            continue
        if _deletes_in_always(data):
            continue
        problems.append(
            "%s: creates a resource but deletes it outside an 'always' block, so a "
            "failure mid-run leaves it behind" % path)
    return problems


def _creates_a_resource(data) -> bool:
    """True when the target asks a module for ``state: present``."""
    for task in walk_tasks(data):
        if isinstance(task, dict):
            for key, value in task.items():
                if isinstance(value, dict) and value.get("state") == "present":
                    return True
    return False


def _deletes_in_always(data) -> bool:
    """True when an ``always`` block asks a module for ``state: absent``."""
    for node in data if isinstance(data, list) else [data]:
        if not isinstance(node, dict):
            continue
        for task in walk_tasks(node.get("always") or []):
            if not isinstance(task, dict):
                continue
            for value in task.values():
                if isinstance(value, dict) and value.get("state") == "absent":
                    return True
    return False


def _all_mappings(node):
    """Yield every mapping in a parsed task document, at any depth."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _all_mappings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_mappings(item)


def audit_lazy_random_names(root: Path | None = None) -> list[str]:
    """Targets that give a resource a ``| random`` name they never freeze.

    A ``vars:`` block on a task is templated lazily, so ``name:
    "ansible-it-{{ 99999999 | random }}"`` is re-rolled on every reference: the
    resource is created under one name and deleted under another, which fails
    the run and leaks it. Every target in this repository freezes the name with
    a ``set_fact`` first -- facts outrank play vars -- and this check exists
    because a rewritten target lost its freeze step while gaining an ``always``
    teardown, so the teardown deleted a name that had never been created.

    The document is walked rather than its tasks: the ``vars:`` that matters
    belongs to the task that wraps the ``block``, and the task walker yields
    what is inside a block, not the block's own task.
    """
    root = root or ROOT
    problems: list[str] = []
    for path in sorted((root / "tests/integration/targets").glob("*/tasks/main.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - reported by the parse check
            continue
        mappings = list(_all_mappings(data))
        lazy = False
        for mapping in mappings:
            task_vars = mapping.get("vars")
            if isinstance(task_vars, dict) and any(
                    isinstance(value, str) and "| random" in value for value in task_vars.values()):
                lazy = True
                break
        if not lazy:
            continue
        frozen = any("set_fact" in str(key) for mapping in mappings for key in mapping)
        if frozen:
            continue
        problems.append(
            "%s: gives a resource a '| random' name in a lazy vars: block and never "
            "freezes it with set_fact, so the create and the delete use different "
            "names and the resource leaks" % path)
    return problems


def audit_registry_claims(root: Path | None = None) -> list[str]:
    """Coverage entries claiming a module the target never calls.

    ``tests/integration/coverage.yml`` is what the quality gate counts when it
    reports how many core modules have an integration target, so an entry that
    is not backed by a task is a coverage number that is too good. Three were:
    ``security_group_rule`` belonged to the ``network`` target rather than to
    ``security_group``, and ``network_acl`` and ``clb_rule`` were called by no
    target at all -- the last of which made the real gap one larger than the
    number the repository had been quoting.
    """
    root = root or ROOT
    coverage = root / "tests/integration/coverage.yml"
    try:
        parsed = yaml.safe_load(coverage.read_text(encoding="utf-8")) or {}
        registry = parsed.get("targets") or {}
    except Exception as exc:  # noqa: BLE001
        return ["%s: %s" % (coverage, exc)]
    if not isinstance(registry, dict):
        return ["%s: 'targets' is not a mapping of target to coverage" % coverage]
    problems: list[str] = []
    for target, info in sorted(registry.items()):
        directory = root / "tests/integration/targets" / target
        text = "".join(
            path.read_text(encoding="utf-8")
            for path in sorted(directory.rglob("*.yml"))) if directory.is_dir() else ""
        for module in info.get("modules") or []:
            if ("susunola.tencentcloud.%s:" % module) not in text:
                problems.append(
                    "%s: claims %s, but the target never calls it -- move the entry to "
                    "the target that does, or drop it and let the gap show"
                    % (coverage, module))
    return problems


def audit_check_mode(root: Path | None = None) -> list[str]:
    """Targets that never run a module in check mode.

    Check mode is a headline claim of this collection: every write module
    documents ``check_mode: full`` and each has a unit test that runs it
    against a fake. Twenty-three of the thirty-three targets also ran one
    against the real API, and ten did not -- so for those the claim rested on
    the fake alone. A target that creates something has a state to predict, so
    it is expected to exercise it.
    """
    root = root or ROOT
    problems: list[str] = []
    for path in sorted((root / "tests/integration/targets").glob("*/tasks/main.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - reported by the parse check
            continue
        if not _creates_a_resource(data):
            continue
        if any(task.get("check_mode") in (True, "true", "yes")
               for task in walk_tasks(data) if isinstance(task, dict)):
            continue
        problems.append(
            "%s: creates a resource but never runs a task in check mode, so its "
            "check-mode claim is only tested against a fake" % path)
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
