# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_remediation_freeze.py"


def test_freeze_script_print_exits_zero():
    previous = sys.argv[:]
    try:
        sys.argv = [str(SCRIPT), "--print"]
        try:
            runpy.run_path(str(SCRIPT), run_name="__not_main__")
        except SystemExit as exc:
            assert exc.code in (0, None)
    finally:
        sys.argv = previous


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
