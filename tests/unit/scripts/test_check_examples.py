# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_examples.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check_examples():
    return _load_script()


@pytest.fixture
def tree(tmp_path, check_examples):
    """Point the script's lookup dirs at a throwaway repository layout."""
    saved = (check_examples.MODULES_DIR, check_examples.ROLES_DIR,
             check_examples.DOC_FRAGMENTS_DIR, check_examples.TARGETS_DIR)
    modules = tmp_path / "plugins" / "modules"
    roles = tmp_path / "roles"
    fragments = tmp_path / "plugins" / "doc_fragments"
    for directory in (modules, roles, fragments):
        directory.mkdir(parents=True)
    check_examples.MODULES_DIR = modules
    check_examples.ROLES_DIR = roles
    check_examples.DOC_FRAGMENTS_DIR = fragments
    # The integration targets are checked by the same run; a fixture that
    # redirects the module tree has to redirect them too, or the real targets
    # are measured against a module directory that holds one fake module.
    check_examples.TARGETS_DIR = tmp_path / "tests" / "integration" / "targets"
    yield tmp_path
    (check_examples.MODULES_DIR, check_examples.ROLES_DIR,
     check_examples.DOC_FRAGMENTS_DIR, check_examples.TARGETS_DIR) = saved


def write_module(tree, name, options=(), fragments=()):
    """Create a module whose DOCUMENTATION declares ``options``."""
    lines = ["DOCUMENTATION = r'''", "module: %s" % name, "options:"]
    for option in options:
        lines += ["  %s:" % option, "    description: x", "    type: str"]
    if fragments:
        lines.append("extends_documentation_fragment:")
        for fragment in fragments:
            lines.append("  - susunola.tencentcloud.%s" % fragment)
    lines += ["author: test", "'''", ""]
    (tree / "plugins" / "modules" / (name + ".py")).write_text("\n".join(lines))


def write_fragment(tree, name, options=()):
    lines = ["class ModuleDocFragment(object):", "    DOCUMENTATION = r'''", "options:"]
    for option in options:
        lines += ["      %s:" % option, "        description: x", "        type: str"]
    lines += ["'''", ""]
    (tree / "plugins" / "doc_fragments" / (name + ".py")).write_text("\n".join(lines))


def write_role(tree, name, variables=()):
    role = tree / "roles" / name / "defaults"
    role.mkdir(parents=True)
    (role / "main.yml").write_text("\n".join(
        ["---"] + ["%s: \"\"" % variable for variable in variables] + [""]))


def write_playbook(tree, body, name="pb.yml"):
    path = tree / name
    path.write_text(body)
    return path


def kinds(problems):
    return {kind for kind, detail in problems}


def write_target(tree, body, name="vpc"):
    """Create an integration target task file in the throwaway tree."""
    path = tree / "tests" / "integration" / "targets" / name / "tasks" / "main.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def example_root(tree):
    """A playbook directory inside the fixture, so a target test does not also
    scan the real docs/examples against the fixture's module tree."""
    directory = tree / "examples"
    directory.mkdir(exist_ok=True)
    write_playbook(directory, "---\n- name: demo\n  hosts: localhost\n  tasks: []\n")
    return [str(directory)]


# --------------------------------------------------------------------------
# integration targets
# --------------------------------------------------------------------------

def test_a_target_calling_a_missing_module_is_reported(tree, check_examples):
    """A target runs only in the credentialed weekly job, so a renamed module
    would be found by a real run against a real account."""
    write_target(tree, """---
- name: Create a network
  susunola.tencentcloud.ghost_vpc:
    name: demo
""")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert any("ghost_vpc" in detail for _kind, detail in problems)


def test_a_target_passing_an_undeclared_option_is_reported(tree, check_examples):
    write_module(tree, "vpc", options=["name"])
    write_target(tree, """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: demo
    nam: typo
""")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert any("nam" in detail and "does not declare" in detail for _kind, detail in problems)


def test_a_target_reading_an_undefined_variable_is_reported(tree, check_examples):
    write_module(tree, "vpc", options=["name"])
    write_target(tree, """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ ghost_name }}"
""")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert any("ghost_name" in detail for _kind, detail in problems)


def test_a_target_variable_declared_on_the_task_is_defined(tree, check_examples):
    """The targets build a payload in a task's own vars: block and compare
    against it later, so a task's vars count as defined names."""
    write_module(tree, "vpc", options=["name"])
    write_target(tree, """---
- name: Create a network
  vars:
    vpc_name: demo
  susunola.tencentcloud.vpc:
    name: "{{ vpc_name }}"

- name: Read it back
  susunola.tencentcloud.vpc:
    name: "{{ vpc_name }}"
""")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert problems == [], problems


def test_a_target_variable_declared_in_vars_main_is_defined(tree, check_examples):
    """A target's inputs are materialised in its own vars/main.yml."""
    write_module(tree, "vpc", options=["name"])
    write_target(tree, """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ vpc_name }}"
""")
    (tree / "tests" / "integration" / "targets" / "vpc" / "vars").mkdir(parents=True)
    (tree / "tests" / "integration" / "targets" / "vpc" / "vars" / "main.yml").write_text(
        "---\nvpc_name: demo\n", encoding="utf-8")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert problems == [], problems


def test_a_jinja_test_is_not_a_variable(tree, check_examples):
    """``x is failed`` reads a test, not a variable named failed."""
    write_module(tree, "vpc", options=["name"])
    write_target(tree, """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: demo
  register: created

- name: Check it
  ansible.builtin.assert:
    that:
      - created is changed
      - created is not failed
""")
    problems, _inventories = check_examples.check(
        roots=example_root(tree), targets=True, roles=False)
    assert problems == [], problems


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_examples_pass_the_check(check_examples):
    """The shipped examples and integration targets must be clean; this is
    what CI asserts."""
    problems, inventories = check_examples.check()
    assert problems == [], problems
    assert len(inventories) == (11 + len(check_examples.discover_targets())
                                + len(check_examples.discover_role_tasks()))
    assert any("06_full_chain" in item["path"] for item in inventories)
    assert any("tests/integration/targets/vpc" in item["path"] for item in inventories)


def test_main_check_exits_zero_on_the_real_tree(check_examples):
    assert check_examples.main(["--check"]) == 0


def test_json_inventory_is_serialisable(check_examples, capsys):
    assert check_examples.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and payload
    for item in payload:
        assert isinstance(item["modules"], list)
        assert isinstance(item["roles"], list)


# --------------------------------------------------------------------------
# expression parsing
# --------------------------------------------------------------------------

def test_expression_names_ignores_filters_and_attributes(check_examples):
    names = check_examples.expression_names("running.instances | length")
    assert names == {"running"}
    assert check_examples.expression_names("demo_tags | susunola.tencentcloud.tag_merge({'a': 1})") == {"demo_tags"}


def test_expression_names_strips_defined_guards(check_examples):
    """'x is defined' guards x; the word 'defined' is not a variable."""
    names = check_examples.expression_names("demo_eip_id is defined and demo_eip_id | length > 0")
    assert names == {"demo_eip_id"}


# --------------------------------------------------------------------------
# metadata lookups
# --------------------------------------------------------------------------

def test_module_options_includes_doc_fragments(tree, check_examples):
    write_fragment(tree, "region", ["region"])
    write_module(tree, "vpc", ["name"], fragments=["region"])
    assert check_examples.module_options("vpc", {}) == {"name", "region"}


def test_module_options_is_empty_for_an_unknown_module(tree, check_examples):
    assert check_examples.module_options("nope", {}) == set()


def test_role_default_vars_reads_defaults(tree, check_examples):
    write_role(tree, "tc_demo", ["tc_demo_name", "tc_demo_region"])
    assert check_examples.role_default_vars("tc_demo", {}) == {"tc_demo_name", "tc_demo_region"}


# --------------------------------------------------------------------------
# per-playbook checks
# --------------------------------------------------------------------------

def test_role_published_names_includes_facts_and_registers(tree, check_examples):
    """Both set_fact and register outlive the role and reach later plays."""
    tasks = tree / "roles" / "tc_demo" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "main.yml").write_text("""---
- name: create
  susunola.tencentcloud.vpc:
    name: web
  register: tc_demo_result

- name: publish
  ansible.builtin.set_fact:
    tc_demo_summary:
      id: "{{ tc_demo_result.vpc.VpcId }}"
""")
    assert check_examples.role_published_names("tc_demo", {}) == {"tc_demo_result", "tc_demo_summary"}


def test_role_result_handoff_passes(tree, check_examples):
    """Stage two may read what stage one's role published."""
    tasks = tree / "roles" / "tc_demo" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "main.yml").write_text("""---
- name: publish
  ansible.builtin.set_fact:
    tc_demo_result:
      vpc_id: vpc-1
""")
    (tree / "roles" / "tc_demo" / "defaults").mkdir(parents=True)
    (tree / "roles" / "tc_demo" / "defaults" / "main.yml").write_text("---\ntc_demo_name: \"\"\n")
    write_fragment(tree, "region", ["region"])
    write_module(tree, "vpc", ["name"], fragments=["region"])
    path = write_playbook(tree, """---
- name: stage one
  hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_demo
      vars:
        tc_demo_name: demo

- name: stage two
  hosts: localhost
  tasks:
    - name: use the published id
      susunola.tencentcloud.vpc:
        name: "{{ tc_demo_result.vpc_id }}"
""")
    problems, inventory = check_examples.check_playbook(path)
    assert problems == [], problems
    assert inventory["plays"] == 2


def test_unknown_module_is_reported(tree, check_examples):
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: call a module that does not ship
      susunola.tencentcloud.ghost_module:
        name: x
""")
    problems, inventory = check_examples.check_playbook(path)
    assert "modules" in kinds(problems)
    # The inventory records what the playbook asks for, resolved or not.
    assert inventory["modules"] == {"ghost_module"}


def test_undeclared_option_is_reported(tree, check_examples):
    write_fragment(tree, "region", ["region"])
    write_module(tree, "security_group", ["name", "region"], fragments=["region"])
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: pass an option the module does not declare
      susunola.tencentcloud.security_group:
        region: ap-guangzhou
        name: demo-sg
        renamed_option: true
""")
    problems, inventory = check_examples.check_playbook(path)
    assert "options" in kinds(problems)
    assert inventory["modules"] == {"security_group"}


def test_declared_options_pass(tree, check_examples):
    write_fragment(tree, "region", ["region"])
    write_module(tree, "security_group", ["name"], fragments=["region"])
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: region comes from a doc fragment, not the module itself
      susunola.tencentcloud.security_group:
        region: ap-guangzhou
        name: demo-sg
      register: sg
""")
    problems, inventory = check_examples.check_playbook(path)
    assert problems == [], problems
    assert inventory["modules"] == {"security_group"}


def test_unknown_role_is_reported(tree, check_examples):
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_missing
""")
    problems, inventory = check_examples.check_playbook(path)
    assert "roles" in kinds(problems)
    assert inventory["roles"] == {"tc_missing"}


def test_role_variable_must_be_declared(tree, check_examples):
    write_role(tree, "tc_demo", ["tc_demo_name"])
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  roles:
    - role: susunola.tencentcloud.tc_demo
      vars:
        tc_demo_name: ok
        tc_demo_renamed: wrong
""")
    problems, inventory = check_examples.check_playbook(path)
    assert "role-vars" in kinds(problems)
    assert inventory["roles"] == {"tc_demo"}


def test_undefined_variable_is_reported(tree, check_examples):
    write_fragment(tree, "region", ["region"])
    write_module(tree, "vpc", ["name"], fragments=["region"])
    path = write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: read a variable nobody declares
      susunola.tencentcloud.vpc:
        name: "{{ missing_name }}"
""")
    problems, inventory = check_examples.check_playbook(path)
    assert "vars" in kinds(problems)


@pytest.mark.parametrize("body", [
    """---
- name: demo
  hosts: localhost
  vars:
    declared_name: ok
  tasks:
    - name: declared in the play
      susunola.tencentcloud.vpc:
        name: "{{ declared_name }}"
""",
    """---
- name: demo
  hosts: localhost
  tasks:
    - name: registered earlier
      susunola.tencentcloud.vpc:
        name: web
      register: created
    - name: read the registration
      ansible.builtin.debug:
        msg: "{{ created.vpc.VpcId }}"
""",
    """---
# Run with:  ansible-playbook pb.yml -e passed_name=vpc-1
- name: demo
  hosts: localhost
  tasks:
    - name: documented as an extra var
      susunola.tencentcloud.vpc:
        name: "{{ passed_name }}"
""",
    """---
- name: demo
  hosts: localhost
  tasks:
    - name: guarded, so it may be absent
      susunola.tencentcloud.vpc:
        name: "{{ optional_name | default('web') }}"
      when: optional_name is defined
""",
    """---
- name: demo
  hosts: localhost
  tasks:
    - name: the collection's own env-var convention
      susunola.tencentcloud.vpc:
        region: "{{ tencentcloud_region | default('ap-guangzhou') }}"
        name: web
""",
])
def test_reachable_variables_pass(tree, check_examples, body):
    write_fragment(tree, "region", ["region"])
    write_module(tree, "vpc", ["name"], fragments=["region"])
    problems, inventory = check_examples.check_playbook(write_playbook(tree, body))
    assert problems == [], problems


def test_broken_yaml_is_reported(tree, check_examples):
    path = write_playbook(tree, "---\n- name: demo\n  hosts: localhost\n  tasks: [\n")
    problems, inventory = check_examples.check_playbook(path)
    assert "yaml" in kinds(problems)
    assert inventory["plays"] == 0


def test_not_a_play_list_is_reported(tree, check_examples):
    path = write_playbook(tree, "---\njust: a mapping\n")
    problems, inventory = check_examples.check_playbook(path)
    assert "yaml" in kinds(problems)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_main_check_fails_on_problems(tree, check_examples, capsys):
    write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: unknown module
      susunola.tencentcloud.ghost_module:
        name: x
""", name="pb.yml")
    assert check_examples.main(["--check", "--path", str(tree)]) == 1
    assert "ghost_module" in capsys.readouterr().err


def test_main_without_check_prints_the_inventory(tree, check_examples, capsys):
    write_playbook(tree, """---
- name: demo
  hosts: localhost
  tasks:
    - name: nothing to resolve
      ansible.builtin.debug:
        msg: hello
""", name="pb.yml")
    # --no-targets because the fixture has no target tree: an empty one is a
    # discovery problem, which is the point of reporting it in a real run.
    assert check_examples.main(["--path", str(tree), "--no-targets",
                                "--no-roles"]) == 0
    assert "1 example playbook(s)" in capsys.readouterr().out


def test_main_reports_when_nothing_is_discovered(tmp_path, check_examples):
    assert check_examples.main(["--check", "--path", str(tmp_path / "empty")]) == 1


# --------------------------------------------------------------------------
# role task files
# --------------------------------------------------------------------------

def write_role_task(tree, role, body, name="main.yml"):
    """Create a role task file in the throwaway tree."""
    path = tree / "roles" / role / "tasks" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_a_role_task_calling_a_missing_module_is_reported(tree, check_examples):
    """A role only ever runs in a real account, so nothing else would notice.

    The 68 roles are the one place a module reference went unchecked: the
    example playbooks and the integration targets are validated, a role's
    tasks were not, and no test executes them.
    """
    write_module(tree, "vpc", options=["name"])
    write_role(tree, "tc_demo", variables=["tc_demo_name"])
    write_role_task(tree, "tc_demo", """---
- name: Create a network
  susunola.tencentcloud.vpc_nonexistent:
    name: "{{ tc_demo_name }}"
""")
    problems, _inventories = check_examples.check(roots=example_root(tree), targets=False)
    assert "modules" in kinds(problems)
    assert any("vpc_nonexistent" in detail for detail in
               [detail for _kind, detail in problems])


def test_a_role_task_passing_an_undeclared_option_is_reported(tree, check_examples):
    write_module(tree, "vpc", options=["name"])
    write_role(tree, "tc_demo", variables=["tc_demo_name"])
    write_role_task(tree, "tc_demo", """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ tc_demo_name }}"
    bogus_option: 1
""")
    problems, _inventories = check_examples.check(roots=example_root(tree), targets=False)
    assert "options" in kinds(problems)


def test_a_role_task_reading_an_undefined_variable_is_reported(tree, check_examples):
    write_module(tree, "vpc", options=["name"])
    write_role(tree, "tc_demo", variables=["tc_demo_name"])
    write_role_task(tree, "tc_demo", """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ tc_demo_missing }}"
""")
    problems, _inventories = check_examples.check(roots=example_root(tree), targets=False)
    assert "vars" in kinds(problems)


def test_a_role_task_variable_from_a_sibling_file_is_defined(tree, check_examples):
    """A role's files include each other, so one scope covers the role."""
    write_module(tree, "vpc", options=["name"])
    write_role(tree, "tc_demo")
    write_role_task(tree, "tc_demo", """---
- name: Publish the name
  ansible.builtin.set_fact:
    tc_demo_name: demo
""", name="prepare.yml")
    write_role_task(tree, "tc_demo", """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ tc_demo_name }}"
""", name="main.yml")
    problems, _inventories = check_examples.check(roots=example_root(tree), targets=False)
    assert problems == []


def test_a_role_custom_loop_var_from_a_sibling_file_is_defined(tree, check_examples):
    """``loop_control.loop_var`` is how a role includes a file per item."""
    write_module(tree, "vpc", options=["name"])
    write_role(tree, "tc_demo")
    write_role_task(tree, "tc_demo", """---
- name: Create each network
  ansible.builtin.include_tasks: create.yml
  loop:
    - demo
  loop_control:
    loop_var: tc_demo_network
""", name="main.yml")
    write_role_task(tree, "tc_demo", """---
- name: Create a network
  susunola.tencentcloud.vpc:
    name: "{{ tc_demo_network }}"
""", name="create.yml")
    problems, _inventories = check_examples.check(roots=example_root(tree), targets=False)
    assert problems == []


def test_a_lookup_call_is_not_a_variable_read(check_examples):
    """``lookup('...', resource_type='vpc')`` reads no variable.

    The name of the function and the name of a keyword argument are not
    variables, and the roles use both on every resolve-by-name step.
    """
    names = check_examples.expression_names(
        "lookup('susunola.tencentcloud.resource_id', tc_demo_name, "
        "resource_type='vpc', region=tc_demo_region)")
    assert names == {"tc_demo_name", "tc_demo_region"}


def test_committed_role_tasks_pass_the_check(check_examples):
    """The repository's own roles must pass, not just the fixture's."""
    problems, _inventories = check_examples.check(targets=False)
    assert problems == []
