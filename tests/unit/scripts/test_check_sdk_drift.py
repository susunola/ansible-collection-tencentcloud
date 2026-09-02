"""Unit tests for scripts/check_sdk_drift.py (the SDK drift sentinel)."""

from __future__ import absolute_import, division, print_function

import importlib.util
import io
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_sdk_drift.py"
REAL_AUTO_SPECS = REPO_ROOT / "scripts" / "info_specs_auto.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_sdk_drift", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def drift():
    return _load_script()


STAMPED_FILE = """\
# -*- coding: utf-8 -*-
\"\"\"Auto-discovered specs.\"\"\"

GENERATED_SDK_VERSION = '3.1.113'

SPECS_AUTO = [
]
"""


def _invoke(drift, monkeypatch, tmp_path, installed, content=STAMPED_FILE, name="info_specs_auto.py"):
    specs_path = tmp_path / name
    if content is not None:
        specs_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(drift, "installed_version", lambda: installed)
    out, err = io.StringIO(), io.StringIO()
    rc = drift.main(["--specs", str(specs_path)], out=out, err=err)
    return rc, out, err


def test_matching_version_passes(drift, monkeypatch, tmp_path):
    rc, out, err = _invoke(drift, monkeypatch, tmp_path, installed="3.1.113")
    assert rc == 0
    assert "SDK drift check OK" in out.getvalue()
    assert "3.1.113" in out.getvalue()
    assert err.getvalue() == ""


def test_real_committed_file_passes(drift, monkeypatch):
    """The committed info_specs_auto.py parses and matches its own stamp."""
    # The mock "installed" version must mirror the stamp the committed file
    # actually carries (it moves on every deliberate SDK bump), otherwise
    # this test couples itself to a specific SDK release.
    stamp = re.search(
        r"^GENERATED_SDK_VERSION\s*=\s*['\"]([^'\"]+)['\"]",
        REAL_AUTO_SPECS.read_text(encoding="utf-8"), re.M).group(1)
    rc, out, err = _invoke(
        drift, monkeypatch, tmp_path=Path(REPO_ROOT) / "scripts",
        installed=stamp, content=None, name="info_specs_auto.py")
    assert rc == 0
    assert "SDK drift check OK" in out.getvalue()


def test_drift_fails_with_actionable_message(drift, monkeypatch, tmp_path):
    rc, out, err = _invoke(drift, monkeypatch, tmp_path, installed="3.1.120")
    assert rc == 1
    assert "SDK drift detected" in err.getvalue()
    assert "3.1.113" in err.getvalue()
    assert "3.1.120" in err.getvalue()
    assert "discover_info_specs.py" in err.getvalue()
    assert "generate_info_modules.py" in err.getvalue()
    assert out.getvalue() == ""


def test_missing_stamp_fails(drift, monkeypatch, tmp_path):
    rc, out, err = _invoke(
        drift, monkeypatch, tmp_path, installed="3.1.113",
        content="SPECS_AUTO = []\n")
    assert rc == 1
    assert "no GENERATED_SDK_VERSION stamp" in err.getvalue()


def test_missing_sdk_fails(drift, monkeypatch, tmp_path):
    def _no_sdk():
        raise RuntimeError("tencentcloud-sdk-python is not installed")

    monkeypatch.setattr(drift, "installed_version", _no_sdk)
    specs_path = tmp_path / "info_specs_auto.py"
    specs_path.write_text(STAMPED_FILE, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    rc = drift.main(["--specs", str(specs_path)], out=out, err=err)
    assert rc == 1
    assert "not installed" in err.getvalue()


def test_missing_specs_file_fails(drift, monkeypatch, tmp_path):
    rc, out, err = _invoke(drift, monkeypatch, tmp_path, installed="3.1.113",
                           content=None, name="does_not_exist.py")
    assert rc == 1
    assert "SDK drift check failed" in err.getvalue()


def test_print_stamp(drift, tmp_path):
    specs_path = tmp_path / "info_specs_auto.py"
    specs_path.write_text(STAMPED_FILE, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    rc = drift.main(["--print-stamp", "--specs", str(specs_path)], out=out, err=err)
    assert rc == 0
    assert out.getvalue().strip() == "3.1.113"
    assert err.getvalue() == ""


def test_print_stamp_missing_file_fails(drift, tmp_path):
    out, err = io.StringIO(), io.StringIO()
    rc = drift.main(["--print-stamp", "--specs", str(tmp_path / "nope.py")],
                    out=out, err=err)
    assert rc == 1
    assert "SDK drift check failed" in err.getvalue()

