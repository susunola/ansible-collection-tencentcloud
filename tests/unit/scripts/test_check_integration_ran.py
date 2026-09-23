"""Regression tests for scripts/check_integration_ran.py.

A target that self-skips prints an "Explain skipped" task and exits green, so
a whole run can be green while executing nothing - the failure mode that let
the scheduled Integration workflow report success for months without running
a single test. These tests pin the gate that catches it.

The numbers below are real PLAY RECAP lines from CI run 34691360139 plus the
local private_dns run, not invented fixtures.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    "check_integration_ran", _REPO / "scripts" / "check_integration_ran.py"
)
_CHECK = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CHECK)  # type: ignore[union-attr]


def _recap(ok: int, changed: int, skipped: int, failed: int = 0) -> str:
    return (
        f"testhost                   : ok={ok:<4} changed={changed:<4} "
        f"unreachable=0    failed={failed:<4} skipped={skipped:<4} "
        f"rescued=0    ignored=0"
    )


def _log(*blocks: tuple[str, str]) -> str:
    out = []
    for target, recap in blocks:
        out.append(f"2026-09-12T11:34:21Z Running {target} integration test role")
        out.append("2026-09-12T11:34:22Z PLAY RECAP *******")
        out.append(f"2026-09-12T11:34:22Z {recap}")
    return "\n".join(out) + "\n"


# Real observations from CI run 34691360139 and the local private_dns run.
REAL_LOG = _log(
    ("apigateway_ip_strategy", _recap(ok=7, changed=0, skipped=11)),
    ("cls_alarm", _recap(ok=20, changed=9, skipped=1)),
    ("redis_replication_group", _recap(ok=3, changed=0, skipped=12)),
    ("tcr_immutable_tag_rule", _recap(ok=10, changed=3, skipped=1)),
    ("tcr_webhook_trigger", _recap(ok=11, changed=3, skipped=1)),
    ("private_dns", _recap(ok=12, changed=6, skipped=1)),
)


def test_parses_every_target_in_the_log():
    recaps = _CHECK.parse_log(REAL_LOG)
    assert set(recaps) == {
        "apigateway_ip_strategy",
        "cls_alarm",
        "redis_replication_group",
        "tcr_immutable_tag_rule",
        "tcr_webhook_trigger",
        "private_dns",
    }


def test_targets_that_ran_their_lifecycle_are_executed():
    recaps = _CHECK.parse_log(REAL_LOG)
    for target in ("cls_alarm", "tcr_immutable_tag_rule", "tcr_webhook_trigger", "private_dns"):
        assert recaps[target].changed > 0, target
        assert recaps[target].executed is True, target


def test_self_skipped_targets_are_not_executed():
    recaps = _CHECK.parse_log(REAL_LOG)
    assert recaps["apigateway_ip_strategy"].executed is False
    assert recaps["redis_replication_group"].executed is False


def test_ansi_colour_codes_are_stripped():
    coloured = REAL_LOG.replace("testhost", "\x1b[0;33mtesthost\x1b[0m")
    coloured = coloured.replace("ok=20  ", "\x1b[0;32mok=20  \x1b[0m")
    recaps = _CHECK.parse_log(coloured)
    assert recaps["cls_alarm"].ok == 20


def test_a_target_that_changed_nothing_but_ran_more_than_it_skipped_passes():
    # Defensive: a read-only target must not be flagged just for changed=0.
    recap = _CHECK.Recap(ok=9, changed=0, failed=0, skipped=2)
    assert recap.executed is True


def test_a_failed_target_is_not_reported_as_executed(tmp_path: Path):
    """Naming it keeps the table from claiming a failed target 'executed'."""
    log = tmp_path / "run.log"
    log.write_text(_log(("private_dns", _recap(ok=3, changed=0, skipped=3, failed=1))))
    assert _CHECK.parse_log(log.read_text())["private_dns"].failed == 1
    # The run is already red via ansible-test's exit code, so the gate itself
    # stays quiet about it rather than piling on a second failure reason.
    assert _CHECK.main(["--log", str(log), "--coverage", str(_REPO / "tests/integration/coverage.yml")]) == 0


def test_missing_log_file_fails(tmp_path: Path):
    assert _CHECK.main(["--log", str(tmp_path / "nope.log")]) == 1


def test_run_with_undeclared_skips_fails(tmp_path: Path):
    """The same log fails when the registry does NOT declare the exemptions."""
    coverage = tmp_path / "coverage.yml"
    coverage.write_text(
        "version: 1\n"
        "targets:\n"
        "  apigateway_ip_strategy: {cost: free}\n"
        "  redis_replication_group: {cost: high}\n"
        "  cls_alarm: {cost: medium}\n"
    )
    log = tmp_path / "run.log"
    log.write_text(REAL_LOG)
    assert _CHECK.main(["--log", str(log), "--coverage", str(coverage)]) == 1


def test_the_repo_registry_declares_the_two_account_blocked_targets(tmp_path: Path):
    """Guard the guard: the real registry must keep both exemptions, or CI reds."""
    log = tmp_path / "run.log"
    log.write_text(REAL_LOG)
    assert _CHECK.main(["--log", str(log), "--coverage", str(_REPO / "tests/integration/coverage.yml")]) == 0


def test_account_blocked_targets_are_tolerated(tmp_path: Path):
    """With both skips declared in the registry the same log passes."""
    coverage = tmp_path / "coverage.yml"
    coverage.write_text(
        "version: 1\n"
        "targets:\n"
        "  apigateway_ip_strategy: {cost: free, account_blocked: true}\n"
        "  redis_replication_group: {cost: high, account_blocked: true}\n"
        "  cls_alarm: {cost: medium}\n"
    )
    log = tmp_path / "run.log"
    log.write_text(REAL_LOG)
    assert _CHECK.main(["--log", str(log), "--coverage", str(coverage)]) == 0


def test_blocked_targets_are_read_from_the_registry():
    blocked = _CHECK.blocked_targets(_REPO / "tests" / "integration" / "coverage.yml")
    assert "apigateway_ip_strategy" in blocked
    assert "redis_replication_group" in blocked


def test_requested_target_with_no_recap_fails(tmp_path: Path):
    log = tmp_path / "run.log"
    log.write_text(_log(("cls_alarm", _recap(ok=20, changed=9, skipped=1))))
    assert _CHECK.main(["--log", str(log), "--targets", "cls_alarm tke_addon"]) == 1
    assert (
        _CHECK.main(["--log", str(log), "--targets", "cls_alarm tke_addon", "--skip-missing"]) == 0
    )


@pytest.mark.parametrize(
    ("ok", "changed", "skipped", "expected"),
    [
        (20, 9, 1, True),   # cls_alarm
        (12, 6, 1, True),   # private_dns
        (7, 0, 11, False),  # apigateway: skipped more than it ran
        (3, 0, 12, False),  # redis: gate never configured
        (1, 0, 4, False),   # bare "Explain skipped" only
    ],
)
def test_executed_classification(ok: int, changed: int, skipped: int, expected: bool):
    assert _CHECK.Recap(ok=ok, changed=changed, failed=0, skipped=skipped).executed is expected
