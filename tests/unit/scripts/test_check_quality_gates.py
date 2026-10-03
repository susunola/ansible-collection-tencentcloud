# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tests for the frozen baselines in scripts/check_quality_gates.py.

Two of the census families are stock counts of existing debt: RETURN entries
with no ``sample`` and core-subset write modules with no integration target.
A stock ceiling alone cannot tell "fixed three, broke three" apart from
"fixed nothing", so each family is also frozen as an explicit list. These
tests pin the three properties that make the list useful: a module that is
not on it must not have the finding, a listed module that no longer has the
finding must be delisted, and the committed lists must match the committed
tree.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_quality_gates.py"


def _null():
    """A throwaway stream for the helper calls that report progress."""
    return io.StringIO()


def _load_script():
    spec = importlib.util.spec_from_file_location("check_quality_gates",
                                                  SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gates():
    return _load_script()


@pytest.fixture
def baselines(gates, tmp_path, monkeypatch):
    """Point the baseline directory at a throwaway tree."""
    monkeypatch.setattr(gates, "BASELINES_DIR", str(tmp_path))
    return gates


def test_missing_baseline_is_reported(baselines):
    problems = baselines.baseline_problems("return_samples", ["a", "b"])
    assert len(problems) == 1
    assert "is missing" in problems[0]
    assert "--write-baseline return_samples" in problems[0]


def test_write_then_read_round_trips(baselines):
    assert baselines.write_baseline("return_samples", ["b", "a"],
                                    out=_null()) == 0
    assert baselines.read_baseline("return_samples") == ["a", "b"]


def test_matching_findings_pass(baselines):
    baselines.write_baseline("return_samples", ["a", "b"], out=_null())
    assert baselines.baseline_problems("return_samples", ["a", "b"]) == []


def test_new_finding_is_reported(baselines):
    baselines.write_baseline("return_samples", ["a"], out=_null())
    problems = baselines.baseline_problems("return_samples", ["a", "new_module"])
    assert len(problems) == 1
    assert "new_module" in problems[0]
    assert "not in the return_samples baseline" in problems[0]
    assert "--write-baseline" not in problems[0]


def test_fixed_and_broken_module_is_still_reported(baselines):
    """The loophole a stock ceiling leaves open.

    One module gained a sample and one new module lost one, so the *count* is
    unchanged and a stock ratchet would stay green. The baseline does not:
    the new module is not on the list.
    """
    baselines.write_baseline("return_samples", ["old_a", "old_b"], out=_null())
    problems = baselines.baseline_problems("return_samples",
                                           ["old_a", "new_module"])
    assert any("new_module" in problem and "not in the" in problem
               for problem in problems)
    assert any("old_b" in problem and "no longer have the finding" in problem
               for problem in problems)


def test_stale_entry_is_reported(baselines):
    baselines.write_baseline("return_samples", ["a", "fixed"], out=_null())
    problems = baselines.baseline_problems("return_samples", ["a"])
    assert len(problems) == 1
    assert "fixed" in problems[0]
    assert "only shrinks" in problems[0]


def test_write_baseline_reports_what_moved(baselines):
    baselines.write_baseline("return_samples", ["a", "b"], out=_null())
    out = io.StringIO()
    baselines.write_baseline("return_samples", ["b", "c"], out=out)
    report = out.getvalue()
    assert "+1, -1" in report
    assert "added:   c" in report
    assert "removed: a" in report


def test_baseline_file_explains_itself(baselines):
    baselines.write_baseline("integration_missing", ["a"], out=_null())
    text = Path(baselines.baseline_path("integration_missing")).read_text(
        encoding="utf-8")
    assert text.startswith("#")
    assert "may only shrink" in text


def test_write_baseline_is_reachable_from_the_command_line(baselines):
    """The documented way to freeze a family must exist and work."""
    assert baselines.main(["--write-baseline", "return_samples"]) == 0
    assert baselines.read_baseline("return_samples") == \
        baselines.return_sample_findings()


def test_committed_return_sample_baseline_matches_the_tree(gates):
    frozen = gates.read_baseline(gates.BASELINE_RETURN_SAMPLES)
    assert frozen is not None
    assert frozen == gates.return_sample_findings()


def test_committed_integration_baseline_matches_the_tree(gates):
    frozen = gates.read_baseline(gates.BASELINE_INTEGRATION_MISSING)
    assert frozen is not None
    assert frozen == gates.integration_findings()[1]


# --------------------------------------------------------------------------
# role READMEs
# --------------------------------------------------------------------------

def _write_role(root, name, readme, defaults="", tasks=None):
    role = Path(root) / "roles" / name
    (role / "defaults").mkdir(parents=True, exist_ok=True)
    (role / "defaults" / "main.yml").write_text(defaults, encoding="utf-8")
    (role / "README.md").write_text(readme, encoding="utf-8")
    if tasks is not None:
        (role / "tasks").mkdir(parents=True, exist_ok=True)
        (role / "tasks" / "main.yml").write_text(tasks, encoding="utf-8")
    return role


@pytest.fixture
def role_tree(gates, tmp_path, monkeypatch):
    monkeypatch.setattr(gates, "REPO_ROOT", str(tmp_path))
    return tmp_path


def test_a_role_readme_naming_a_declared_input_is_clean(gates, role_tree):
    _write_role(role_tree, "tc_demo",
                "Set `tc_demo_name` and `tc_demo_cidr_block`.\n",
                defaults="---\ntc_demo_name: \"\"\ntc_demo_cidr_block: \"\"\n")
    assert gates.role_doc_findings() == []


def test_a_role_readme_naming_a_published_output_is_clean(gates, role_tree):
    """``tc_<role>_result`` is an output: defaults do not declare it."""
    _write_role(role_tree, "tc_demo",
                "The role publishes `tc_demo_result`.\n",
                defaults="---\ntc_demo_name: \"\"\n",
                tasks="---\n- name: Publish\n  ansible.builtin.set_fact:\n"
                      "    tc_demo_result: \"{{ tc_demo_name }}\"\n")
    assert gates.role_doc_findings() == []


def test_a_role_readme_naming_an_unknown_variable_is_reported(gates, role_tree):
    _write_role(role_tree, "tc_demo", "Set `tc_demo_missing`.\n",
                defaults="---\ntc_demo_name: \"\"\n")
    problems = gates.role_doc_findings()
    assert len(problems) == 1
    assert "tc_demo_missing" in problems[0]


def test_a_renamed_default_leaves_the_readme_behind(gates, role_tree):
    """The rename-rot case: the variable exists, under another name."""
    _write_role(role_tree, "tc_demo", "Set `tc_demo_name`.\n",
                defaults="---\ntc_demo_naming: \"\"\n")
    assert len(gates.role_doc_findings()) == 1


def test_a_registered_result_counts_as_published(gates, role_tree):
    _write_role(role_tree, "tc_demo",
                "The role publishes `tc_demo_vpc`.\n",
                defaults="---\ntc_demo_name: \"\"\n",
                tasks="---\n- name: Read\n  ansible.builtin.debug:\n"
                      "    msg: x\n  register: tc_demo_vpc\n")
    assert gates.role_doc_findings() == []


def test_a_role_without_a_readme_is_reported(gates, role_tree):
    role = Path(role_tree) / "roles" / "tc_demo"
    (role / "defaults").mkdir(parents=True)
    (role / "defaults" / "main.yml").write_text("---\n", encoding="utf-8")
    problems = gates.role_doc_findings()
    assert len(problems) == 1
    assert "no README.md" in problems[0]


def test_committed_role_readmes_are_consistent(gates):
    """The repository's own 68 roles must pass, not just the fixture's."""
    assert gates.role_doc_findings() == []


def _module_with_return(tmp_path, body):
    module = tmp_path / "fake_module.py"
    module.write_text('RETURN = r"""\n%s\n"""\n' % body, encoding="utf-8")
    return str(module)


def test_sample_type_census_flags_a_contradiction(gates, tmp_path, monkeypatch):
    """A sample that contradicts the declared type is the doc lying."""
    path = _module_with_return(tmp_path,
                               "good:\n"
                               "  type: int\n"
                               "  sample: 7\n"
                               "bad:\n"
                               "  type: str\n"
                               "  sample: 7\n"
                               "nested:\n"
                               "  type: dict\n"
                               "  contains:\n"
                               "    inner:\n"
                               "      type: list\n"
                               "      sample: not-a-list")
    monkeypatch.setattr(gates, "module_paths", lambda: [path])
    findings = gates.return_sample_type_findings()
    assert len(findings) == 2
    assert any("fake_module :: bad " in f for f in findings)
    assert any("fake_module :: nested.inner " in f for f in findings)


def test_sample_type_census_rejects_a_bool_posing_as_an_int(gates, tmp_path,
                                                            monkeypatch):
    """bool subclasses int in Python; an id documented as int is not a flag."""
    path = _module_with_return(tmp_path,
                               "flag:\n"
                               "  type: int\n"
                               "  sample: true")
    monkeypatch.setattr(gates, "module_paths", lambda: [path])
    assert len(gates.return_sample_type_findings()) == 1


def test_sample_type_census_ignores_untyped_and_raw_entries(gates, tmp_path,
                                                            monkeypatch):
    path = _module_with_return(tmp_path,
                               "anything:\n"
                               "  type: raw\n"
                               "  sample: 7\n"
                               "untyped:\n"
                               "  sample: 7")
    monkeypatch.setattr(gates, "module_paths", lambda: [path])
    assert gates.return_sample_type_findings() == []


def test_committed_return_samples_match_their_declared_types(gates):
    """The repository's own RETURN blocks must pass, not just the fixture's."""
    assert gates.return_sample_type_findings() == []


def _shadow_tree(gates, tmp_path, monkeypatch, frag_type, own_type):
    """One fragment and one module re-declaring its option; returns findings."""
    fragments = tmp_path / "doc_fragments"
    fragments.mkdir()
    (fragments / "shared.py").write_text(
        "class ModuleDocFragment(object):\n"
        "    DOCUMENTATION = r'''\n"
        "options:\n"
        "  role_arn:\n"
        "    description: x\n"
        "    type: %s\n"
        "'''\n" % frag_type, encoding="utf-8")
    module = tmp_path / "fake_module.py"
    module.write_text(
        "DOCUMENTATION = r'''\n"
        "module: fake_module\n"
        "options:\n"
        "  role_arn:\n"
        "    description: x\n"
        "    type: %s\n"
        "extends_documentation_fragment:\n"
        "  - susunola.tencentcloud.shared\n"
        "'''\n" % own_type, encoding="utf-8")
    monkeypatch.setattr(gates, "_DOC_FRAGMENTS_DIR", str(fragments))
    monkeypatch.setattr(gates, "module_paths", lambda: [str(module)])
    return gates.fragment_shadow_findings()


def test_same_type_redeclaration_is_not_a_shadow(gates, tmp_path, monkeypatch):
    """Re-declaring to override a default or description is legitimate."""
    assert _shadow_tree(gates, tmp_path, monkeypatch, "str", "str") == []


def test_a_different_type_is_reported_as_a_shadow(gates, tmp_path, monkeypatch):
    findings = _shadow_tree(gates, tmp_path, monkeypatch, "str", "int")
    assert findings == [
        "fake_module :: role_arn (shared declares str, module declares int)"]


def test_committed_tree_has_only_the_grandfathered_shadow(gates):
    assert gates.fragment_shadow_findings() == [
        "dlc_spark_job :: role_arn (credentials declares str, module declares int)"]
