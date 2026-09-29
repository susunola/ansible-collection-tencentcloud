# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _find_script(name):
    """Locate a repository script from wherever this test file was copied.

    ``ansible-test units`` runs the tests from a copy that contains the plugin
    tree but not ``scripts/``, so ``parents[3]`` alone points at a directory
    where the script is absent and ``runpy`` answers with a confusing
    ``ImportError: can't find '__main__' module``. Walking up looks in every
    enclosing tree and says where it looked when it finds nothing.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / name
        if candidate.is_file():
            return candidate
    return None


SCRIPT = _find_script("check_remediation_freeze.py")


@pytest.mark.skipif(
    SCRIPT is None,
    reason="scripts/check_remediation_freeze.py is outside the tree this test "
           "was copied into (ansible-test units copies tests without scripts/)",
)
def test_freeze_script_print_exits_zero():
    """Run the script the way a user does.

    ``runpy.run_path`` on the script path raises ``ImportError: can't find
    '__main__' module in '<script>'`` under ``ansible-test units`` (its pytest
    invocation runs from the collection root, and runpy treats the path as a
    directory there), which says nothing about the script. A subprocess has no
    such heuristic: it runs the file and reports the exit status the test is
    actually about.
    """
    finished = subprocess.run(
        [sys.executable, str(SCRIPT), "--print"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert finished.returncode == 0, finished.stdout.decode("utf-8", "replace")


def test_allowlist_stays_under_cap():
    text = (ROOT / "docs" / "core-allowlist.yml").read_text(encoding="utf-8")
    names = [
        line.split("-", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("  - ")
    ]
    roles = {"tc_vpc_foundation", "tc_clb_http", "tc_tke_cluster"}
    modules = [name for name in names if name not in roles]
    assert len(modules) <= 120
    assert len(modules) == len(set(modules))
    assert "ame_ktv_robot_info" not in modules
    assert "alb_listener" not in modules
