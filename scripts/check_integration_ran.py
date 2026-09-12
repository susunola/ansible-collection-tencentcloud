#!/usr/bin/env python
"""Fail an integration run whose targets only ever skipped.

Every target self-skips when its gate variable is unset (it prints an
"Explain skipped ..." task and exits green), so a run can be green while
executing no test at all - the exact failure mode that let the scheduled
workflow report success for months without running anything.

This gate reads the ``ansible-test integration`` log and decides, per target,
whether the target actually exercised its module. A target that created or
changed nothing while skipping more tasks than it ran never reached its
module, so it counts as NOT EXECUTED.

Targets the account genuinely cannot host (API Gateway is stopped for sale,
Redis replication groups are whitelist-only) are exempt via
``account_blocked: true`` in tests/integration/coverage.yml. That keeps the
exemptions in the registry instead of hard-coding them here, so adding a
target to the default list without wiring its gate fails the run.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# "Running cls_alarm integration test role"
_TARGET_LINE = re.compile(r"Running\s+(?P<target>[A-Za-z0-9_]+)\s+integration test role")
# "testhost : ok=20  changed=9  unreachable=0  failed=0  skipped=1  ...".
# Not anchored: CI prefixes every line with "<job>\t<step>\t<timestamp>Z ".
_RECAP_LINE = re.compile(
    r"(?:^|\s)(?P<host>[A-Za-z0-9_.-]+)\s*:\s*ok=(?P<ok>\d+)\s+changed=(?P<changed>\d+)\s+"
    r"unreachable=\d+\s+failed=(?P<failed>\d+)\s+skipped=(?P<skipped>\d+)"
)
# ansible-test --color wraps every field in SGR sequences. GitHub stores those
# as the literal two-character form "^[[", so match both that and a real ESC.
_ANSI = re.compile(r"(?:\x1b|\^\[)\[[0-9;]*m")


class Recap:
    __slots__ = ("ok", "changed", "failed", "skipped")

    def __init__(self, ok: int, changed: int, failed: int, skipped: int) -> None:
        self.ok = ok
        self.changed = changed
        self.failed = failed
        self.skipped = skipped

    @property
    def executed(self) -> bool:
        """True when the target reached its module and did real work."""
        if self.changed:
            return True
        # Nothing changed: it only ran when it ran more tasks than it skipped.
        # Every real lifecycle changes at least one resource.
        return self.skipped <= self.ok


def parse_log(text: str) -> dict[str, Recap]:
    """Map target name -> its PLAY RECAP, in log order."""
    recaps: dict[str, Recap] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = _ANSI.sub("", raw)
        started = _TARGET_LINE.search(line)
        if started:
            current = started.group("target")
            continue
        recap = _RECAP_LINE.search(line)
        if recap and current:
            recaps[current] = Recap(
                ok=int(recap.group("ok")),
                changed=int(recap.group("changed")),
                failed=int(recap.group("failed")),
                skipped=int(recap.group("skipped")),
            )
    return recaps


def blocked_targets(coverage: Path) -> set[str]:
    data = yaml.safe_load(coverage.read_text()) or {}
    targets = data.get("targets") or {}
    return {name for name, spec in targets.items() if (spec or {}).get("account_blocked")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", required=True, type=Path, help="ansible-test integration output")
    parser.add_argument("--coverage", type=Path, default=Path("tests/integration/coverage.yml"))
    parser.add_argument(
        "--targets",
        default="",
        help="space separated targets the run was asked to execute",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="do not fail when a requested target produced no recap at all",
    )
    args = parser.parse_args(argv)

    if not args.log.exists():
        print(f"FAIL integration log not found: {args.log}")
        return 1

    recaps = parse_log(args.log.read_text(errors="replace"))
    blocked = blocked_targets(args.coverage) if args.coverage.exists() else set()
    requested = [t for t in args.targets.split() if t]
    missing = [t for t in requested if t not in recaps]

    print(f"{'target':<28}{'ok':>5}{'chg':>5}{'skip':>6}{'fail':>6}  verdict")
    print("-" * 62)
    not_executed: list[str] = []
    for target, recap in recaps.items():
        if recap.failed:
            # ansible-test already fails the run for this; naming it here keeps
            # the table from claiming a failed target "executed".
            verdict = "FAILED (see run log)"
        elif recap.executed:
            verdict = "executed"
        elif target in blocked:
            verdict = "SKIPPED (account cannot host)"
        else:
            verdict = "NOT EXECUTED"
            not_executed.append(target)
        print(
            f"{target:<28}{recap.ok:>5}{recap.changed:>5}{recap.skipped:>6}{recap.failed:>6}  {verdict}"
        )

    for target in missing:
        print(f"{target:<28}{'-':>5}{'-':>5}{'-':>6}{'-':>6}  NO RECAP")

    errors: list[str] = []
    if not_executed:
        errors.append(
            "targets reported green without running their module: "
            + ", ".join(sorted(not_executed))
            + " -- configure their gate variables, or mark them account_blocked in "
            + str(args.coverage)
            + " if the account genuinely cannot host them"
        )
    if missing and not args.skip_missing:
        errors.append("targets produced no PLAY RECAP at all: " + ", ".join(missing))

    if errors:
        print()
        for err in errors:
            print(f"FAIL {err}")
        return 1

    print()
    print("OK every target either executed or is a documented account limitation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
