"""Unit tests for resource diff computation."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import (
    build_diff,
    changed,
    maybe_diff,
)


class FakeModule(object):
    def __init__(self, check_mode=False, diff=False):
        self.check_mode = check_mode
        if diff is not None:
            self._diff = diff


def test_build_diff_create():
    assert build_diff(None, {"name": "web"}) == {"before": None, "after": {"name": "web"}}


def test_build_diff_delete():
    assert build_diff({"name": "web"}, None) == {"before": {"name": "web"}, "after": None}


def test_build_diff_update():
    diff = build_diff({"name": "old"}, {"name": "new"})
    assert diff["before"]["name"] == "old"
    assert diff["after"]["name"] == "new"


def test_build_diff_both_none():
    assert build_diff(None, None) is None


def test_build_diff_strips_empty_values():
    diff = build_diff({"a": "", "b": [], "c": {}, "d": "keep"}, {"a": "x"})
    assert diff["before"] == {"d": "keep"}
    assert diff["after"] == {"a": "x"}


def test_changed_detects_difference():
    assert changed({"name": "old"}, {"name": "new"})
    assert not changed({"name": "same"}, {"name": "same"})


def test_changed_ignores_noise_keys():
    assert not changed({"name": "same", "CreatedTime": "t1"}, {"name": "same", "CreatedTime": "t2"}, ignore_keys=("CreatedTime",))
    assert changed({"name": "same", "Desc": "a"}, {"name": "same", "Desc": "b"}, ignore_keys=("CreatedTime",))


def test_changed_absent_vs_present():
    assert changed(None, {"name": "new"})
    assert not changed(None, None)


def test_changed_normalizes_empty_containers():
    assert not changed({"tags": {}}, {"tags": None})


def test_maybe_diff_plain_run_returns_none():
    assert maybe_diff(FakeModule(), {"a": 1}, {"a": 2}) is None


def test_maybe_diff_check_mode_returns_diff():
    diff = maybe_diff(FakeModule(check_mode=True), {"a": 1}, {"a": 2})
    assert diff == {"diff": {"before": {"a": 1}, "after": {"a": 2}}}


def test_maybe_diff_diff_mode_returns_diff():
    diff = maybe_diff(FakeModule(diff=True), None, {"a": 1})
    assert diff == {"diff": {"before": None, "after": {"a": 1}}}


def test_maybe_diff_tolerates_missing_diff_attribute():
    assert maybe_diff(FakeModule(diff=None), {"a": 1}, {"a": 2}) is None
