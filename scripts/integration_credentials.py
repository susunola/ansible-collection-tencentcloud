"""Materialise Tencent Cloud credentials for ``ansible-test integration`` runs.

Why this exists
---------------
``ansible-test`` sanitises the environment it hands to ``ansible-playbook``:
only ``HOME``, ``PATH``, ``LC_ALL`` and a short platform-compatibility list
survive (``ansible_test._internal.util.common_environment``). Every
``TENCENTCLOUD_*`` variable is dropped, so a workflow that injects credentials
with a step-level ``env:`` block silently fails with::

    Set secret_id and secret_key, their TENCENTCLOUD_* environment variables,
    or the secret_id/secret_key keys of a profile in
    ~/.tencentcloud/default.configure.

The one channel that does survive is ``HOME``, and every module already falls
back to the TCCLI profile file ``$HOME/.tencentcloud/default.configure`` for
``secret_id``, ``secret_key``, ``token`` and ``region`` (see
``plugins/module_utils/client.py``). This script copies the environment into
that file so the credentials reach the module subprocess.

Run it once before ``ansible-test integration``, both in CI and locally:

    export TENCENTCLOUD_SECRET_ID=... TENCENTCLOUD_SECRET_KEY=...
    export TENCENTCLOUD_REGION=ap-guangzhou      # optional, defaults below
    python scripts/integration_credentials.py --write
    ansible-test integration key_pair --local

The file is written with mode 0600 and never printed unmasked.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_REGION = "ap-guangzhou"
SECTION = "default"
#: Keys of the ``[default]`` section understood by
#: ``plugins/module_utils/client.py`` — keep the two in sync.
PROFILE_KEYS = ("secret_id", "secret_key", "token", "region")


class MissingCredentials(Exception):
    """Raised when the environment does not carry a usable key pair."""


def profile_path(home: str | os.PathLike[str] | None = None) -> Path:
    """Return the TCCLI profile path under ``home`` (default: ``$HOME``)."""
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".tencentcloud" / "default.configure"


def values_from_env(env: dict[str, str] | None = None, region: str | None = None) -> dict[str, str]:
    """Return the profile values read from ``env``.

    ``region`` overrides ``TENCENTCLOUD_REGION``; when neither is set the
    documented CI default (``ap-guangzhou``) is used so a plain run matches
    the workflow.
    """
    source = os.environ if env is None else env
    values = {
        "secret_id": source.get("TENCENTCLOUD_SECRET_ID", ""),
        "secret_key": source.get("TENCENTCLOUD_SECRET_KEY", ""),
        "token": source.get("TENCENTCLOUD_TOKEN", ""),
        "region": region or source.get("TENCENTCLOUD_REGION", "") or DEFAULT_REGION,
    }
    return values


def render(values: dict[str, str]) -> str:
    """Render the profile values as TCCLI INI text."""
    lines = ["[%s]" % SECTION]
    for key in PROFILE_KEYS:
        value = values.get(key)
        if value:
            lines.append("%s = %s" % (key, value))
    return "\n".join(lines) + "\n"


def masked(values: dict[str, str]) -> dict[str, str]:
    """Return ``values`` with every secret reduced to a length hint."""
    out = dict(values)
    for key in ("secret_id", "secret_key", "token"):
        value = out.get(key)
        if value:
            out[key] = "%s…(%d chars)" % (value[:4], len(value))
    return out


def write(values: dict[str, str], home: str | os.PathLike[str] | None = None) -> Path:
    """Write the profile file and return its path."""
    if not values.get("secret_id") or not values.get("secret_key"):
        raise MissingCredentials(
            "TENCENTCLOUD_SECRET_ID and TENCENTCLOUD_SECRET_KEY must both be set "
            "before integration tests can run."
        )
    path = profile_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(values), encoding="utf-8")
    path.chmod(0o600)
    return path


def check(home: str | os.PathLike[str] | None = None) -> tuple[bool, dict[str, str]]:
    """Return ``(ok, values)`` for an existing profile file."""
    path = profile_path(home)
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith(("#", "[")):
                key, _sep, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError:
        return False, values
    ok = bool(values.get("secret_id") and values.get("secret_key") and values.get("region"))
    return ok, values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", help="home directory to write under (default: $HOME)")
    parser.add_argument("--region", help="override TENCENTCLOUD_REGION")
    parser.add_argument("--write", action="store_true", help="write the profile file (default action)")
    parser.add_argument("--check", action="store_true", help="verify an existing profile file")
    parser.add_argument("--dry-run", action="store_true", help="print the masked profile instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        ok, values = check(args.home)
        print("%s: %s" % ("ok" if ok else "missing", profile_path(args.home)))
        print("values: %s" % masked(values))
        return 0 if ok else 1

    values = values_from_env(region=args.region)

    if args.dry_run:
        print("would write %s:" % profile_path(args.home))
        print(masked(values))
        return 0

    try:
        path = write(values, args.home)
    except MissingCredentials as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    print("wrote %s (region=%s)" % (path, values["region"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
