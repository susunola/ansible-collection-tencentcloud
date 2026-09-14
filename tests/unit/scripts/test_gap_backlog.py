# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for scripts/gap_backlog.py.

The tool's first version scraped ``KNOWN_GAPS`` out of
``scripts/audit_info_coverage.py`` with a regex that only matched
double-quoted names, while the set is written with single quotes, so it
reported every gap as UNTRACKED -- 0% of the curated backlog was visible.
It also called every write module without a sibling ``_info`` a gap, which
mixed together three very different situations.

So the anchor here is the curated tables themselves: every name the audit
module knows about must land in the bucket its verdict implies. If the
scraper ever comes back, or if a bucket silently empties, these fail.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "gap_backlog.py"
AUDIT_PATH = REPO_ROOT / "scripts" / "audit_info_coverage.py"
MODULES_DIR = REPO_ROOT / "plugins" / "modules"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load(SCRIPT_PATH, "gap_backlog")


@pytest.fixture(scope="module")
def audit():
    return _load(AUDIT_PATH, "audit_info_coverage_for_backlog")


@pytest.fixture(scope="module")
def data(tool):
    return tool.collect(REPO_ROOT)


def _names(bucket_map):
    return {name for names in bucket_map.values() for name in names}


def test_the_real_repo_has_a_backlog(data):
    """Anti-vacuity: an empty backlog would make every other test pass."""
    assert data["counts"]["backlog"] > 0
    assert data["counts"]["mapped"] > 0
    assert data["counts"]["no-list-api"] > 0


def test_every_known_gap_is_reported_as_backlog(data, audit):
    backlog = _names(data["by_product"]["backlog"])
    assert audit.KNOWN_GAPS, "the curated backlog itself is empty"
    assert audit.KNOWN_GAPS <= backlog


def test_every_no_list_api_module_is_reported_as_such(data, audit):
    no_list = _names(data["by_product"]["no-list-api"])
    assert audit.KNOWN_NO_LIST_API, "the no-list-api table itself is empty"
    assert set(audit.KNOWN_NO_LIST_API) <= no_list


def test_every_known_coverage_module_is_reported_as_mapped(data, audit):
    mapped = _names(data["by_product"]["mapped"])
    assert audit.KNOWN_COVERAGE, "the coverage table itself is empty"
    assert set(audit.KNOWN_COVERAGE) <= mapped


def test_the_report_has_no_surprise_buckets(data, tool):
    """A bucket nobody reads would silently break the partition."""
    assert set(data["by_product"]) == set(tool.BUCKETS)


def test_the_buckets_partition_the_modules_without_a_sibling(data):
    on_disk = {p.stem for p in MODULES_DIR.glob("*.py")
               if not p.name.startswith("__")}
    writes = {n for n in on_disk if not n.endswith("_info")}
    missing = {n for n in writes if "%s_info" % n not in on_disk}

    counted = set()
    for names_by_product in data["by_product"].values():
        counted |= _names(names_by_product)
    assert counted == missing
    assert data["write_modules"] == len(writes)
    assert data["covered"] == len(writes) - len(missing)
    total = sum(data["counts"].values())
    assert total == len(missing)


def test_no_module_lands_in_two_buckets(data):
    seen = {}
    for bucket, names_by_product in data["by_product"].items():
        for name in _names(names_by_product):
            assert name not in seen, "%s is in both %s and %s" % (
                name, seen[name], bucket)
            seen[name] = bucket


def test_the_audit_itself_leaves_nothing_uncovered(data):
    audit_info_coverage = _load(AUDIT_PATH, "audit_info_coverage_uncovered")
    _rows, uncovered = audit_info_coverage.audit()
    assert uncovered == []
    assert data["uncovered"] == []


def test_products_come_from_the_repo_definition(tool):
    products = tool.product_map(REPO_ROOT)
    on_disk = {p.stem for p in MODULES_DIR.glob("*.py")
               if not p.name.startswith("__")}
    assert set(products) == on_disk
    # The old prefix split put these two families in different products.
    assert products["api_gateway_api_key"] == products["apigateway_plugin"]


def test_the_report_states_every_bucket(tool, data):
    text = tool.report(data)
    for bucket in ("mapped", "no-list-api", "backlog"):
        assert bucket in text
        assert str(data["counts"][bucket]) in text
    assert "tse" in text or "cos" in text


def test_the_report_lists_every_backlog_product(tool, data):
    full = tool.report(data, show_all=True)
    products = data["by_product"]["backlog"]
    assert products
    for product in products:
        assert product in full


def test_the_report_can_truncate_long_products(tool, data):
    long_product = max(data["by_product"]["backlog"],
                       key=lambda p: len(data["by_product"]["backlog"][p]))
    text = tool.report(data)
    full = tool.report(data, show_all=True)
    assert len(full) >= len(text)
    assert long_product in text
