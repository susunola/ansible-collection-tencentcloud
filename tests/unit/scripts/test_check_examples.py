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
             check_examples.DOC_FRAGMENTS_DIR)
    modules = tmp_path / "plugins" / "modules"
    roles = tmp_path / "roles"
    fragments = tmp_path / "plugins" / "doc_fragments"
    for directory in (modules, roles, fragments):
        directory.mkdir(parents=True)
    check_examples.MODULES_DIR = modules
    check_examples.ROLES_DIR = roles
    check_examples.DOC_FRAGMENTS_DIR = fragments
    yield tmp_path
    (check_examples.MODULES_DIR, check_examples.ROLES_DIR,
     check_examples.DOC_FRAGMENTS_DIR) = saved


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


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_examples_pass_the_check(check_examples):
    """The shipped examples must be clean; this is what CI asserts."""
    problems, inventories = check_examples.check()
    assert problems == [], problems
    assert len(inventories) == 11
    assert any("06_full_chain" in item["path"] for item in inventories)


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
    assert check_examples.main(["--path", str(tree)]) == 0
    assert "1 example playbook(s)" in capsys.readouterr().out


def test_main_reports_when_nothing_is_discovered(tmp_path, check_examples):
    assert check_examples.main(["--check", "--path", str(tmp_path / "empty")]) == 1
