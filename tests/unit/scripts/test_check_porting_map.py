# -*- coding: utf-8 -*-
"""Tests for scripts/check_porting_map.py."""

from __future__ import absolute_import, division, print_function

import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_porting_map.py"

_spec = importlib.util.spec_from_file_location("check_porting_map", SCRIPT)
check_porting_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_porting_map)


REAL_DOC = check_porting_map.PORTING_DOC


def _write_doc(tmp_path, text):
    p = tmp_path / "porting.md"
    p.write_text(text, encoding="utf-8")
    return p


# A minimal but representative mapping row: a real Terraform resource in the
# first cell, a single backticked module in the second.
GOOD_ROW = "| `tencentcloud_vpc` | `vpc` | directly named |\n"


def test_real_doc_passes():
    problems, seen = check_porting_map.check(REAL_DOC)
    assert problems == [], problems
    # The two resource-map tables in the shipped doc name 30 modules.
    assert len(seen) == 30


def test_missing_module_is_reported(tmp_path):
    doc = _write_doc(tmp_path, "# t\n\n" + GOOD_ROW +
                     "| `tencentcloud_clb_instance` | `clb_loadbalancer` | wrong name |\n")
    problems, seen = check_porting_map.check(doc)
    assert any("clb_loadbalancer" in p for p in problems), problems
    assert "vpc" in seen


def test_fqcn_form_resolves(tmp_path):
    doc = _write_doc(tmp_path, "# t\n\n" +
                     "| `tencentcloud_clb_instance` | `susunola.tencentcloud.clb_load_balancer` | fqcn |\n")
    problems, seen = check_porting_map.check(doc)
    assert problems == [], problems
    assert "clb_load_balancer" in seen


def test_prose_tables_are_ignored(tmp_path):
    # The mental-model table (col2 `loop`) and the credential table (col2
    # `region`, `TENCENTCLOUD_SHARED_CREDENTIALS_DIR`) must not be read as
    # module names even though they are single backticks.
    doc = _write_doc(tmp_path, "# t\n\n"
                     "| `count` / `for_each` | `loop` | see [x](#y) |\n"
                     "| File location override | `TENCENTCLOUD_SHARED_CREDENTIALS_DIR` | none |\n"
                     "| `resource " + '"tencentcloud_x" "y"` | `susunola.tencentcloud.<module>` | z |\n')
    problems, seen = check_porting_map.check(doc)
    assert problems == [], problems
    assert seen == set()


def test_separator_row_is_skipped(tmp_path):
    doc = _write_doc(tmp_path, "# t\n\n"
                     "| Terraform resource | Module | Note |\n"
                     "| --- | --- | --- |\n" + GOOD_ROW)
    problems, seen = check_porting_map.check(doc)
    assert problems == [], problems
    assert seen == {"vpc"}


def test_missing_doc_reports_error():
    problems, seen = check_porting_map.check(REPO_ROOT / "docs" / "nope.md")
    assert problems
    assert seen == set()
