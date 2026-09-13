"""Find expired E2E resources and emit a cleanup plan.

Deletion remains delegated to the collection's cleanup integration target so
the reaper never embeds a second, unaudited cloud API implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from e2e_manifest import load, validate


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("tests/output/e2e-resources.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("tests/output/reaper-plan.json"))
    parser.add_argument("--fail-on-expired", action="store_true")
    parser.add_argument(
        "--warn-on-empty",
        action="store_true",
        help="report when no target registered anything, since an empty "
        "manifest makes this audit meaningless",
    )
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    entries = list(load(args.manifest))
    expired = []
    for entry in entries:
        validate(entry)
        expiry = datetime.fromisoformat(entry["expires_at"].replace("Z", "+00:00"))
        if not entry.get("deleted_at") and expiry <= now:
            expired.append(entry)
    if not entries and args.warn_on_empty:
        # An empty manifest is not "nothing expired", it is "nothing was
        # tracked" - reporting 0 expired here reads like a working safeguard
        # while the third cleanup line is doing no work at all.
        print(
            "WARNING: the E2E manifest is empty, so this expiry audit proves "
            "nothing. No integration target registers what it creates: wire "
            "`python scripts/e2e_manifest.py add` into the targets.",
            file=sys.stderr,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"generated_at": now.isoformat(), "expired": expired}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("expired resources: %d" % len(expired))
    return 1 if expired and args.fail_on_expired else 0


if __name__ == "__main__":
    raise SystemExit(main())
