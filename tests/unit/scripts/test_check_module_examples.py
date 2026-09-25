# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_module_examples.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_module_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_script()


@pytest.fixture
def tree(tmp_path, checker):
    """Point the checker's lookup dirs at a throwaway repository layout."""
    import check_examples

    saved_modules = checker.MODULES_DIR
    saved_fragments = checker.DOC_FRAGMENTS_DIR
    saved_shared_modules = check_examples.MODULES_DIR
    saved_shared_fragments = check_examples.DOC_FRAGMENTS_DIR
    modules = tmp_path / "plugins" / "modules"
    fragments = tmp_path / "plugins" / "doc_fragments"
    for directory in (modules, fragments):
        directory.mkdir(parents=True)
    checker.MODULES_DIR = modules
    checker.DOC_FRAGMENTS_DIR = fragments
    # The option and required-option lookups are shared with check_examples,
    # so both modules have to be redirected or the fixture would validate
    # against the real collection.
    check_examples.MODULES_DIR = modules
    check_examples.DOC_FRAGMENTS_DIR = fragments
    yield tmp_path
    checker.MODULES_DIR = saved_modules
    checker.DOC_FRAGMENTS_DIR = saved_fragments
    check_examples.MODULES_DIR = saved_shared_modules
    check_examples.DOC_FRAGMENTS_DIR = saved_shared_fragments


def write_module(tree, name, body, options=(), fragments=()):
    """Create a module file whose EXAMPLES block is *body*.

    *options* takes either a name or a ``(name, required)`` pair.
    """
    lines = ["DOCUMENTATION = r'''", "module: %s" % name, "options:"]
    for entry in options:
        if isinstance(entry, str):
            option, required = entry, False
        else:
            option, required = entry
        lines += ["  %s:" % option, "    description: x", "    type: str"]
        if required:
            lines += ["    required: true"]
    if fragments:
        lines.append("extends_documentation_fragment:")
        for fragment in fragments:
            lines.append("  - susunola.tencentcloud.%s" % fragment)
    lines += ["author: test", "'''", "", "EXAMPLES = r'''", body, "'''", ""]
    return (tree / "plugins" / "modules" / (name + ".py")).write_text("\n".join(lines))


def write_fragment(tree, name, options=()):
    lines = ["class ModuleDocFragment(object):", "    DOCUMENTATION = r'''", "options:"]
    for option, required in options:
        lines += ["      %s:" % option, "        description: x", "        type: str"]
        if required:
            lines += ["        required: true"]
    lines += ["'''", ""]
    (tree / "plugins" / "doc_fragments" / (name + ".py")).write_text("\n".join(lines))


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_examples_pass_the_check(checker):
    """Every shipped example must be runnable; this is what CI asserts."""
    assert checker.check() == {}


def test_main_check_exits_zero_on_the_real_tree(checker):
    assert checker.main(["--check"]) == 0


def test_census_reports_the_module_count(checker, capsys):
    assert checker.main([]) == 0
    out = capsys.readouterr().out
    assert "1027 module(s) checked" in out


# --------------------------------------------------------------------------
# the defects this check was written for
# --------------------------------------------------------------------------

def test_misspelled_module_name_is_reported(tree, checker):
    """tse_governance_alias_info shipped an example calling a name that does
    not exist, so the copy-paste failed before reaching Tencent Cloud."""
    write_module(tree, "tse_governance_alias_info", """\
- name: List all governance aliases
  susunola.tencentcloud.tse_governance_aliase_info:
    region: ap-guangzhou
""")
    problems = checker.check_module(tree / "plugins" / "modules" / "tse_governance_alias_info.py")
    assert any("tse_governance_aliase_info" in item for item in problems)
    assert any("itself" in item for item in problems)


def test_missing_required_option_is_reported(tree, checker):
    """lcic_answer_info documented an example without the question id its
    argument spec requires."""
    write_module(tree, "lcic_answer_info", """\
- name: List all answers
  susunola.tencentcloud.lcic_answer_info:
    region: ap-guangzhou
""", options=["region", ("question_id", True), "page_size"])
    problems = checker.check_module(tree / "plugins" / "modules" / "lcic_answer_info.py")
    assert problems == ["task 'List all answers' calls lcic_answer_info without "
                        "question_id, which it marks required"]


def test_required_option_from_a_fragment_is_honoured(tree, checker):
    write_fragment(tree, "credentials", options=[("secret_id", True)])
    write_module(tree, "demo_info", """\
- name: List demos
  susunola.tencentcloud.demo_info:
    region: ap-guangzhou
""", fragments=["credentials"])
    problems = checker.check_module(tree / "plugins" / "modules" / "demo_info.py")
    assert any("without secret_id" in item for item in problems)


def test_undeclared_option_is_reported(tree, checker):
    write_module(tree, "demo", """\
- name: Create a demo
  susunola.tencentcloud.demo:
    region: ap-guangzhou
    namee: typo
""", options=["region", "name"])
    problems = checker.check_module(tree / "plugins" / "modules" / "demo.py")
    assert problems == ["task 'Create a demo' passes namee to demo, "
                        "which does not declare that option"]


# --------------------------------------------------------------------------
# shapes the checker has to accept
# --------------------------------------------------------------------------

def test_module_call_with_no_arguments_is_recognised(tree, checker):
    """A module with no options is documented as a bare ``module:`` key,
    whose value is None and which no other parser treats as a call."""
    write_module(tree, "ssm_supported_product_info", """\
- susunola.tencentcloud.ssm_supported_product_info:
  register: ssm_products
""")
    problems = checker.check_module(
        tree / "plugins" / "modules" / "ssm_supported_product_info.py")
    assert problems == []


def test_play_style_examples_are_accepted(tree, checker):
    write_module(tree, "demo", """\
- name: Create a demo
  hosts: localhost
  tasks:
    - name: Do it
      susunola.tencentcloud.demo:
        region: ap-guangzhou
""", options=[("region", False)])
    problems = checker.check_module(tree / "plugins" / "modules" / "demo.py")
    assert problems == []


def test_other_collections_modules_are_ignored(tree, checker):
    write_module(tree, "demo", """\
- name: Create a demo
  susunola.tencentcloud.demo:
    region: ap-guangzhou
- name: Debug
  ansible.builtin.debug:
    msg: hello
""", options=[("region", False)])
    problems = checker.check_module(tree / "plugins" / "modules" / "demo.py")
    assert problems == []


def test_module_with_no_examples_is_reported(tree, checker):
    path = tree / "plugins" / "modules" / "demo.py"
    path.write_text("DOCUMENTATION = r'''\nmodule: demo\n'''\n")
    assert checker.check_module(path) == ["has no EXAMPLES block that can be read"]


def test_examples_that_are_not_yaml_are_reported(tree, checker):
    write_module(tree, "demo", "- name: broken\n   susunola.tencentcloud.demo: {")
    problems = checker.check_module(tree / "plugins" / "modules" / "demo.py")
    assert len(problems) == 1
    assert "not valid YAML" in problems[0]


def test_examples_that_are_not_a_task_list_are_reported(tree, checker):
    write_module(tree, "demo", "just a string")
    problems = checker.check_module(tree / "plugins" / "modules" / "demo.py")
    assert problems == ["EXAMPLES is not a list of tasks or of plays"]


def test_empty_examples_block_is_not_a_problem(tree, checker):
    """validate-modules already covers a missing block; this check is about
    examples that exist and cannot be run."""
    write_module(tree, "demo", "")
    assert checker.check_module(tree / "plugins" / "modules" / "demo.py") == []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_main_check_fails_and_names_the_module(tree, checker, capsys):
    write_module(tree, "demo", """\
- name: Create a demo
  susunola.tencentcloud.ghost:
    region: ap-guangzhou
""")
    assert checker.main(["--check"]) == 1
    assert "demo" in capsys.readouterr().err
