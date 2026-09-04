from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_info_coverage.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("audit_info_coverage", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_script():
    return _load_script()


@pytest.fixture
def fake_modules(tmp_path, audit_script):
    """Point the script's MODULES_DIR at a throwaway directory."""
    old_dir = audit_script.MODULES_DIR
    audit_script.MODULES_DIR = tmp_path
    yield tmp_path
    audit_script.MODULES_DIR = old_dir


def _touch(fake_modules, name):
    (fake_modules / (name + ".py")).write_text("# stub\n", encoding="utf-8")


def test_direct_info_module_covers(audit_script, fake_modules):
    _touch(fake_modules, "vpc")
    _touch(fake_modules, "vpc_info")
    rows, uncovered = audit_script.audit()
    assert rows == [("vpc", "covered", "vpc_info")]
    assert uncovered == []


def test_known_coverage_mapping(audit_script, fake_modules, monkeypatch):
    monkeypatch.setitem(audit_script.KNOWN_COVERAGE, "nat_gateway_rule",
                        (["nat_gateway_dnat_rule_info", "nat_gateway_snat_rule_info"], "test"))
    _touch(fake_modules, "nat_gateway_rule")
    _touch(fake_modules, "nat_gateway_dnat_rule_info")
    _touch(fake_modules, "nat_gateway_snat_rule_info")
    try:
        rows, uncovered = audit_script.audit()
        assert rows[0][1] == "mapped"
        assert uncovered == []
    finally:
        monkeypatch.undo()


def test_known_coverage_referencing_missing_module_fails(audit_script, fake_modules, monkeypatch):
    monkeypatch.setitem(audit_script.KNOWN_COVERAGE, "ghost", (["ghost_info"], "test"))
    _touch(fake_modules, "ghost")
    try:
        rows, uncovered = audit_script.audit()
        assert uncovered == ["ghost"]
        assert "missing" in rows[0][2]
    finally:
        del audit_script.KNOWN_COVERAGE["ghost"]


def test_backlog_gap_is_accepted(audit_script, fake_modules, monkeypatch):
    monkeypatch.setattr(audit_script, "KNOWN_GAPS", {"widget"})
    _touch(fake_modules, "widget")
    rows, uncovered = audit_script.audit()
    assert rows[0][1] == "gap"
    assert "backlog" in rows[0][2]
    assert uncovered == []


def test_no_list_api_gap_is_accepted(audit_script, fake_modules, monkeypatch):
    monkeypatch.setattr(audit_script, "KNOWN_NO_LIST_API", {"widget": "no list API"})
    _touch(fake_modules, "widget")
    rows, uncovered = audit_script.audit()
    assert rows[0][1] == "gap"
    assert "no-list-api" in rows[0][2]
    assert uncovered == []


def test_uncovered_module_fails_check(audit_script, fake_modules):
    _touch(fake_modules, "mystery")
    rows, uncovered = audit_script.audit()
    assert uncovered == ["mystery"]
    assert audit_script.main(["--check"], out=io.StringIO(), err=io.StringIO()) == 1


def test_check_passes_when_all_classified(audit_script, fake_modules, monkeypatch):
    monkeypatch.setattr(audit_script, "KNOWN_GAPS", set())
    monkeypatch.setattr(audit_script, "KNOWN_NO_LIST_API", {})
    monkeypatch.setattr(audit_script, "KNOWN_COVERAGE", {})
    _touch(fake_modules, "widget")
    _touch(fake_modules, "widget_info")
    assert audit_script.main(["--check"], out=io.StringIO(), err=io.StringIO()) == 0


def test_stale_gap_entry_fails_check(audit_script, fake_modules, monkeypatch):
    # A KNOWN_GAPS name whose <name>_info now exists must be removed.
    monkeypatch.setattr(audit_script, "KNOWN_GAPS", {"widget"})
    _touch(fake_modules, "widget")
    _touch(fake_modules, "widget_info")
    try:
        assert audit_script.main(["--check"], out=io.StringIO(), err=io.StringIO()) == 1
    finally:
        monkeypatch.undo()


def test_real_collection_has_no_uncovered_write_modules(audit_script):
    rows, uncovered = audit_script.audit()
    assert uncovered == []
    assert audit_script.main(["--check"], out=io.StringIO(), err=io.StringIO()) == 0
