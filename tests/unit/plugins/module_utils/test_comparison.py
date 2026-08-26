"""Unit tests for resource diff computation."""

from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import (
    build_diff,
    changed,
)


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
