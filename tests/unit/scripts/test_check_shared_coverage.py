# -*- coding: utf-8 -*-
# Copyright: (c) 2026 Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/old-licenses/gpl-3.0.txt)
"""Tests for scripts/check_shared_coverage.py.

The gate exists because the collection-wide coverage floor cannot see one
untested file. These tests pin what it reads out of a report and the two ways
it can be wrong: counting a file that is not shared, and passing a file that is
below the floor.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_shared_coverage.py"

COVERAGE = """<?xml version="1.0" ?>
<coverage>
  <packages>
    <package name="plugins.module_utils">
      <classes>
        <class filename="ansible_collections/susunola/tencentcloud/plugins/module_utils/base.py" line-rate="1.0"/>
        <class filename="ansible_collections/susunola/tencentcloud/plugins/module_utils/client.py" line-rate="0.91"/>
        <class filename="ansible_collections/susunola/tencentcloud/plugins/module_utils/thin.py" line-rate="0.50"/>
      </classes>
    </package>
    <package name="plugins.plugin_utils">
      <classes>
        <class filename="ansible_collections/susunola/tencentcloud/plugins/plugin_utils/tags.py" line-rate="1.0"/>
      </classes>
    </package>
    <package name="plugins.modules">
      <classes>
        <class filename="ansible_collections/susunola/tencentcloud/plugins/modules/cvm_instance.py" line-rate="0.10"/>
      </classes>
    </package>
  </packages>
</coverage>
"""


def _load_script():
    spec = importlib.util.spec_from_file_location("check_shared_coverage", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def coverage():
    return _load_script()


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "coverage.xml"
    path.write_text(COVERAGE, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# reading the report
# --------------------------------------------------------------------------

def test_only_shared_helpers_are_read(report, coverage):
    """A module at 10% is the measure's business, not this gate's."""
    files = dict(coverage.shared_files(str(report))[0])
    assert set(files) == {
        "plugins/module_utils/base.py",
        "plugins/module_utils/client.py",
        "plugins/module_utils/thin.py",
        "plugins/plugin_utils/tags.py",
    }


def test_rates_are_percentages(report, coverage):
    files = dict(coverage.shared_files(str(report))[0])
    assert files["plugins/module_utils/base.py"] == 100.0
    assert files["plugins/module_utils/client.py"] == 91.0


# --------------------------------------------------------------------------
# judging it
# --------------------------------------------------------------------------

def test_a_file_below_the_floor_fails(report, coverage, capsys):
    assert coverage.main(["--coverage-xml", str(report)]) == 1
    out = capsys.readouterr().out
    assert "plugins/module_utils/thin.py" in out
    assert "1 shared helper(s) below 85%" in out


def test_a_floor_below_every_file_passes(report, coverage, capsys):
    assert coverage.main(["--coverage-xml", str(report), "--min", "40"]) == 0
    assert "at or above 40%" in capsys.readouterr().out


def test_the_floor_is_applied_per_file(report, coverage, capsys):
    """91% passes a 90 floor and fails a 95 one, which is the whole point:
    the total can be high while one file is not."""
    assert coverage.main(["--coverage-xml", str(report), "--min", "90"]) == 1
    below = [line for line in capsys.readouterr().out.splitlines() if "BELOW" in line]
    assert len(below) == 1 and "thin.py" in below[0]


def test_a_missing_report_is_reported(tmp_path, coverage, capsys):
    assert coverage.main(["--coverage-xml", str(tmp_path / "nothing.xml")]) == 2
    assert "no coverage report" in capsys.readouterr().err


def test_a_bare_file_name_is_resolved_against_the_shared_directories(report, coverage):
    """Pointed at a directory, coverage records bare names; the gate has to
    read that shape too, and it does so from the files on disk."""
    files, ambiguous = coverage.shared_files(str(report))
    assert ambiguous == []
    assert any(path.endswith("plugins/module_utils/base.py") for path, _rate in files)


def test_a_name_in_two_directories_is_reported_rather_than_guessed(tmp_path, coverage, capsys):
    """inventory.py, paging.py and polling.py exist in both module_utils and
    plugin_utils, so a bare name cannot be attributed -- the gate says so
    instead of holding the wrong file to the floor."""
    path = tmp_path / "ambiguous.xml"
    path.write_text(
        '<?xml version="1.0" ?><coverage><packages><package><classes>'
        '<class filename="inventory.py" line-rate="1.0"/>'
        '</classes></package></packages></coverage>\n', encoding="utf-8")
    assert coverage.main(["--coverage-xml", str(path)]) == 2
    assert "matches more than one directory" in capsys.readouterr().err


def test_a_report_without_shared_files_is_reported(tmp_path, coverage, capsys):
    path = tmp_path / "empty.xml"
    path.write_text('<?xml version="1.0" ?>\n<coverage><packages/></coverage>\n', encoding="utf-8")
    assert coverage.main(["--coverage-xml", str(path)]) == 2
    assert "no shared helper" in capsys.readouterr().err
