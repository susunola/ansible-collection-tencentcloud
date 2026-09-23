"""Regression tests for scripts/audit_integration_targets.py.

The audit script guards the P0-01/02 flagship integration targets (and any
future targets added for the 21 -> 30+ push): YAML must parse, every FQCN
must resolve to a real module, and ``when`` guards may only reference
variables registered earlier in the same task file. These tests pin that
behaviour so a future target batch cannot silently rot the checker itself.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Import the audit script as a module without executing its __main__.
_REPO = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location("audit_integration_targets", _REPO / "scripts" / "audit_integration_targets.py")
_AUDIT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDIT)  # type: ignore[union-attr]

META = "---\ncollections:\n  - susunola.tencentcloud\n"
VARS = "---\ntencentcloud_region: ap-guangzhou\n"


@pytest.fixture()
def target_tree(tmp_path, monkeypatch):
    """A scratch collection root with one fake module, mirroring the audit script's ROOT assumptions."""
    modules = tmp_path / "plugins" / "modules"
    modules.mkdir(parents=True)
    (modules / "demo_thing.py").write_text("", encoding="utf-8")
    (modules / "demo_thing_info.py").write_text("", encoding="utf-8")
    # main() also parses the coverage registry and the integration workflow.
    integ = tmp_path / "tests" / "integration"
    integ.mkdir(parents=True)
    (integ / "coverage.yml").write_text("version: 1\ntargets:\n", encoding="utf-8")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "integration.yml").write_text("name: integration\non: workflow_dispatch\n", encoding="utf-8")
    targets = integ / "targets"
    targets.mkdir()
    monkeypatch.setattr(_AUDIT, "MODULES", {p.stem for p in modules.glob("*.py")})
    monkeypatch.setattr(_AUDIT, "TARGETS", ["demo_thing"])
    monkeypatch.setattr(_AUDIT, "ROOT", tmp_path)
    return tmp_path


def _write_target(root, tasks):
    base = root / "tests" / "integration" / "targets" / "demo_thing"
    (base / "meta").mkdir(parents=True)
    (base / "tasks").mkdir(parents=True)
    (base / "vars").mkdir(parents=True)
    (base / "meta" / "main.yml").write_text(META, encoding="utf-8")
    (base / "vars" / "main.yml").write_text(VARS, encoding="utf-8")
    (base / "tasks" / "main.yml").write_text(tasks, encoding="utf-8")


GOOD_TASKS = """---
- name: Create a demo thing
  susunola.tencentcloud.demo_thing:
    state: present
  register: created

- name: It changed
  ansible.builtin.assert:
    that:
      - created is changed

  always:
    - name: Clean up
      susunola.tencentcloud.demo_thing:
        state: absent
      when: created is defined
"""


def test_well_formed_target_passes(target_tree):
    _write_target(target_tree, GOOD_TASKS)
    assert _AUDIT.main() == 0


def test_unknown_module_fqcn_is_flagged(target_tree):
    bad = GOOD_TASKS.replace("demo_thing:", "no_such_module:")
    _write_target(target_tree, bad)
    assert _AUDIT.main() == 1


def test_guard_before_register_is_flagged(target_tree):
    bad = """---
- name: Clean up before anything was created
  susunola.tencentcloud.demo_thing:
    state: absent
  when: created is defined
"""
    _write_target(target_tree, bad)
    assert _AUDIT.main() == 1


def test_field_guard_uses_base_register(target_tree):
    tasks = GOOD_TASKS.replace("created is defined", "created.thing is defined")
    _write_target(target_tree, tasks)
    assert _AUDIT.main() == 0


def test_group_module_defaults_is_not_an_fqcn(target_tree):
    tasks = GOOD_TASKS.replace(
        "- name: Create a demo thing",
        "- name: Create a demo thing\n  module_defaults:\n    group/susunola.tencentcloud.all:\n      region: ap-guangzhou\n",
    )
    _write_target(target_tree, tasks)
    assert _AUDIT.main() == 0


# ansible-core 2.19 raises "Conditional result (False) was derived from value
# of type 'str'" for a guard that is only identifiers and and/or/not, so the
# audit has to reject them (gate variables are strings).
BARE_GUARDS = [
    "  when: demo_vpc_id\n",
    "  when: not demo_vpc_id\n",
    "  when: demo_vpc_id and demo_subnet_id\n",
    "  when: not (demo_vpc_id and demo_subnet_id)\n",
]
# A filter chained onto the result of a comparison: dies at runtime with
# "object of type 'bool' has no len()".
MALFORMED_GUARDS = [
    "  when: demo_vpc_id | length > 0 | length == 0\n",
    "  when: demo_vpc_id | length > 0 | length > 0\n",
    "  when: demo_count > 0 | length > 0\n",
]
SAFE_GUARDS = [
    "  when: demo_vpc_id | length > 0\n",
    "  when: demo_vpc_id | length == 0 or demo_subnet_id | length == 0\n",
    "  when: created is defined\n",
    "  when: created.thing.PolicyId is defined\n",
    "  when: region == 'ap-guangzhou'\n",
]


@pytest.mark.parametrize("guard", BARE_GUARDS)
def test_bare_conditionals_are_flagged(target_tree, guard):
    _write_target(target_tree, GOOD_TASKS + guard.rstrip("\n").replace("  when:", "- name: Guard\n  ansible.builtin.debug:\n    msg: x\n  when:"))
    problems = _AUDIT.audit_conditionals(target_tree)
    assert len(problems) == 1
    assert _AUDIT.main() == 1


@pytest.mark.parametrize("guard", MALFORMED_GUARDS)
def test_malformed_conditionals_are_flagged(target_tree, guard):
    _write_target(target_tree, GOOD_TASKS + guard.rstrip("\n").replace("  when:", "- name: Guard\n  ansible.builtin.debug:\n    msg: x\n  when:"))
    problems = _AUDIT.audit_conditionals(target_tree)
    assert len(problems) == 1
    assert "comparison" in problems[0]
    assert _AUDIT.main() == 1


@pytest.mark.parametrize("guard", SAFE_GUARDS)
def test_boolean_conditionals_are_accepted(target_tree, guard):
    _write_target(target_tree, GOOD_TASKS + guard.rstrip("\n").replace("  when:", "- name: Guard\n  ansible.builtin.debug:\n    msg: x\n  when:"))
    assert _AUDIT.audit_conditionals(target_tree) == []
    assert _AUDIT.main() == 0


# The scheduled run has no workflow_dispatch inputs, so it uses the inline
# `${{ inputs.targets || '...' }}` fallback; a manual dispatch uses the input
# default. Both must name the same targets.
def _write_workflow(root, default, fallback):
    (root / ".github" / "workflows" / "integration.yml").write_text(
        "name: Integration\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      targets:\n"
        f'        default: "{default}"\n'
        "jobs:\n"
        "  integration:\n"
        "    steps:\n"
        "      - name: Run integration tests\n"
        "        run: >-\n"
        f"          ansible-test integration ${{{{ inputs.targets || '{fallback}' }}}}\n",
        encoding="utf-8",
    )


def test_matching_dispatch_default_and_fallback_pass(target_tree):
    _write_target(target_tree, GOOD_TASKS)
    _write_workflow(target_tree, "vpc subnet", "vpc subnet")
    assert _AUDIT.audit_workflow_targets(target_tree) == []
    assert _AUDIT.main() == 0


def test_drifted_dispatch_default_is_flagged(target_tree):
    # The stale default from commit fd1d754: it had lost the five new targets.
    _write_target(target_tree, GOOD_TASKS)
    _write_workflow(target_tree, "vpc", "vpc subnet")
    problems = _AUDIT.audit_workflow_targets(target_tree)
    assert len(problems) == 1
    assert "fallback" in problems[0]
    assert _AUDIT.main() == 1


def test_workflow_without_a_dispatch_input_passes(target_tree):
    (target_tree / ".github" / "workflows" / "integration.yml").write_text(
        "name: Integration\non:\n  schedule:\n    - cron: '0 2 * * 6'\n",
        encoding="utf-8",
    )
    assert _AUDIT.audit_workflow_targets(target_tree) == []


# ansible-test rebuilds the environment before spawning ansible-playbook, so a
# gate only reaches a target when it is exported on the "Materialise
# integration inputs" step. Before this check existed every gate lived on the
# "Run integration tests" step - too late - and every gated target self-skipped
# while the run still reported success.
def _write_gated_workflow(root, inputs_env, run_env):
    def block(indent, env):
        return "".join(f"{indent}{key}: '{value}'\n" for key, value in env.items())

    (root / ".github" / "workflows" / "integration.yml").write_text(
        "name: Integration\n"
        "on:\n  schedule:\n    - cron: '0 2 * * 6'\n"
        "jobs:\n"
        "  integration:\n"
        "    steps:\n"
        "      - name: Materialise integration inputs for ansible-test\n"
        "        env:\n"
        + block(" " * 10, inputs_env)
        + "        run: python scripts/integration_inputs.py --write\n"
        "      - name: Run integration tests\n"
        "        env:\n"
        + block(" " * 10, run_env)
        + "        run: ansible-test integration vpc\n",
        encoding="utf-8",
    )


def test_gate_exported_on_both_steps_passes(target_tree):
    _write_target(target_tree, GOOD_TASKS)
    _write_gated_workflow(
        target_tree,
        {"TENCENTCLOUD_REGION": "ap-guangzhou", "TENCENTCLOUD_CLS_ALARM_UIN": "abc"},
        {"TENCENTCLOUD_SECRET_ID": "id", "TENCENTCLOUD_CLS_ALARM_UIN": "abc"},
    )
    assert _AUDIT.audit_workflow_input_parity(target_tree) == []
    assert _AUDIT.main() == 0


def test_gate_missing_from_the_inputs_step_is_flagged(target_tree):
    _write_target(target_tree, GOOD_TASKS)
    _write_gated_workflow(
        target_tree,
        {"TENCENTCLOUD_REGION": "ap-guangzhou"},
        {"TENCENTCLOUD_SECRET_ID": "id", "TENCENTCLOUD_CLS_ALARM_UIN": "abc"},
    )
    problems = _AUDIT.audit_workflow_input_parity(target_tree)
    assert len(problems) == 1
    assert "TENCENTCLOUD_CLS_ALARM_UIN" in problems[0]
    assert "self-skips" in problems[0]
    assert _AUDIT.main() == 1


def test_credential_pair_is_exempt_from_input_parity(target_tree):
    # The key pair travels in the TCCLI profile, so it is expected to be
    # missing from the inputs step.
    _write_target(target_tree, GOOD_TASKS)
    _write_gated_workflow(
        target_tree,
        {"TENCENTCLOUD_REGION": "ap-guangzhou"},
        {"TENCENTCLOUD_SECRET_ID": "id", "TENCENTCLOUD_SECRET_KEY": "key"},
    )
    assert _AUDIT.audit_workflow_input_parity(target_tree) == []
