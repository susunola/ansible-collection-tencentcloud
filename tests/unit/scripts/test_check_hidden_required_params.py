"""Unit tests for scripts/check_hidden_required_params.py.

The gate introspects SDK request models to find required fields a
generated ``*_info`` spec cannot supply. The docstring heuristics,
pagination coverage logic, curated-map validation and the ``--check``
exit behaviour are all testable without the SDK installed (the script
loads fine SDK-less; model introspection degrades to import errors).
"""

from __future__ import absolute_import, division, print_function

import importlib.util
import io
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_hidden_required_params.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "check_hidden_required_params", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load_script()


def _invoke(guard, monkeypatch, argv, scan_result):
    """Run main() with a stubbed scan() over one synthetic spec."""
    spec = {"module": "synthetic_demo_info", "pagination_type": "int"}
    monkeypatch.setattr(guard, "SPECS", [spec])
    monkeypatch.setattr(guard, "KNOWN_REQUIRED", {})
    monkeypatch.setattr(guard, "scan", lambda spec: scan_result)
    out, err = io.StringIO(), io.StringIO()
    rc = guard.main(argv, out=out, err=err)
    return rc, out, err


# --- Docstring requiredness heuristics -------------------------------------

def test_old_style_marker_marks_required(guard):
    class FakeRequest(object):
        def __init__(self):
            """Docstring.

            <li> ZoneId - String - 是否必填：是 - The zone id</li>
            <li> Limit - Integer - 是否必填：否 - Max results</li>
            """

    fields = guard._docstring_fields(FakeRequest)
    assert fields == {"ZoneId": False}  # False == required


def test_format_b_fields_without_default_are_required(guard):
    """At least one literal default -> fields without a literal are required."""
    class FakeRequest(object):
        def __init__(self):
            """Docstring.

            :param _Limit: 20
            :param _ZoneId: the target zone
            """

    fields = guard._docstring_fields(FakeRequest)
    assert fields["Limit"] is True    # has default -> optional
    assert fields["ZoneId"] is False  # prose -> required


def test_format_a_no_default_signal(guard):
    """No literal defaults at all -> requiredness not encoded."""
    class FakeRequest(object):
        def __init__(self):
            """Docstring.

            :param _Name: the instance name
            :param _Zone: availability zone
            """

    assert guard._docstring_fields(FakeRequest) == {}


def test_old_style_wins_over_new_style(guard):
    class FakeRequest(object):
        def __init__(self):
            """Docstring.

            <li> QuestionId - String - 是否必填：是 - The question</li>
            :param _QuestionId: some prose
            """

    fields = guard._docstring_fields(FakeRequest)
    assert fields["QuestionId"] is False


def test_default_regex_matches_literals_only(guard):
    literal = ["1", "0", "-5", "1.5", "True", "False", "None",
               "[a, b]", "'x'", '"y"']
    for value in literal:
        assert guard._DEFAULT_RE.match(value), value
    # Prose that merely starts with a digit must not be a default.
    assert not guard._DEFAULT_RE.match("1：倒序，0：顺序")
    assert not guard._DEFAULT_RE.match("the zone id")


# --- Coverage computation --------------------------------------------------

def test_covered_fields_int_pagination(guard):
    spec = {"pagination_type": "int", "extra_params": [
        {"field": "ZoneId", "name": "zone_id", "type": "str"},
    ]}
    assert guard._covered_fields(spec) == {"Offset", "Limit", "ZoneId"}


def test_covered_fields_page_pagination(guard):
    spec = {"pagination_type": "page", "ids": {"field": "ClusterId", "param": "cluster_id"},
            "filters": True}
    assert guard._covered_fields(spec) == {
        "PageNumber", "PageSize", "ClusterId", "Filters"}


def test_covered_fields_token_pagination(guard):
    spec = {"pagination_type": "token", "token_request_field": "NextToken",
            "page_size_field": "MaxResults"}
    assert guard._covered_fields(spec) == {"NextToken", "MaxResults"}


# --- Curated map validation ------------------------------------------------

def test_validate_known_required_fails_on_missing_spec(guard, monkeypatch):
    monkeypatch.setattr(guard, "SPECS", [{"module": "a_info"}])
    monkeypatch.setattr(guard, "KNOWN_REQUIRED", {"ghost_info": {"X"}})
    with pytest.raises(SystemExit) as exc:
        guard._validate_known_required()
    assert "ghost_info" in str(exc.value)
    assert "no longer exist" in str(exc.value)


# --- main() gate behaviour -------------------------------------------------

def test_main_check_passes_when_clean(guard, monkeypatch):
    rc, out, err = _invoke(guard, monkeypatch, ["--check"], ([], None))
    assert rc == 0
    assert "no hidden required params found" in out.getvalue()
    assert err.getvalue() == ""


def test_main_check_fails_on_findings(guard, monkeypatch):
    rc, out, err = _invoke(
        guard, monkeypatch, ["--check"],
        ([("ZoneId", "SDK docstring")], None))
    assert rc == 1
    assert "hidden required params (1)" in out.getvalue()
    assert "ZoneId" in out.getvalue()
    assert "REQUIRED_PARAM_OVERRIDES" in err.getvalue()
    assert "KNOWN_REQUIRED" in err.getvalue()


def test_main_report_mode_does_not_fail_on_findings(guard, monkeypatch):
    rc, out, err = _invoke(
        guard, monkeypatch, [],
        ([("ZoneId", "SDK docstring")], None))
    assert rc == 0
    assert "hidden required params (1)" in out.getvalue()


def test_main_check_fails_on_import_errors(guard, monkeypatch):
    rc, out, err = _invoke(
        guard, monkeypatch, ["--check"], ([], "import error for x.models"))
    assert rc == 1
    assert "import errors prevent full verification" in err.getvalue()
    assert "import error for x.models" in out.getvalue()
