# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_changelog_fragments.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_changelog_fragments", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fragments():
    return _load_script()


@pytest.fixture
def tree(tmp_path, fragments):
    """Point the check at a throwaway fragments directory and config."""
    saved = (fragments.FRAGMENTS_DIR, fragments.CONFIG)
    (tmp_path / "fragments").mkdir()
    (tmp_path / "config.yaml").write_text(
        "---\n"
        "prelude_section_name: release_summary\n"
        "sections:\n"
        "  - [major_changes, Major Changes]\n"
        "  - [minor_changes, Minor Changes]\n"
        "  - [bugfixes, Bugfixes]\n", encoding="utf-8")
    fragments.FRAGMENTS_DIR = str(tmp_path / "fragments")
    fragments.CONFIG = str(tmp_path / "config.yaml")
    yield tmp_path
    fragments.FRAGMENTS_DIR, fragments.CONFIG = saved


def write(tree, name, body):
    (tree / "fragments" / name).write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------
# the real repository
# --------------------------------------------------------------------------

def test_repository_fragments_pass(fragments):
    assert fragments.findings() == []
    assert fragments.main(["--check"]) == 0


def test_config_sections_include_the_prelude(fragments):
    sections = fragments.configured_sections()
    assert {"bugfixes", "minor_changes"} <= sections
    assert "release_summary" in sections


def test_config_sections_match_the_repository_config(fragments):
    """The section list is read from the config, not written down here."""
    assert fragments.configured_sections() == {
        "major_changes", "minor_changes", "breaking_changes",
        "deprecated_features", "removed_features", "security_fixes",
        "bugfixes", "known_issues", "release_summary"}


# --------------------------------------------------------------------------
# what the check rejects
# --------------------------------------------------------------------------

def test_unknown_section_is_reported(tree, fragments):
    """``bugfix`` for ``bugfixes`` is valid YAML, so yamllint accepts it and
    the entry is dropped from the release notes."""
    write(tree, "typo.yml", "---\nbugfix:\n  - a thing\n")
    problems = fragments.findings()
    assert len(problems) == 1
    assert problems[0][0] == "typo.yml"
    assert "uses section 'bugfix'" in problems[0][1]


def test_known_sections_are_accepted(tree, fragments):
    write(tree, "ok.yml", "---\nbugfixes:\n  - a thing\nminor_changes:\n  - another\n")
    assert fragments.findings() == []


def test_empty_fragment_is_reported(tree, fragments):
    write(tree, "empty.yml", "---\n")
    assert fragments.findings() == [("empty.yml", "is empty")]


def test_fragment_that_is_not_a_mapping_is_reported(tree, fragments):
    write(tree, "list.yml", "---\n- one\n- two\n")
    assert fragments.findings() == [
        ("list.yml", "is not a mapping of section to entries")]


def test_fragment_that_is_not_yaml_is_reported(tree, fragments):
    write(tree, "broken.yml", "---\nbugfixes:\n  - [unclosed\n")
    problems = fragments.findings()
    assert len(problems) == 1 and "is not valid YAML" in problems[0][1]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_main_check_fails_and_names_the_fragment(tree, fragments, capsys):
    write(tree, "typo.yml", "---\nbugfix:\n  - a thing\n")
    assert fragments.main(["--check"]) == 1
    assert "typo.yml" in capsys.readouterr().err


def test_main_without_check_reports_the_census(tree, fragments, capsys):
    write(tree, "typo.yml", "---\nbugfix:\n  - a thing\n")
    assert fragments.main([]) == 0
    assert "1 fragment(s), 1 problem(s)" in capsys.readouterr().out


def test_a_subject_naming_a_real_module_passes(tree, fragments):
    write(tree, "ok.yml", "---\nbugfixes:\n  - cdb_instance - fixed a thing.\n")
    assert fragments.findings() == []


def test_a_subject_naming_a_ghost_is_reported(tree, fragments):
    """The failure mode this is for: a fragment naming modules from a wrong
    census reads as fact in the release notes."""
    write(tree, "ghost.yml",
          "---\nbugfixes:\n  - cdb_ghost_module - fixed a thing.\n")
    found = fragments.findings()
    assert len(found) == 1
    assert "cdb_ghost_module" in found[0][1]


def test_a_module_named_only_in_the_body_is_not_checked(tree, fragments):
    """The subject is the claim; prose after the dash stays prose."""
    write(tree, "prose.yml",
          "---\nbugfixes:\n  - cdb_instance - see also made_up_name here.\n")
    assert fragments.findings() == []


def test_an_allowlisted_subject_passes(tree, fragments):
    write(tree, "nolog.yml",
          "---\nminor_changes:\n  - no_log - marked secret options.\n")
    assert fragments.findings() == []


def test_a_script_or_role_subject_passes(tree, fragments):
    write(tree, "multi.yml",
          "---\nminor_changes:\n"
          "  - check_quality_gates - new ratchet.\n"
          "  - tc_alb_application_entry - documented a variable.\n")
    assert fragments.findings() == []
