"""Find expired E2E resources and emit a cleanup plan.

Deletion remains delegated to the collection's cleanup integration target so
the reaper never embeds a second, unaudited cloud API implementation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from e2e_manifest import load, validate


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("tests/output/e2e-resources.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("tests/output/reaper-plan.json"))
    parser.add_argument("--fail-on-expired", action="store_true")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    expired = []
    for entry in load(args.manifest):
        validate(entry)
        expiry = datetime.fromisoformat(entry["expires_at"].replace("Z", "+00:00"))
        if not entry.get("deleted_at") and expiry <= now:
            expired.append(entry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"generated_at": now.isoformat(), "expired": expired}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("expired resources: %d" % len(expired))
    return 1 if expired and args.fail_on_expired else 0


if __name__ == "__main__":
    raise SystemExit(main())
