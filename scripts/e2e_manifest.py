#!/usr/bin/env python3
"""Record and audit resources created by real-cloud integration tests."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {"run_id", "target", "resource_type", "resource_id", "region", "expires_at"}


def load(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(entry):
    missing = sorted(REQUIRED - set(entry))
    if missing:
        raise ValueError("missing manifest fields: %s" % ", ".join(missing))
    datetime.fromisoformat(entry["expires_at"].replace("Z", "+00:00"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=Path("tests/output/e2e-resources.jsonl"))
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    for name in sorted(REQUIRED):
        add.add_argument("--" + name.replace("_", "-"), required=True)
    add.add_argument("--name", default="")
    add.add_argument("--cost-class", choices=("free", "low", "medium", "high"), default="low")
    add.add_argument("--metadata", default="{}")
    sub.add_parser("audit")
    args = parser.parse_args(argv)
    if args.command == "add":
        entry = {name: getattr(args, name) for name in REQUIRED}
        entry.update(name=args.name, cost_class=args.cost_class, metadata=json.loads(args.metadata), recorded_at=datetime.now(timezone.utc).isoformat())
        validate(entry)
        args.path.parent.mkdir(parents=True, exist_ok=True)
        with args.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
        return 0
    entries = load(args.path)
    for entry in entries:
        validate(entry)
    active = [entry for entry in entries if not entry.get("deleted_at")]
    print(json.dumps({"records": len(entries), "active": len(active), "resources": active}, indent=2, sort_keys=True))
    return 1 if active else 0


if __name__ == "__main__":
    raise SystemExit(main())
